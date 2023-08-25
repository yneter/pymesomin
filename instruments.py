from .runexp import Instrument
from .runexp import Parameter
import re 
import sys 
import time 
import numpy as np
import asyncio


def report_and_exit(message : str):
    sys.stderr.write(message + "\n")
    sys.exit()


try:
    import pyvisa as visa

    class GPIB_Instrument( Instrument ) : 
        def __init__( self, address, instrument_name) : 
            rm = visa.ResourceManager()
            self.vi = rm.open_resource(address) 
            Instrument.__init__(self, instrument_name)

        def write_dev(self, message):
            return self.vi.write(message)

        def read_dev(self, message = ""):
            return self.vi.read().rstrip()

    class SR830( GPIB_Instrument ) : instruction_file = "instrufiles/sr830.txt" 

    class ARF( GPIB_Instrument ) : instruction_file = "instrufiles/AE8257d.txt" 

    class SRSIM( GPIB_Instrument ) : instruction_file = "instrufiles/srsim.txt"

    class ITC503( GPIB_Instrument ) : 
        instruction_file = "instrufiles/itc503.txt"
        def __init__( self, address, instrument_name) : 
            GPIB_Instrument.__init__(self, address, instrument_name)
            self.vi.read_termination = '\r'
            
            
        def get(self, pname, args = [], wait = 0.005) :
            s = super().get(pname, args, wait)
            try :
                value = re.search('[A-Z]*(.+)', s).group(1) 
                float(value)
                return value
            except ValueError:
                return s
            except AttributeError:
                return s

        def set(self, name, value, args = [ ], wait = 0.005):
            super().set(name, value, args, wait)
            self.read_dev("")
            

    class Yoko200( GPIB_Instrument ) : instruction_file = "instrufiles/yokoGS200.txt" 

    class Yoko610( GPIB_Instrument ) : instruction_file = "instrufiles/yokoGS610.txt" 

    class Yoko( GPIB_Instrument ) : 
        instruction_file = "instrufiles/yoko.txt"  # "instrufiles/yoko.txt"
        def get(self, pname, args = []) :
            """ maybe we should use super().get here instead of Instrument.get """
            s = Instrument.get(self, pname, args)
            try :
                return re.search('[A-Z]*(.+)', s).group(1) 
            except AttributeError:
                return s

    class PPMS( GPIB_Instrument ) : 
        instruction_file = "instrufiles/ppms.txt"
        def get(self, pname, args = []) :
            """ maybe we should use super().get here instead of Instrument.get """
            s = Instrument.get(self, pname, args)
            try :
                return re.search('.*,(.+);', s).group(1) 
            except AttributeError:
                return s
            

    class Keithley2100( GPIB_Instrument ) : instruction_file = "instrufiles/keithley2100.txt"


    class Keithley7001( GPIB_Instrument ) : 
        instruction_file = "instrufiles/keithley7001.txt"
        #def __init__(self, main_resource_manager, card_number,address_number):
        #    self.wrapped_GpibInstrument = main_resource_manager.open_resource('GPIB'+str(card_number)+'::'+str(address_number)+'::INSTR', read_termination='\n')
        current_configuration = ''
        def ground(self):
            self.write_dev(':CLOS (@1!1!10,1!2!10,1!3!10,1!4!10,2!1!10,2!2!10,2!3!10,2!4!10)')
            self.readconfig()

        def hardground(self):
            self.write_dev(':CLOS (@1!1!8,1!2!8,1!3!8,1!4!8,2!1!8,2!2!8,2!3!8,2!4!8,1!1!10,1!2!10,1!3!10,1!4!10,2!1!10,2!2!10,2!3!10,2!4!10)')
            self.readconfig()

        def clearall(self):
            self.write_dev(':OPEN ALL')
            self.readconfig()

        def K7001_set(self, new_config_numeric):
            self.ground()

            new_config_string=str(new_config_numeric)
            close_string=':CLOS (@'
            open_string=':OPEN (@'
            for i in range(0,10):
                if int(new_config_string[i])==0:
                    for j in range(1,9):
                        if j>=5:
                            ochips='2!'
                            joprime=str(j-4)
                        else:
                            ochips='1!'
                            joprime=str(j)
                        open_string=open_string+ochips+joprime+'!'+str(i+1)+','
                else:
                    if int(new_config_string[i])>=5:
                        cchips='2!'
                        jcprime=str(int(new_config_string[i])-4)
                    else:
                        cchips='1!'
                        jcprime=new_config_string[i]
                    close_string=close_string+cchips+jcprime+'!'+str(i+1)+','
                    for j in range(1,9):
                        if j==int(new_config_string[i]):
                            pass
                        else:
                            if j>=5:
                                ochips='2!'
                                joprime=str(j-4)
                            else:
                                ochips='1!'
                                joprime=str(j)
                            open_string=open_string+ochips+joprime+'!'+str(i+1)+','
            open_string=open_string[:-1]+')'
            if len(open_string)==8:
                open_string=''
            close_string=close_string[:-1]+')'
            if len(close_string)==8:
                close_string=''
            command_string=close_string+';'+open_string
            time.sleep(1)
            #print(command_string)
            self.write_dev(command_string)
            time.sleep(1)
            self.readconfig()

        def readconfig(self):
            #config=self.get(':CLOS? (@ 1!1!1:1!1!10,1!2!1:1!2!10,1!3!1:1!3!10,1!4!1:1!4!10,2!1!1:2!1!10,2!2!1:2!2!10,2!3!1:2!3!10,2!4!1:2!4!10)')
            self.config=self.get('closed')
            self.configarray_1D=np.array(list(map(int,self.config.split(','))))
            self.configmatrix=self.configarray_1D.reshape(8,10)
            self.config_digits=np.zeros(10,dtype=int)
            if np.all(self.configmatrix==0)==True:
                self.config_string='CLEARED'
            elif np.all(self.configmatrix[:,9])==True and np.all(self.configmatrix[:,7])==True:
                self.config_string='HARD GROUNDED'
            elif np.all(self.configmatrix[:,9])==True:
                self.config_string='GROUNDED'
            else:
                for j in range(10):
                    for i in range (8):
                        if self.configmatrix[i,j]==1:
                            self.config_digits[j]=i+1
                        else:
                            pass
                self.config_string=self.config_digits                      
            self.current_configuration = self.config_string
            return self.config_string

        def read_dev(self, message):
            if "config" in message.casefold():
                return str(self.readconfig())
            else:
                return super().read_dev(message)

        def write_dev( self, message ) : 
            if "setconfig" in message:
                self.K7001_set( message.split()[-1] )
            else:
                super().write_dev(message)

