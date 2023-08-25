
import re 
import numpy as np 
import time
import os.path 
from datetime import datetime
import sys
import asyncio

import nest_asyncio
"""
nest_asyncio is needed to avoid collision with event loop from jupyter etc...
"""
nest_asyncio.apply()
from concurrent.futures import ThreadPoolExecutor

#
# matplotlib + multiprocessing based GUI 
# 
# import pymesomin.plotgui as plotgui
#

#
# plotly + dash client/server 
#
import pymesomin.plotclient as plotgui


class Parameter :
    def __init__(self, dictionary = { }):
        """
        Parameter : initialization to default values of all entries
        next loops over dictionary setting available class entries from the dictionary      
        """
        self.argmax = { }
        self.argmin = { }
        self.read = None
        self.write = None
        self.vmin = None
        self.vmax = None
        for key, value in dictionary.items():
            setattr(self, key, value)


class Instrument :
    instruction_file = None

    def __init__(self, instrument_name):
        """
        self.com is a dictionary of Parameters for each measurable parameter of the instrument
        """
        self.com = { }  
        self.name = instrument_name
        self.docs = "" 

        if self.instruction_file :
            sys.stderr.write("reading instructions from %s\n" % self.instruction_file)
            self.read_instructions(self.instruction_file)
    
    
    def _replace_args(self, order, args) :
        narg = order.count("$arg") 
        if narg > 0:            
            if not isinstance(args, list):
                args = [ args ]
            arglist = list( map(str, args) )
            if len(arglist) < narg:
                sys.stderr.write("not enough arguments for '%s' = %s\n" % (order, str(arglist)))
                return "" 
            for k in range(narg):
                order = order.replace("$arg"+ str(k+1), arglist[k])
        return order

    def _check_value_limit(self, name ,value) :
        if not str(value) : return True
        elif self.device(name).vmin is not None and (float(value) < self.device(name).vmin) : 
            sys.stderr.write("attempting to set %s.%s to %s < %f\n" % (self.name, name, str(value), self.device(name).vmin) )
            return False
        elif self.device(name).vmax is not None and (float(value) > self.device(name).vmax ) : 
            sys.stderr.write("attempting to set %s.%s to %s > %f\n" % (self.name, name, str(value), self.device(name).vmax) )
            return False
        return True
        
    def _check_arg_limit(self, pname, args):
        for n in range(len(args)):
            s = "$arg" + str(n+1)
            if s in self.com[pname].argmax: 
                if float(args[n]) > self.com[pname].argmax[s]:
                    sys.stderr.write("attempting to set %s.%s %s to %s > %f\n" % (self.name, pname, s, str(args[n]),  self.com[pname].argmax[s]) )                    
                    return False
                if float(args[n]) < self.com[pname].argmin[s]:
                    sys.stderr.write("attempting to set %s.%s %s to %s < %f\n" % (self.name, pname, s, str(args[n]),  self.com[pname].argmin[s]) )                    
                    return False
        return True

    def _read_argminmax(self, instruction) :
        m = re.search("(\$arg[0-9]+)\s*(\w+)", instruction)
        if m:
            return m.group(1), m.group(2)
        else :
            return None

    def device(self, name): return self.com[name.casefold()]

    def device_present(self, name):
        if name.casefold() not in self.com : 
            sys.stderr.write("device_present: unknown device %s.%s\n"  % (self.name, name) )
            return False
        return True        
    
    def write_dev(self, message):
        return None        
    
    def write_for_read(self, message):
        """
        write_for_read is called inside get() to send 'message' to instrument requesting a value 
        for some devices all the read/write occurs in read_dev in which case 
        write_for_read can be set do to do nothing
        """
        return self.write_dev(message)
    

    def read_dev(self, message):
        """
        read_dev reads response from instrument
        'message' is the string to requests a reading from device 
        used when the write and read sequence is packed in a single function call
        can be set to default message="" in devices where message is sent through write_for_read
        """ 
        return ""
    
    def get_message(self, name, args):
        """
        returns the message sent to instrument for read of interface name
        modify to be used in set also ? 
        """
        if not self.device_present(name) or self.device(name).read is None: 
            sys.stderr.write("no read instruction for %s.%s\n" % (self.name, name) )
            return ""
        if not self._check_arg_limit(name, args): 
            return ""

        order_str = self._replace_args(self.device(name).read, args)
        return order_str

    
    def get(self, name, args = [ ], wait = 0.005) :
        """
        get name value returns- answers form instruments as a concatenated string with ";" spacer 
        can return binary output if reply is binary 
        the wait argument is important for instruments containing a sequence of instructions
        """

        order_str = self.get_message(name, args)
        if not order_str: return ""

        reply=[]
        if "|" in order_str: 
            """
            for read instructions with split character | - we need to know when to read  
            we read only after instructions containing ?
            """
            for order in order_str.split("|"):
                self.write_for_read(order)
                time.sleep(wait)
                if "?" in order:
                    reply.append( self.read_dev(order) )
        else:
            """
            some read requests contain no ? - always read if there is no split character |  
            """
            self.write_for_read(order_str)
            time.sleep(wait)
            reply.append( self.read_dev(order_str) )
        if len(reply) == 1 and type( reply[0] ) is not str:
            return reply[0]
        else:
            return ";".join( reply )

    def set(self, name, value, args = [ ], wait = 0.005) :
        """
        set name to value with args - the wait argument is important for instruments containing a sequence of instructions
        """
        if not self.device_present(name) or self.device(name).write is None:
            sys.stderr.write("no write instruction for %s.%s\n" % (self.name, name) )
            return
       
        if not self._check_value_limit(name, value) or not self._check_arg_limit(name, args): 
            return 
        
        order_str = self._replace_args(self.device(name).write, args)
        for order in order_str.split("|"):
            if "$data" in order and not str(value): 
                sys.write.stderr("missing value for set %s.%s" % (self.name, name))
            elif "$data" in order:
                self.write_dev( order.replace("$data", str(value)) )      
            elif "$data" in order_str: # for SR SIM
                self.write_dev(order)
            else: # for PyMeasure
                self.write_dev( order + " " + str(value) )
            time.sleep(wait)

    def read_instructions(self, filename):
        try : 
            f = open(os.path.join(os.path.dirname(__file__), filename), 'r')
            for line in f :    
                if re.match("%", line) or re.match("#", line) or re.match("\s+", line) :
                    continue
                try :
                    name, ptype, instruction  = re.split("\s+", line.rstrip(), 2)
                    pname = name.casefold()
                    if pname not in self.com: 
                        self.com[pname] = Parameter() 
                    if ptype.casefold() == "I".casefold():
                        self.write_dev(instruction)
                        if "?" in instruction: self.read_dev(instruction)
                    elif ptype.casefold() == "W".casefold():
                        self.com[pname].write = instruction 
                    elif ptype.casefold() == "R".casefold():
                        self.com[pname].read = instruction 
                    elif ptype.casefold() == "min".casefold():
                        m = self._read_argminmax(instruction)
                        if m: self.com[pname].argmin[m[0]] = float( m[1] )
                        else: self.com[pname].vmin = float(instruction)
                    elif ptype.casefold() == "max".casefold():
                        m = self._read_argminmax(instruction)
                        if m: self.com[pname].argmax[m[0]] = float( m[1] )
                        else: self.com[pname].vmax = float(instruction) 
                except ValueError:
                    sys.stderr.write("read_instructions from %s : error processing line %s\n" % (filename, line))
                    pass
        except IOError : 
            sys.stderr.write("failed to read instructions from %s \n" % filename )   

    def instructions(self):
        for dev in self.com:
            dread = (self.com[dev].read is not None)
            dwrite = (self.com[dev].write is not None)
            print("%s.%s R=%s W=%s" % (self.name, dev, str(dread), str(dwrite)))

    def instrument_as_dictionary(self):
        instru_dictionary = { }
        for parameter in self.com:
            instru_dictionary[parameter] = vars( self.com[parameter] )
        return instru_dictionary

    def documents(self) :
        if not self.instruction_file:
            return self.docs
        """
        generate documentation from self.instruction_file when available
        """
        L = [ ]
        with open(os.path.join(os.path.dirname(__file__), self.instruction_file), 'r') as file:
            for line in file:
                if re.match("%", line) or re.match("#", line) :
                    L.append( "####" + line.replace("%", "").replace("#", "") )
                else:
                    L.append( "- %s.%s" % (self.name, line) )
        return "".join(L)
            
