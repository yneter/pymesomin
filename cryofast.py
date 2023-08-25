# -*- coding: utf-8 -*-

        # data.decode(encoding='utf-8').rstrip().rstrip()
        
from pymesomin.magnetsafety import MagnetCheckCryofast
from pymesomin.instruments import Instrument
from pymesomin.instruments import SocketInstrument
from pymesomin.instruments import report_and_exit

import sys
import re
import numpy as np
import aiohttp

class AMI_Cryofast( SocketInstrument ) :
    def __init__( self, address, instrument_name) : 
        SocketInstrument.__init__(self, address, instrument_name) 
        self.mcheck = MagnetCheckCryofast()
        print( self.read_dev() ) # read welcome message
  
    def set(self, name, value, args = [ ]) :
        if self.mcheck.error() and name == "field" and abs( float(value) ) > 0 : 
            sys.stderr.write("magnet error detected - will not set field>0 before reset, to reset run:\n")
            sys.stderr.write("from pymesomin.magnetsafety import MagnetCheckCryofast\n") 
            sys.stderr.write("MagnetCheckCryofast().reset_error()\n")    
        else: 
            super().set(name, value, args)
        

class AMIZ( AMI_Cryofast ) :
    instruction_file = "instrufiles/amiZ.txt" 

class AMIX( AMI_Cryofast ) :
    instruction_file = "instrufiles/amiX.txt" 

class AMIY( AMI_Cryofast ) :
    instruction_file = "instrufiles/amiY.txt" 

    
class Bluefors ( Instrument ) :
    instruction_file = "instrufiles/cryofast.txt"

    import requests
    import json
    import urllib.parse as up # import urlparse, parse_qs
    import datetime
    import re
    
    def __init__( self, address, instrument_name) : 
        self.address = address
        Instrument.__init__(self, instrument_name)        

    def format_request(self, message):
        try : 
            parameter, url_pattern = re.split('\s+', message)    
        except ValueError:
            sys.stderr.write("%s.read_dev error processing : %s\n" % (type(self).__name__, message))
            return ""
        url_name = url_pattern.replace("$address", self.address )
        parsed_url = self.up.urlparse(url_name)
        args =  self.up.parse_qs(parsed_url.query)
        request_param = { k:int(v[0]) for k, v in args.items() }
        now = self.datetime.datetime.utcnow()
        start = now - self.datetime.timedelta(minutes=5)        
        request_param.update( {
            'start_time' : start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'stop_time' : now.strftime("%Y-%m-%dT%H:%M:%SZ"), 
        } )
        request_param['fields'] = [ parameter ]
        return url_name, parameter, request_param

    def read_dev(self, message) :
        url_name, parameter, request_param = self.format_request(message)
        req = self.requests.post(url_name, json=request_param, timeout=10)    
        data = req.json()
        return str(data['measurements'][parameter][-1])

    def write_for_read(self, message) :
        """ does nothing as read_dev directly reads measurement """        
        pass

    async def get_async(self, instru_parameter, arguments):
        message = self.get_message(instru_parameter, arguments)
        if not message: return ""
        url_name, parameter, request_param = self.format_request(message)
        async with aiohttp.ClientSession() as session:
            async with session.post(url_name, json=request_param) as response:
                data = await response.json()
                return str(data['measurements'][parameter][-1])

        
    def write_dev(self, message) :
        try :
            parameter, url_pattern, value = re.split('\s+', message)  
        except ValueError: 
            sys.stderr.write("%s.write_dev error processing : %s\n" % (type(self).__name__, message))
            return 
            
        url_name = url_pattern.replace("$address", self.address )
        parsed_url = self.up.urlparse(url_name)
        args =  self.up.parse_qs(parsed_url.query)
        request_param = { k:int(v[0]) for k, v in args.items() }
        request_param[parameter] = float(value)
        self.requests.post(url_name, json=request_param, timeout=10)          