except ModuleNotFoundError as err: 
    sys.stderr.write(str(err) + "\n") 
    pass 


try : 
    class LecroyHRO66 ( GPIB_Instrument ) : 
        import lecroyparser
        
        """
        Lecroy HRO 66 - some aquisition code inspired from 
        https://github.com/sca-research/Python-Acquisition-Script-for-Lecroy/blob/master/scope.py
        waveform parser:
        https://pypi.org/project/lecroyparser/
        last acquired wave accessible through self.wave.x self.wave.y
        """ 
        instruction_file = "instrufiles/LECROYHRO66.txt"
           
        
        def __init__( self, address, instrument_name) : 
            self.write_waveform = True
            self.report_function = np.average
            self.running_average_number = 0
            GPIB_Instrument.__init__(self, address, instrument_name) 
        
        def read_dev(self, message):
            """
            - waveform returned as bytes
            - everything else returned as a string 
            """
            if "waveform" in message.casefold():
                return self.vi.read_raw()
            else:
                return super().read_dev(message)
 
        def write_dev( self, message ) : 
            if "writewave" in message:
                m, v = re.split("\s+", message)
                if int(v) == 0:
                    self.write_waveform = False
                else :
                    self.write_waveform = True
            else:
                super().write_dev(message)
            
            
        def filter_function(self, wave) : 
            from scipy.ndimage import uniform_filter1d
            step = int(self.running_average_number/10)
            if step == 0: 
                step = 1 
            return uniform_filter1d( wave, self.running_average_number, mode="wrap")[::step]
 
        def last_wave(self) :
            if self.running_average_number > 0:
                return self.filter_function(self.wave.y)
            else:
                return self.wave.y
     
        def get(self, pname, args = [], wait = 0.005):
            if "mean" in pname:
                return str( np.mean( self.wave.y ) )
            elif "var" in pname:
                return str( np.var( self.wave.y ) )  
            
            
            reply = super().get(pname, args, wait)
            if "template" == pname:
                sys.stderr.write(reply + "\n")
                return ""
            elif "waveform" in pname:
                self.wave = self.lecroyparser.ScopeData(data=reply)
                if self.write_waveform:
                    if self.running_average_number == 0 :
                        return ";".join( map(str, self.wave.y) )
                    else:
                        return ";".join( map(str, self.filter_function( self.wave.y ) ) )
                else:
                    return str( self.report_function( self.wave.y) )
            elif "data" in pname:
                output = reply.split() 
                return ";".join( output[2:-1] )
            elif "coupling" in pname:
                return reply
            else:
                return reply.split()[-2]