class Experiment :    
    def __init__(self, instru_list, display=True) :
        self._instru = { "hal" : None }
        self._devices = [ ]
        self._log_devices = [ ] 
        self.path = None
        self._log_instru_file = None
        self.test_mode = False
        self.append_to_file = True
        if display:
            self.Display = plotgui.DisplayPlot
        else:
            self.Display = None
        self._docs = { }
        self._add_instru(instru_list)
        self.comment = "" 
        
    def _add_instru(self, instru_list) :
        for u in instru_list:
            if u.name in self._instru:
                sys.stderr.write("instrument %s already loaded - skip\n" % u.name)
            else:
                self._instru[u.name] = u       
                self._docs[u.name] = u.documents()
        if self.Display is not None:
            pl = self.Display()
            pl.documents( self._docs ) 

    def sleep(self, time_in_seconds):
        if not self.test_mode:
            time.sleep(time_in_seconds)
            
    def instrument(self, instrument_name) : 
        return self._instru[instrument_name]
    
    def instruments(self):
        return list( self._instru.keys() )
    
    def documents(self, instrument_name) : print( self._docs[instrument_name] )

    def instruments_as_dictionary(self) : 
        """
        returns available instruments in experiment
        """
        instruments_summary = { }
        for instru in self._instru:
            try:
                instruments_summary[instru] = self._instru[instru].instrument_as_dictionary() 
            except AttributeError:
                pass
        return instruments_summary

    def documents_as_dictionary(self) :
        """
        returns documentations for all instruments in the experiment as a dictionary 
        """
        return self._docs

    def _instrument_here(self, name) : return name in self._instru
    
    def _split_instrument_and_parameter(self, fullname: str) : 
        if "." not in fullname:
            sys.stderr.write("device : %s specify parameter - for example: sr1.freq\n" % fullname)
            return None, None
        iname, pname = fullname.split(".", 1)
        if "hal" == iname:
            return iname, pname
        if not self._instrument_here(iname):
            sys.stderr.write("device_list : instrument %s not present\n" % iname)
            return None, None
        if not self.instrument(iname).device_present(pname):
            sys.stderr.write("device_list : unknown device %s\n" % fullname)
            return None, None
        else :
            return iname, pname
        
    def _device_list_from_str(self, device_list_as_string) :
        mstr = device_list_as_string
        dev = [ ]
        dev_str = re.split("\s*,\s*", mstr)
        for d_str in dev_str:
            l = re.split("\s+", d_str)
            iname, pname = self._split_instrument_and_parameter(l[0])
            if iname is not None:
                if len(l) > 1 and l[1] != "": 
                    dev.append( [ iname, pname ] + l[1:] )
                else :
                    dev.append( [ iname, pname ] )
        return dev
    
    def _device_list(self, devices=None) :
        if devices is None: 
            return self._devices
        elif isinstance(devices, str):
            return self._device_list_from_str(devices)
        elif isinstance(devices, list):
            return devices
        else:
            sys.stderr.write("unrecognized device list format %s" % str(devices))
            return [ ]

    def _device_to_str(self, x) :
        return "%s.%s %s" % (x[0], x[1], "" if x[2:] == [] else str(x[2:]))

    def _device_list_of_str(self) : 
        return list( map( self._device_to_str, self._device_list() ) )

    def _device_summary(self, dev = None) :
        if not dev :
            dev = self._devices
        if not isinstance(dev, list): 
            return str(dev)
        elif not dev:
            return "No devices to measure in: call .measure('sr1.x', 'sr1.y')\n"
        elif isinstance( dev[0], list ):
            return ", ".join(map(self._device_to_str, dev))
        else :
            return self._device_to_str(dev)

    def _writef(self, f, s, print_to_screen = False) :
        f.write(s)
        f.flush()
        if print_to_screen:
            print(s.strip())


    def get_log(self) -> str :
        now = datetime.now()
        log_list = [ ]
        log_list.append("# when %s \n" % now.strftime("%d/%m/%Y %H:%M"))
        log_measurement = self.get_vec(self._log_devices, write_log=False)

        for dev, measurement_output in zip(self._log_devices, log_measurement):
            log_list.append("# %s.%s = %s\n" % (dev[0], dev[1], measurement_output))
            
        return ''.join( log_list )

    def _openfile(self, outfile):
        if self.path:
            outfile = os.path.join(self.path, outfile)
        if not self.append_to_file : 
            pre, end = outfile.split(".", 1)
            while os.path.exists(outfile) : 
                now = datetime.now()
                d1 = now.strftime("_%d_%m_%Y_H%H_M%M_S%S")
                outfile = "%s%s.%s" % (pre, d1, end)

        if os.path.exists(outfile) : 
            file = open(outfile, "a")
            file.write("\n")
        else:
            file = open(outfile, "w")
        return file
    
    def _measurement_to_float_vec(self, expvalues ):
        mvec = [ ]
        for vp in expvalues: 
            try: 
                mvec.append( float(vp) )
            except ValueError:
                mvec.append( 0 )
        return mvec

    def _log_enabled(self, enabled = True) :
        return enabled and (not self.test_mode) and self._log_instru_file



    def measure(self, devices_to_measure = None) : 
        """
        argument: devices_to_measure as string for example "sr1.x, sr1.y, sr2.x, sr2.y"
        no change to measured devices when no argument is provided - 
        returns currently measured devices as string 
        """
        if devices_to_measure is not None:      
            if self._log_instru_file:
                self._writef(self._log_instru_file, "measure %s \n" % devices_to_measure)
            self._devices = self._device_list(devices_to_measure)
        return self._device_summary()

    def log(self, devices_to_log = None):
        """
        argument: devices_to_log as string for example "sr1.freq, sr1.sensitivity"
        no change to measured devices when no argument is provided - 
        returns currently measured logged as string 
        """
        if devices_to_log is not None:        
            if self._log_instru_file:
                self._writef(self._log_instru_file, "log %s \n" % devices_to_log)
            self._log_devices = self._device_list(devices_to_log)    
        return self._device_summary(devices_to_log)
        
    def log_instructions_end(self):
        if self._log_instru_file: self._log_instru_file.close()
        self._log_instru_file = None
        
    def log_instructions(self, logfile):
        self._log_instru_file = self._openfile(logfile)
       
    def value_from_instru_ready(self, instrument: str, parameter: str , value: str ) :
        """
        called when instrument.parameter is available (in both sequential and asynchroneous versions)
        overloading to allow safety checks on the values - pass by default
        """
        pass
        
    def get_from_instru(self, instru_name, var_name, arguments = [ ]) :
        """
        sequential version of get_from_instru - get_from_instru_async provides the asynchrnous version
        if instru_name is 'hal' evaluates self.var_name and returns as a string 
        """
        if "hal" == instru_name:
            try: 
                return str( eval( "self." + var_name ) )
            except ValueError:
                sys.stderr.write("failed to evaluate self."  + var_name + "\n")
                return ""
        reply = self.instrument(instru_name).get(var_name, arguments)
        self.value_from_instru_ready(instru_name, var_name, reply) 
        return reply
    
    async def get_from_instru_async(self, instru_name, var_name, arguments):
        """
        asychronous version of get_from_instru
        """
        reply = await self.instrument(instru_name).get_async(var_name, arguments)
        self.value_from_instru_ready( instru_name, var_name, reply )
        return reply
    
    async def get_vec_async(self, list_of_arguments_for_get_async) :
        tasks = [ ]
        for arguments_for_get_async in list_of_arguments_for_get_async:
            tasks.append( self.get_from_instru_async( *arguments_for_get_async ) )
        result = await asyncio.gather( *tasks ) 
        return result
    
    
    def get_vec_seq(self, list_of_arguments_for_get) :
        results = [] 
        for arguments_for_get in list_of_arguments_for_get:
            results.append( self.get_from_instru(*arguments_for_get) )
        return results 
    
    async def get_vec_task_manager(self, seq_arguments, async_arguments, use_async_version):
        async_results = await self.get_vec_async(async_arguments)
        
        with ThreadPoolExecutor() as thread_pool:
            seq_results = await asyncio.get_event_loop().run_in_executor(
                thread_pool, self.get_vec_seq, seq_arguments
            )
            
        async_count = 0
        seq_count = 0
        all_results = []
        for n in range( len(use_async_version) ) : 
            if use_async_version[n]: 
                all_results.append( async_results[async_count] )
                async_count += 1
            else:
                all_results.append( seq_results[seq_count] )
                seq_count += 1
        return all_results

        
    def get_vec(self, command=None, write_log=True, run_seq=False):
        devices = self._device_list(command)
        if self._log_enabled(write_log): 
            self._writef(self._log_instru_file, "get_vec %s\n" % self._device_summary(devices)) 
        if self.test_mode : 
            for dev in devices:
                if not self.instrument(dev[0]).device_present(dev[1]):
                    sys.stderr.write("get_vec : %s.%s missing\n" % (dev[0], dev[1]))
            return [ ]
        
        elif run_seq: 
            response = [ ] 
            for dev in devices: 
                iname, pname, args = dev[0], dev[1], dev[2:]  
                value =  self.get_from_instru(iname, pname, args)
                response.append ( value )
            return response
        
        else:
            seq_arguments = [ ]
            async_arguments = [ ]
            use_async_version = [ ]
            for dev in devices: 
                iname, pname, args = dev[0], dev[1], dev[2:]

                if hasattr( self.instrument(iname), "get_async" ):
                    async_arguments.append( [iname, pname, args] )     
                    use_async_version.append(True)
                else:
                    seq_arguments.append( [iname, pname, args] )
                    use_async_version.append(False)
                                             
            result = asyncio.run(
                self.get_vec_task_manager(seq_arguments, async_arguments, use_async_version)
                )
            return result
            
    
    def get(self, command = None, write_log = True) :
        if self._log_enabled(write_log): 
            self._writef(self._log_instru_file, "get %s\n" % str(command)) 
        return "  ".join( self.get_vec(command, write_log = False) ) 
    

    def set_instru(self, instru_name, var_name, value, arguments = [ ]) :
        """
        encapsulates request to instruments - to allow overloading when extra safety checks are needed 
        """
        self.instrument(instru_name).set(var_name, value, arguments)

    def _nothing_to_measure(self):
        if not self._device_list():
            sys.stderr.write("no instruments to measure\n")
            sys.stderr.write("to add instruments use\n")
            sys.stderr.write("(self).measure(\"sr1.x, sr1.y\")\n")
            sys.stderr.write("to log instruments before measurement sequence\n")
            sys.stderr.write("(self).log(\"sr1.freq, sr1.sens\")\n")
            return True
        else:
            return False

    def set(self, command, value = "", write_log = True) :
        if self._log_enabled(write_log): 
            self._writef(self._log_instru_file, "set %s %s\n" % (str(command), str(value) )) 
        devices = self._device_list(command)
        if self.test_mode : return
        for dev in devices:
            iname, pname, args = dev[0], dev[1], dev[2:]
            if args : # if there is an argument args[0] is the value for set 
                self.set_instru(iname, pname, args[0], args[1:])
            else:
                self.set_instru(iname, pname, value)

    def instructions(self, name) : self.instrument(name).instructions()
               
    def move(self, name, end_value, rate, nsteps = 100, write_log = True, display=False):
        instruction_str = "move %s %s %s" % (str(name), str(end_value), str(rate))
        if self._log_enabled(write_log):
            self._writef(self._log_instru_file, instruction_str + "\n" )
        if self.test_mode :
            self.get(name)  # attempts a get in test mode to check if device is here
            return
        if self.Display is None:
            # if no display available - disable display
            display=False


        start_value = self.get(name)
        step = (float(end_value) - float(start_value)) / float(nsteps)
        if (abs(step) == 0): return  # we are there already, exit
        dt = abs(step / float(rate))
        if display: 
            pl = self.Display()
            pl.plot( [ "time", name, "rate" ], instruction_str )
        
        c = 0
        start_time = time.time()
        for v in np.arange(float(start_value), float(end_value)+step, step):
            if c % 2 == 0:
                sys.stdout.write("move %s: %f -> %f -> %f    \r" 
                         % (name, float(start_value), v, float(end_value)))
            self.set(name, v)
            time.sleep(dt)
            if display:
                t = time.time() - start_time
                pl.replot([t, v, (v-float(start_value))/float(t)])
            c += 1
        sys.stdout.write("\n")
        if display:
            pl.close()
            
    
    def sweep(self, name : str, vinit : float, vend : float, npoints : int, outfile: str, 
              wait = 0.2, rate = None, write_log=True, display=True, reset_plot=True) : 
        instruction =  "sweep %s %s %s %d %s %s" % (str(name), str(vinit), str(vend), int(npoints), str(wait), str(outfile) )
        if write_log and self._log_instru_file:
            self._writef(self._log_instru_file, instruction, print_to_screen = reset_plot )
            
        if self._nothing_to_measure() :
            return

        iname, pname = self._split_instrument_and_parameter(name)
        if iname is None:
            return 

        if self.test_mode : 
            # attempts a false get to check if devices are here/have correct read/write 
            self.get(name)
            self.get_vec(write_log = False)
            return 

        if self.Display is None:
            # if no display available - disable display
            display=False

        if vinit is not None:
            if not rate : 
                rate = 10. * (float(vinit) - float(vend)) / ( float(npoints) * wait )
            self.move(name, vinit, rate, write_log = False)
        else:
            try:
                vinit = float( self.get(name) ) 
            except ValueError: 
                sys.stderr.write("could not read initial value for {}\n".format( name ))
                return 


        f = self._openfile(outfile)
        try : 
            log_values = self.get_log() 
            self._writef(f, "# %s \n" % (instruction), print_to_screen=reset_plot )
            self._writef(f, "# measuring %s with wait %g\n" % (self._device_summary(), wait) )
            self._writef(f, log_values)

    
            if display:
                pl = self.Display()
                if reset_plot:
                    pl.plot( [ name ] +  self._device_list_of_str(), instruction )
                pl.log_values( log_values )
    
            step=(vend - vinit)/float(npoints)
            for v in np.arange(vinit, vend + step, step):
                self.set(name, v, write_log = False)
                time.sleep(wait)
                expvalues = self.get_vec(write_log = False)
                expstr = "  ".join(expvalues)
                self._writef(f, "%s %s \n" % (str(v), expstr) )
                f.flush()
                if display:
                    pl.replot([ float(v) ] +  self._measurement_to_float_vec(expvalues) ,
                              float(v - vinit)/float(vend - vinit))
                    if pl.promalpt :
                        self._process_prompt(pl)

        finally :
            f.close()
            if display: pl.close()
            
    def stop_record(self) : 
        return True 
            
    def record_eta(self) -> float:
        return 0.5


    def _process_prompt(self, pl):
        print("prompt received")
        print(pl.prompt)
        reply = self.run(pl.prompt, set_and_get_only=True)
        print("prompt reply")
        print(reply)
        pl.prompt_reply(reply)
    
    def record(self, wait, total_time, outfile=None, write_log=True, display=True, reset_plot = True, record_callback = None) : 
        instruction = "record %s %s %s" % (str(wait), str(total_time), str(outfile))
        if self._log_enabled(write_log):
            self._writef(self._log_instru_file, instruction )            
        if self.test_mode : 
            # attempts a false get to check if devices are here
            self.get_vec(write_log = False)
            return
        if self._nothing_to_measure() :
            return
        if self.Display is None:
            # if no display available - disable display
            display=False

        try:
            log_values = self.get_log()
            if outfile:
                f = self._openfile(outfile)
                self._writef(f, "# %s \n" % (instruction), print_to_screen=reset_plot) 
                self._writef(f, "# measuring %s with wait %g\n" % (self._device_summary(), wait) )
                self._writef(f, log_values)
                
                
            start_time = time.time()
            t = time.time() - start_time
            if display:
                pl = self.Display()
                if reset_plot:
                    pl.plot( [ "time" ] +  self._device_list_of_str(), instruction )
                pl.log_values(log_values)
    
            while (total_time is not None and t < total_time) or ( not self.stop_record() ):
                expvalues = self.get_vec(write_log=False)
                expstr = "  ".join(expvalues)
                if outfile:
                    self._writef(f, "%g %s \n" % (t, expstr ) )
                    f.flush()
                if display:
                    if not total_time : advance_fraction = self.record_eta()
                    else : advance_fraction = float(t)/float(total_time)
                    pl.replot( [ t ] +  self._measurement_to_float_vec(expvalues) , advance_fraction )
                    if pl.prompt :
                        self._process_prompt(pl)
                        
                if record_callback is not None:
                    record_callback(self, expvalues)
                time.sleep(wait)
                t = time.time() - start_time