class BlueforsSoftware ( Instrument ): 
    instruction_file = "instrufiles/bluefors_control_software.txt"

    import requests
    import json
    
    def __init__( self, address, instrument_name) : 
        if address[-1] != '/':
            self.address = address + "/"
        else:
            self.address = address
        Instrument.__init__(self, instrument_name)    

    def format_request(self, message):
        url_name = self.address + message.replace(".", "/")
        return url_name
    
    def process_response(self, message, reply):
        try:
            return reply['data'][message]['content']['latest_valid_value']['value']
        except TypeError:
            return "NoReplyFromServer"
    
    def write_for_read(self, message) :
        """ does nothing as read_dev directly reads measurement """        
        pass
    
    def read_dev(self, message) :
        url_name = self.format_request(message)
        req = self.requests.get(url_name, timeout=10)    
        return self.process_response(message, req.json())


    async def get_async(self, instru_parameter, arguments):
        message = self.get_message(instru_parameter, arguments)
        if not message: return ""
        url_name = self.format_request(message)
        async with aiohttp.ClientSession() as session:
            async with session.get(url_name) as response:
                reply = await response.json()
                return self.process_response(message, reply )

    
    def write_dev(self, message) :
        sys.stderr.write("writing not implemented\n")
        pass

from .runexp import Experiment
    