except ModuleNotFoundError as err: 
    sys.stderr.write(str(err) + "\n") 
    pass 


import pydoc

class PyMeasure ( Instrument ) :
    def __init__( self, pyinstrument, instrument_name ) :
        self.vi = pyinstrument
        Instrument.__init__(self, instrument_name)   
        
    
    def device_present(self, name):
        try:
            if name in self.com :
                return True
            eval( "self.vi." + name)
            p = Parameter();
            p.read = name;
            p.write = name; 
            self.com[name] = p 
            return True
        except AttributeError:
            return False
        
    def write_dev(self, message): 
        try : 
            device, value = message.split(' ', 1)
        except ValueError : 
            device, value = message, ""

        if value != "":
            try: 
                exec( "self.vi." + device + " = float(value)")
            except ValueError:
                exec( "self.vi." + device + " = str(value)")
        else:
            eval("self.vi." + device)

    def write_for_read(self, message):
        pass 
    
    def read_dev(self, device) : 
        return str( eval( "self.vi." + device) )
    
    def documents(self) : 
        url = "https://pymeasure.readthedocs.io/en/latest/api/instruments/index.html"
        strhelp = pydoc.render_doc(self.vi, 
                                       "Help on %s \n see also: " + url
                                       , renderer=pydoc.plaintext)
        return strhelp.replace("|", "")
    
class Random_Walk( Instrument ) :
    import random 
    instruction_file = "instrufiles/random_walk.txt"

    def __init__( self, address, instrument_name) : 
        Instrument.__init__(self, instrument_name)
        self.sum = 0
    
    def get(self, pname, args = []):
        if pname == "rand" :
            return str(self.random.uniform(-1,1))
        if pname == "randsum" :
            self.sum += self.random.uniform(-1,1)
            return str(self.sum)

    def set(self, name, value, args = [ ]) :
        self.sum = value        

