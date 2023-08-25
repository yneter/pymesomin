import requests
import time
import math
import threading 
import sys

    
class DisplayPlot:
    """
    sends data to plotting server, 
    if self.sequential = False
       launching a new thread (non blocking) 
    or sequentially     
    """
    def __init__(self, address = None):
        if address is not None:
            self.address = address 
        else :
            self.address = "http://127.0.0.1:8050/"
        self.server_error = False    
        self.timeout = 15
        self.stop = False
        self.pause = False
        self.running = False
        self.lock = threading.Lock()
        self.talking_to_server = False
        self.sequential = False
        self.prompt = ""
        
    def make_request(self, url, params=None):
        return requests.get(url, timeout=self.timeout, params=params).json()

    def update_server(self, newdata, progress):
        """
        skips requests when self.talking_to_server is true 
        this skips communication requests with server which are faster than the communication rate 
        """
        if self.server_error : 
            return 

        with self.lock:
            if self.talking_to_server:                
                return
            else:
                self.talking_to_server = True
        try:        
            if self.make_request(self.address + "stop")['stop']:
                self.stop = True
            self.pause = self.make_request(self.address + "paused")['paused']
            self.prompt = self.make_request(self.address + "prompt")['prompt']
    
            url_name = self.address + "update"
            request_param = {
                'values' : ' '.join(map(str, newdata))
            }
            if progress is not None:
                request_param.update( {
                    'progress' : str(progress),
                } )                
            self.make_request(url_name, params=request_param)    
        except requests.exceptions.ConnectionError as err:
            self.server_error = True
            print(str(err))
            return 

        self.talking_to_server = False
            
    def replot(self, newdata, progress = None):
        if self.sequential: 
            self.update_server(newdata, progress)
        else:
            threading.Thread(target=self.update_server, args=( newdata, progress ) ).start()        
        if self.stop:            
            sys.stderr.write("STOP button pressed\n")
            # sys.exit("STOP button pressed\n")
            sys.exit()
        while self.pause:
            if self.make_request(self.address + "paused")['paused']:
                time.sleep(0.3)
            else:
                self.pause = False
            
    def plot(self, labels, title) :  
        try :
            url_name = self.address + "start"
            request_param = {
                'measuring' : ' '.join(labels),
                'title' : title
            }
            requests.get(url_name, params=request_param, timeout=self.timeout)
            self.server_error = False
        except requests.exceptions.ConnectionError as err:
            self.server_error = True
            print(str(err))            

    def update_server_plot_yx(self, ydata, xdata):
        with self.lock:
            if self.talking_to_server:                
                return
            else:
                self.talking_to_server = True
                
        url_name = self.address + "otherplots"
        request_param = {
            'y' : ' '.join(map(str, ydata))
        }
        if xdata is not None:
            request_param['x'] = ' '.join(map(str, xdata))
        self.make_request(url_name, params=request_param)
        self.talking_to_server = False
            
    def prompt_reply(self, reply) :
        with self.lock:
            while self.talking_to_server:                
                time.sleep(1)
            self.talking_to_server = True
        url_name = self.address + "promptreply"
        request_param = {
            'reply' : reply
        }
        self.make_request(url_name, params=request_param)
        self.talking_to_server = False
        
    def other_plot_yx(self, ydata, xdata = None) : 
        if self.sequential:
            self.update_server_plot_yx(ydata, xdata)
        else:
            threading.Thread(target=self.update_server_plot_yx, args=( ydata, xdata ) ).start()                    

            
    def send_string(self, address_string : str, instrument_doc : str) :
        try :
            url_name = self.address + address_string
            request_param = instrument_doc
            requests.get(url_name, params=request_param, timeout=self.timeout)
            self.server_error = False
        except requests.exceptions.ConnectionError as err:
            self.server_error = True
            print(str(err))            
                
    def documents(self, instrument_doc) :
        self.send_string("instruments", instrument_doc)
          
    def log_values(self, log_values) :
        self.send_string("logvalues", { "log_values":  log_values } )
         
    def close(self):
        pass


    
def example_task():
    pl = DisplayPlot("http://127.0.0.1:8050/")
    pl.plot( ["time", "sr1.x", "sr1.y"], "sweep cos " )
    t0 = time.time() - 1.   
    for ii in range(3000):
        t = time.time()    
        v =  [ t - t0, math.cos(t), math.sin(t) ] 
        pl.replot(v, float(ii)/float(3000))
        print(v)
        time.sleep(0.1)
    pl.plot( ["time", "sr2.x"], "sin" )
    for ii in range(3000):
        t = time.time()
        v =  [ t - t0, math.sin(t) ] 
        pl.replot(v)
        print(v)
        time.sleep(0.2)
        
if __name__ == '__main__':
    example_task()