class Cryofast( Experiment ) : 
    """
    defines Cryofast experiment, adding Bluefors and AMI X, Y, Z power supplies
    overloads set_instru and get_from_instru to implement fast on the fly preliminary safety checks 
    
    """
    def __init__( self, instru_list) :
        Experiment.__init__(self, 
                            [ Bluefors("192.168.10.54:5001", "cryo"), 
                             BlueforsSoftware("http://localhost:49099/values", "bf"),
                             AMIZ("192.168.10.31:7180", "amiZ"),
                             AMIX("192.168.10.33:7180", "amiX"),
                             AMIY("192.168.10.32:7180", "amiY"), ] + 
                            instru_list)
        
        self.ami = { "amiZ", "amiY", "amiX"}
        self.sample_rot = None
        self._ramping_fields =[ ]
        self.field = { }       # dictionary with field values stored as float numbers
        self.setp_field = { }  # dictionary with field setpoint values stored as float numbers
        self.start_field = { } 
        self.update_magnet_info()  # start by updating magnet info 
        
    def _update_setpoint(self, instru_name, value):
        self.setp_field[instru_name] = float(value)

        
    def _update_field(self, instru_name, value):
        self.field[instru_name] = float(value)  
        
    def _vector_field_not_safe_old(self, instru_name, value):
        ami_perp = self.ami.copy()
        ami_perp.remove( instru_name )
        B2_current_value = 0
        B2_perp_current_value = 0
        B2_setpoint_value = 0       
        for ami_name in self.field:
            B2_current_value += self.field[ami_name]**2
        for ami_name in ami_perp:
            if ami_name in self.setp_field:
                B2_setpoint_value += self.setp_field[ami_name]**2
                B2_perp_current_value += self.field[ami_name]**2
        if max( B2_perp_current_value, B2_setpoint_value ) > 0.003**2 : 
            """ vector mode  """
            B2_setpoint_value += float(value)**2
            if B2_setpoint_value > 1.001:
                return True
        return False
    
    def _vector_field_not_safe(self, field_name, value):
        other_fields = self.ami.copy()
        other_fields.remove( field_name )
        
        
        B2_other_fields = 0     
        B2_other_fields_setpoint = 0 
        for b in other_fields:
            B2_other_fields += self.field[b]**2
            if b in self.setp_field:
                B2_other_fields_setpoint += self.setp_field[b]**2

        if max( B2_other_fields, B2_other_fields_setpoint ) > 0.003**2 : 
            """ vector mode  """
            max_B2_xy = 0.42
            max_Bz = 1.5
            B2_setpoint = float(value)**2 + B2_other_fields_setpoint
            if B2_setpoint > 1.001:
                """
                we are beyond |B| <= 1 safety limit 
                """
                if field_name == "amiZ":
                    """
                    updating Bz: condition on amplitude of in plane field and upper bound on Bz setpoint
                    """
                    B2_xy_current = self.field["amiX"]**2 + self.field["amiY"]**2
                    if B2_xy_current > max_B2_xy**2 or abs(float(value)) > max_Bz:
                        return True
                else:
                    """
                    check amplitude of setpoint in plane field
                    """
                    if "amiZ" not in self.setp_field:
                        return True
                    else: 
                        B2_xy_setpoint = B2_setpoint - self.setp_field["amiZ"]**2
                        if B2_xy_setpoint > max_B2_xy**2 : 
                            return True
        return False
    
    
    
    def update_magnet_info(self):
        for ami in self.ami: 
            self.field[ami] = float( self.get_from_instru(ami, "field") )
        for ami in self.ami: 
            self.setp_field[ami] = float( self.get_from_instru(ami, "target") )

    def magnet_info(self):
        sys.stderr.write("stored run_time magnet values, may not coincide with real values\n")
        sys.stderr.write( str(self.field) + "  " + str(self.setp_field) + "\n" )
        sys.stderr.write("%s.update_magnet_info() to update\n"  % self._my_name())
 

    def _my_name(self):
        return "(Cryofast instance name)"
    
    def set_instru(self, instru_name, var_name, value, args = [ ]) :
        if instru_name in self.ami and var_name == "field" :
            if self._vector_field_not_safe(instru_name, value) :
                sys.stderr.write("vector_field error - make sure total B < 1 - no field update on %s\n" % instru_name)
                sys.stderr.write("%s.fields() to check all fields\n" % self._my_name())
                sys.stderr.write("%s.magnet_info() to check stored magnet run_time values\n" % self._my_name())               
                sys.stderr.write("%s.update_magnet_info() to update run_time safety\n"  % self._my_name())
                return 
            else:
                self._update_setpoint(instru_name, value)
        super().set_instru(instru_name, var_name, value, args)
        
    def fields(self):
        return "Bz = %s , By = %s, Bx = %s" % ( self.get("amiZ.field"), self.get("amiY.field"), self.get("amiX.field"))

    def field_vec(self):
        return np.array( [ float( self.get("amiX.field") ), float( self.get("amiY.field") ), float( self.get("amiZ.field") ) ] )
    
    def target_fields(self):
        return "Bz_set = %s , By_set = %s, Bx_set = %s" % ( self.get("amiZ.target"), self.get("amiY.target"), self.get("amiX.target"))
 
    def set_fields(self, Bx : float, By : float, Bz : float) : 
        Bx_set = False
        By_set = False
        Bz_set = False
        """
        because of safety rules the order in which we attempt to set the fields matters
        We start by magnetic fields components that decrease total |B| 
        """
        if abs(Bx) < abs(self.field["amiX"]):
            self.set("amiX.field", Bx)
            Bx_set = True
        if abs(By) < abs(self.field["amiY"]):
            self.set("amiY.field", By)
            By_set = True
        if abs(Bz) < abs(self.field["amiZ"]):
            self.set("amiZ.field", Bz)
            Bz_set = True
        """
        we now attempt to set the remaining fields
        """
        if Bx is not None and not Bx_set:
            self.set("amiX.field", Bx)
        if By is not None and not By_set:
            self.set("amiY.field", By)
        if Bz is not None and not Bz_set:
            self.set("amiZ.field", Bz)

    def set_fields_rate(self, Bx : float, By : float, Bz : float, rate : float) : 
        if rate == 0:
            sys.sterr.write("set_fields_rate : rate = 0, choose a rate > 0")
            return
        if self.test_mode:
            return 
        Bvec = self.field_vec()
        vBx, vBy, vBz = Bx, By, Bz
        if vBx is None:
            vBx = Bvec[0]
        if vBy is None:
            vBy = Bvec[1]
        if vBz is None:
            vBz = Bvec[2]
        u_vec = (np.array( [ vBx, vBy, vBz ] ) - Bvec)
        u_norm = np.linalg.norm(u_vec)
        if u_norm < 1e-4: 
            return 
        rate_vec = rate * u_vec / u_norm
        rate_limit = 1e-6
        if (abs(rate_vec[0]) > rate_limit):
            self.set("amiX.rate", abs( rate_vec[0] ) )
        if (abs(rate_vec[1]) > rate_limit):
            self.set("amiY.rate", abs( rate_vec[1] ) )
        if (abs(rate_vec[2]) > rate_limit):
            self.set("amiZ.rate", abs( rate_vec[2] ) )        
        self.set_fields(Bx, By, Bz)
        
    def value_from_instru_ready(self, instru_name, var_name, value ) :
        if instru_name in self.ami and var_name == "field":
            self._update_field(instru_name, value)
            
    
    def stop_record(self) -> bool:
        """
        redefines Experiment.stop_record() to return True 
        at the end of the magnet ramp
        """
        for ami in self._ramping_fields:
            if self.get_from_instru(ami, "state") == '1': # ramping 
                return False
        return True
    
    def record_eta(self) -> float: 
        eta_list = [ ]
        for ami in self._ramping_fields:
            if ami in self.start_field:
                if abs(self.setp_field[ami] - self.start_field[ami]) > 1e-6:
                    eta_ami =  abs( (self.field[ami] - self.start_field[ami]) / (self.setp_field[ami] - self.start_field[ami]) )
                    eta_list.append( eta_ami )
                else:   
                    eta_list.append( 1. )
        return min(eta_list)
            
    def find_ramping_fields(self) :
        self._ramping_fields = [ ]
        for ami in self.ami: 
            if self.get_from_instru(ami, "state") == '1': # ramping 
                self._ramping_fields.append( ami )
                if ami in self.field:
                    self.start_field[ami] = self.field[ami]

    def record_magnet_ramp(self, wait, outfile=None, write_log=True, display=True, reset_plot = True, record_callback=None) : 
        """ 
        starts by finding the ramping fields
        then call self.record with total_time = None, 
        record then finishes when stop_record() == True
        """
        self.find_ramping_fields()
        self.record(wait, None, outfile, write_log, display, reset_plot, record_callback)
        
    def set_sample_frame(self, rotation_matrix):
        """
        rotation_matrix : numpy 3x3 matrix, col(1) gives sample x direction, col(2) sample y, col(3) sample z
        this matrix roates from sample frame to lab frame
        """
        err_norm = np.linalg.norm( np.dot( rotation_matrix.transpose(), rotation_matrix ) - np.identity(3) )
        if err_norm > 1e-10: 
            sys.stderr.write("argument is not a rotation matrix\n")
            return
        else:
            self.sample_rot = rotation_matrix

    def set_sample_B_direction_rate(self, j : int, new_b, b_rate):
        """
        j : 0,1,2 integer giving direction 
        new_b : new sample frame B value along direction j
        b_rate : at which we move 
        """
        if self.sample_rot is None:
            sys.stderr.write("rotation matrix is not defined, use self.set_sample_frame(matrix) to set it\n")
            return 
        if self.test_mode : 
            return
        u_vec = self.sample_rot[:,j]
        b_vec = self.field_vec()
        b_sample_vec = np.dot( self.sample_rot.transpose(), b_vec )
        new_b_sample_vec = b_sample_vec
        new_b_sample_vec[j] = new_b # we will change only one field component at a time in the sample fame
        new_b_vec = np.dot( self.sample_rot, new_b_sample_vec)
        rate_vec = u_vec * b_rate
        
        rate_limit = 1e-6
        if (abs(rate_vec[0]) > rate_limit):
            self.set("amiX.rate", abs( rate_vec[0] ) )
        if (abs(rate_vec[1]) > rate_limit):
            self.set("amiY.rate", abs( rate_vec[1] ) )
        if (abs(rate_vec[2]) > rate_limit):
            self.set("amiZ.rate", abs( rate_vec[2] ) )
        
        self.set_fields( new_b_vec[0], new_b_vec[1], new_b_vec[2] )
        
    def set_sample_Bx_rate(self, bx : float, bx_rate : float) :
        self.set_sample_B_direction_rate(0, bx, bx_rate)

    def set_sample_By_rate(self, by : float, by_rate : float) :
        self.set_sample_B_direction_rate(1, by, by_rate)

    def set_sample_Bz_rate(self, bz : float, bz_rate : float) :
        self.set_sample_B_direction_rate(2, bz, bz_rate)

    def set_sample_fields_rate(self, bx: float, by: float, bz: float, rate: float) : 
        newB = np.dot( self.sample_rot, np.array( [bx, by, bz] ))
        self.set_fields_rate(newB[0], newB[1], newB[2], rate)

    def sample_fields(self) : 
        if self.test_mode:
            return ""
        b_vec = self.field_vec()
        b_sample_vec = np.dot( self.sample_rot.transpose(), b_vec )
        return "Bz(sample) = %f, By(sample) = %f, Bx(sample) = % f" % ( b_sample_vec[2], b_sample_vec[1],b_sample_vec[0])
        
    def sample_Bx_formula(self) : 
        if self.sample_rot is None:
            report_and_exit("set sample frame using: hexp.set_sample_frame")
        return "(%f) * Bx + (%f) * By + (%f) * Bz" % ( self.sample_rot[0,0],  self.sample_rot[1,0],  self.sample_rot[2,0])

    def sample_By_formula(self) :
        if self.sample_rot is None:
            report_and_exit("set sample frame using: hexp.set_sample_frame")     
        return "(%f) * Bx + (%f) * By + (%f) * Bz" % ( self.sample_rot[0,1],  self.sample_rot[1,1],  self.sample_rot[2,1])

    def sample_Bz_formula(self) : 
        if self.sample_rot is None:
            report_and_exit("set sample frame using: hexp.set_sample_frame")
        return "(%f) * Bx + (%f) * By + (%f) * Bz" % ( self.sample_rot[0,2],  self.sample_rot[1,2],  self.sample_rot[2,2])