try:
    import serial
    # import io

    class SerialInstrument( Instrument ) : 
        def open_serial(self, address):
            """ 
            opens a serial connection - can be overloaded for non default baud rate,parity,... settings
            """
            return serial.Serial(address, timeout=0.3)
        
        
        def __init__( self, address, instrument_name) :
            try:
                self.vi = self.open_serial(address)
                #if self.ser.is_open: 
                #    self.ser.close()
                #    self.ser.open()
                # before we used an IO wrapper for conversion from string to bytes 
                # self.vi = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
                Instrument.__init__(self, instrument_name)
            except serial.serialutil.SerialException :
                self.vi = None
                sys.stderr.write("error opening COM %s port for %s\n" % (address, instrument_name))

        def write_dev( self, message) : 
            if self.vi:
                # self.vi.write(message + "\n")
                # self.vi.flush()
                self.vi.write( (message + "\n").encode("utf-8") )
                """ For Serial - request is made with write_dev, read_dev only listens reply """        
        def read_dev( self, message="" ) :
            if self.vi: 
                return self.vi.read_until().decode("utf-8").rstrip()
            else : 
                return "0"



    class TTI400( SerialInstrument ) : 
        instruction_file = "instrufiles/ttiCPX400.txt"
        def get(self, pname, args = []) : 
            return SerialInstrument.get(self, pname, args).split(" ")[-1]

        def set(self, name, value, args = [ ], wait = 0.005):
            if name == "temp" or name == "setp":
                value = int(1000*value)
            super().set(name, value, args, wait)


    class IPS( SerialInstrument ) :
        instruction_file = "instrufiles/ipsMercury.txt"
        def get(self, pname, args = []) :
            reply = SerialInstrument.get(self, pname, args).split(":")[-1]
            try :
                value = re.search('(.+)[a-zA-Z/]+', reply).group(1)
                float(value)
                return value
            except (ValueError, AttributeError) as e:
                return reply
            
        def set(self, name, value, args = [ ], wait = 0.005):
            super().set(name, value, args, wait)
            reply = self.read_dev("")
            if reply == "INVALID":
                sys.stderr.write("set %s to %s failed" % (name, value)) 


    class CryoMagnetSource( SerialInstrument ) :
        instruction_file = "instrufiles/cryogenics_psu.txt"
        def open_serial(self, address):        
            return serial.Serial(address,  baudrate=9600, timeout=1)

        def __init__( self, address, instrument_name, timeout = 1) :
            # CryoMagnetSource requries a longer timeout than default
            SerialInstrument.__init__(self, address, instrument_name)

        def set(self, name, value, args = [ ], wait = 0.3):
            super().set(name, value, args, wait)
            while self.vi.inWaiting() > 0:
                print(self.read_dev(""))

        def get(self, pname, args = []) :
            reply = SerialInstrument.get(self, pname, args)
            if pname == "field":
                try:
                    return re.search(': (.+) TESLA', reply).group(1)
                except AttributeError:
                    return reply
            else:
                return reply
            

    class Lakeshore350( SerialInstrument ):
        instruction_file = "instrufiles/lakeshore350.txt"    
        def open_serial(self, address):        
            return serial.Serial(address,  baudrate=57600, bytesize=7, parity='O', stopbits=1)

    class Lakeshore218( SerialInstrument ) :
        instruction_file = "instrufiles/lakeshore218.txt"
        def open_serial(self, address):        
            return serial.Serial(address,  baudrate=9600, bytesize=7, parity='O', stopbits=1)


            
except ModuleNotFoundError as err: 
    sys.stderr.write(str(err) + "\n") 
    pass 

try:
    from instrumental import instrument, list_instruments

    class ThorCCS( Instrument ) : 
        instruction_file = "instrufiles/thorspec.txt"


        def __init__( self, instrument_name) : 
            address = "thorlabs_ccs"
            self.last_scan = None
            self.average_scan = None 
            self.average_count = 0
            self.write_spec = True
            matching_instruments = list_instruments(module=address)
            if len(matching_instruments) == 1:
                self.vi = instrument(matching_instruments[0])
            else:
                sys.stderr.write("ThorCCS : no instruments found (or too many), %s\n" % (str(matching_instruments))) 
            Instrument.__init__(self, instrument_name)   

        def write_for_read(self, message):
            pass

        """
        here message just identifies the .vi function to be called, 
        last scan read is stored into self.last_scan
        """
        def read_dev( self, message ) : 
            if "time" in message:
                return str( self.vi.get_integration_time() )
            elif "spec" == message:
                self.vi.start_single_scan()
                while not self.vi.is_data_ready():
                    time.sleep(0.05) # waits 50ms
                self.last_scan = self.vi.get_scan_data()
                if self.write_spec : 
                    return ";".join( map ( str, self.last_scan ) )
                else:
                    return str(  self.last_scan.sum() )
            elif "avspec" == message:
                self.vi.start_single_scan()
                while not self.vi.is_data_ready():
                    time.sleep(0.05) # waits 50ms
                self.last_scan = self.vi.get_scan_data()

                if self.average_scan is None:
                    self.average_scan = self.last_scan
                    self.average_count = 1.
                else:
                    self.average_scan = np.add( self.average_scan, self.last_scan )
                    self.average_count += 1.               

                if self.write_spec : 
                    return ";".join( map ( str, self.average_scan / self.average_count ) )
                else:
                    return str(  self.last_scan.sum() )            
            elif "last_spectrum_sum" == message:
                if self.last_scan is None: return str(0)
                else: return str( self.last_scan.sum() )
            else:
                return ""

        """
        the beginning of the message allows to identify the vi. function to be called
        it is removed to keep only the parameter value 
        """
        def write_dev( self, message ) : 
            if "time" in message:
                self.vi.set_integration_time( message.replace("time", "") + " s" )
            elif "resetav" in message :
                self.average_scan = None
            elif "writespec" in message:
                m, v = re.split("\s+", message)
                if int(v) == 0:
                    self.write_spec = False
                else :
                    self.write_spec = True

        def wavelength_from_pixel(self, n): 
            return 500. + 0.153 * float(n) + 7e-6*float(n)*float(n)

        def wavelengths(self) :
            w = np.arange(0, len(self.last_scan))
            for n in range( len(w) ) : 
                w[n] = self.wavelength_from_pixel( n )
            return w


        def average_spec(self) : 
            return self.average_scan / self.average_count

        def last_spec(self): 
            return self.last_scan