#        except plotgui.STOP_HAL as stoped: 
#            sys.stderr.write(str(stoped)+ "\n")
        finally :
            if display: pl.close()
            if outfile: f.close()

    def run(self, batch, write_log = True, set_and_get_only = False) :
        """
        runs a batch text similar to the old HAL labview syntax, 
        examples: 
        run("get bf.compressor,sr1.dac 1,sr1.freq")
        run("set sr1.dac 0.03 1")
        run("recprd 1 1000 wait.dat")
        """
        if write_log and self._log_instru_file:
            self._writef(self._log_instru_file, batch)
        reply = [] 
        for line in batch.splitlines():
            first_two_words = re.split("\s+", line.lstrip(), 1)
            if len(first_two_words) == 2:
                command, rest = first_two_words
            else :
                continue
            
            if command.casefold() == "get": reply.append ( self.get(rest) )
            elif command.casefold() == "set": self.set(rest)
            
            if set_and_get_only:
                continue
            
            args = re.split("\s+", rest.lstrip())  
            args = list( filter(None, args) ) # remove empty strings 
            if command.casefold() == "move" : 
                if len(args) == 3:
                    self.move(args[0], args[1], args[2])
                else:
                    sys.stderr.write("move : wrong number of arguments %s" % line)
            elif command.casefold() == "record" : 
                if len(args) == 3:
                    self.record(float(args[0]), float(args[1]), args[2])
                else:
                    sys.stderr.write("record : wrong number of arguments %s" % line)
            elif command.casefold() == "sweep" : 
                 if len(args) == 5:
                    self.sweep(args[0], float(args[1]), float(args[2]), int(args[3]), args[4])
                 else:
                    sys.stderr.write("sweep : wrong number of arguments %s" % line)
        return "\n".join(reply)              
        
    def show(self, xdata, ydata = None):
        if type(xdata) is str:
            xvec = map(float, xdata.split(";")) 
        else:
            xvec = xdata
        if type(ydata) is str:
            yvec = map(float, ydata.split(";")) 
        else:
            yvec = ydata
        if self.Display is None:
            sys.stderr.write("show - no display available\n")
            return
        pl = self.Display()
        if yvec is not None:
            pl.other_plot_yx(yvec, xvec)
        else:
            pl.other_plot_yx(xvec, None)