except ModuleNotFoundError as err: 
    sys.stderr.write(str(err) + "\n") 
    pass 


class SocketInstrument ( Instrument ) : 
    import socket 
    
    def __init__( self, address, instrument_name, timeout = 1) : 
        try :
            self.vi = self.socket.socket()
            self.ip,self.port = address.split(":")
            self.vi.connect( (self.ip, int(self.port)) )
            self.vi.settimeout( timeout )
            
        except TimeoutError : 
            self.vi = None
            sys.stderr.write("error opening socket %s\n" % address)            
        Instrument.__init__(self, instrument_name)        
    
    def write_dev(self, message) :
        if self.vi : 
            self.vi.send(  bytes("%s\r\n" % message, encoding='utf-8') )
            
    def read_dev( self, message = "" ) :
        if self.vi: 
            return self.vi.recv(2048).decode(encoding='utf-8').rstrip().rstrip()
        else : 
            return "0"
        
    async def get_async(self, instru_parameter, arguments):
        message = self.get_message(instru_parameter, arguments)
        if not message : 
            return ""
        
        self.vi.setblocking(False)
        
        wait = 0.05
        write = False
        while not write:
            try:
                self.vi.send(  bytes("%s\r\n" % message, encoding='utf-8') )
                write = True
            except BlockingIOError:
                await asyncio.sleep(wait)
                
        read = False
        while not read:
            try:
                reply = self.vi.recv(2048).decode(encoding='utf-8').rstrip().rstrip()
                read = True
            except BlockingIOError:
                await asyncio.sleep(wait)
        self.vi.setblocking(True)
        return reply 
    
        # reader, writer = await asyncio.open_connection(self.ip, int(self.port))
        # welcome = await reader.read(2048)
        # writer.write(  bytes("%s\r\n" % message, encoding='utf-8') )
        # data = await reader.read(2048)

try:
    import usb.core
    import struct
    from usb.backend import libusb0  
    
    class JobinYvonMicroHR( Instrument ) : 
        """
        Jobin Yvon Micro HR Installation steps: 
        driver inspired from yaqd_core package
        1) install libusb driver from
        https://sourceforge.net/projects/libusb-win32/files/libusb-win32-releases/1.2.6.0/
        2) make libusb the driver for the spectrometer :
        using https://zadig.akeo.ie/
        and/or libusb-win32-devel-filter-1.2.6.0.exe
        """
        instruction_file = "instrufiles/jymicrohr.txt" 
        def __init__( self, instrument_name) : 
            self.JOBIN_YVON_ID_VENDOR = 0xC9B
            self.MICRO_HR_ID_PRODUCT = 0x100
            self.BM_REQUEST_TYPE = 0xB3
            self.B_REQUEST_OUT = 0x40
            self.B_REQUEST_IN = 0xC0
            
            backend = libusb0.get_backend()
            self.vi=usb.core.find(idVendor=self.JOBIN_YVON_ID_VENDOR, 
                                  idProduct=self.MICRO_HR_ID_PRODUCT, backend=backend)
            Instrument.__init__(self, instrument_name)

        def write_dev(self, message):
            message_parts = message.split()
            if len(message_parts) == 1:
                sys.stderr.write("intializing JY\n")
                self.vi.ctrl_transfer(self.B_REQUEST_OUT, self.BM_REQUEST_TYPE, wIndex=int(message_parts[0]))
            elif len(message_parts) == 3:
                if message_parts[1] == "int": 
                    self.vi.ctrl_transfer(self.B_REQUEST_OUT, self.BM_REQUEST_TYPE,
                                    wIndex=int(message_parts[0]), 
                                      data_or_wLength= struct.pack("<i", int(message_parts[2])) )
                elif message_parts[1] == "float":
                    self.vi.ctrl_transfer(self.B_REQUEST_OUT, self.BM_REQUEST_TYPE,
                                    wIndex=int(message_parts[0]), 
                                      data_or_wLength= struct.pack("<f", float(message_parts[2])) )                   
 
        def write_for_read(self, message):
            pass 

        def read_dev(self, message):
            message_parts = message.split()
            if len(message_parts) == 2:
                if message_parts[1] == "int": 
                    return str( struct.unpack("<i", self.vi.ctrl_transfer(self.B_REQUEST_IN,
                                      self.BM_REQUEST_TYPE,
                                      wIndex=int(message_parts[0]),
                                      data_or_wLength=4) )[0] )
                elif message_parts[1] == "float":
                    return "{:.3f}".format( struct.unpack("<f", self.vi.ctrl_transfer(self.B_REQUEST_IN,
                                      self.BM_REQUEST_TYPE,
                                      wIndex=int(message_parts[0]),
                                      data_or_wLength=4) )[0] )

        def set(self, name, value, args = [ ]) :
            """
            redefine set to sleep until spectrometer stops moving (blocking wait)
            """
            super().set(name, value, args)
            wait = 0.05
            wait_time = 0
            while self.get("busy") == '1' :
                time.sleep(wait) 
                wait_time += wait
                if wait_time > 60:
                    sys.write.stderr("JY spectrometer busy for more than %f seconds\n" % wait_time)
                    return 
                
                
except ModuleNotFoundError as err: 
    sys.stderr.write(str(err) + "\n") 
    pass 


class ServerSideInstrument( Instrument ): 
    import aiohttp
    import requests

    def __init__(self, instrument_name, instruction_dictionary, documents, port=8050) :
        self.docs = documents
        self.name = instrument_name
        self.com  = { } 
        self.url = "http://127.0.0.1:%d/serverside/run?run=" % port
        for interface, parameter in instruction_dictionary.items():
            self.com[interface] = Parameter(dictionary = parameter)
    
    def write_dev(self, message):
        sys.stderr.write("%s : is a server-side instrument, communication through get/set directly\n" % self.name)

    def read_dev(self, message = ""):
        sys.stderr.write("%s : is a server-side instrument, communication through get/set directly\n" % self.name)
        
    def get(self, instru_parameter, args = [], wait = 0.005) :
        """
        sequential get version - 
        async version seems to mix read order with multiple queries to same instrument on the server side
        """
        message = "get %s.%s %s" % (self.name, instru_parameter, " ".join(args))
        return self.requests.get(self.url + message).json()['reply']

    def set(self, instru_parameter, value, args = [ ], wait = 0.005) :
        message = "set %s.%s %s %s" % (self.name, instru_parameter, str(value), " ".join(args))
        self.requests.get(self.url + message)

def server_side_instruments( port = 8050 ):
    import requests
    req = requests.get("http://127.0.0.1:%d/serverside/experiment" % port, timeout=10).json()
    instrument_list = [ ]
    for name, instructions in req['instruments'].items() : 
        instrument_list.append( 
            ServerSideInstrument(instrument_name=name, 
                                 instruction_dictionary=instructions, 
                                 documents = req['documents'][name],
                                 port = port))
    return instrument_list
