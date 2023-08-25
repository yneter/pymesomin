import pymesomin as hal
import math
import os
import time 

magnet_error_filename =  os.path.abspath("C:\ProgramData\Anaconda3\Lib\site-packages\pymesomin\magneterrorfile.txt")


class MagnetCheckCryofast : 
    def error(self):
        return os.path.exists(magnet_error_filename)
    
    def reset_error(self):
        if os.path.exists(magnet_error_filename):
            os.remove(magnet_error_filename) 
        time.sleep(1)


class MagnetSafeCryofast : 
    def __init__(self):
        self.amiz = hal.AMIZ("192.168.10.31:7180", "amiZ")
        self.amix = hal.AMIX("192.168.10.33:7180", "amiX")
        self.amiy = hal.AMIY("192.168.10.32:7180", "amiY")
        self.cryo = hal.Bluefors("192.168.10.54:5001", "cryo")
        self.mag_error = False
        self.mag_locked = False
        self.update()
   

    def is_float(self, element):
        try:
            float(element)
            return True
        except ValueError:
            return False
    
    def format_float_str(self, float_str):
        if self.is_float(float_str): return  ("%.3f" % float(float_str)).rstrip('0').rstrip('.')
        else : return "read error"

    def message(self):
        bz_str = self.format_float_str(self.z_field)
        by_str = self.format_float_str(self.y_field)
        bx_str = self.format_float_str(self.x_field)
        mag_str = self.format_float_str(self.mag_temp)
        mc_str = self.format_float_str(self.mc_temp)
        message = "DL T: %s K , Magnet T: %s K , Bz:  %s Tesla , By: %s Tesla , Bx: %s Tesla , Magnet error: %s" % ( 
                 mc_str, mag_str, bz_str, by_str, bx_str, str(self.mag_error) )
        return message
        
    
    def field_active(self, field) : 
        return abs(float(field)) > 0.003
    
    def field_amp(self): 
        return math.sqrt( float(self.x_field)**2 +  float(self.y_field)**2 +  float(self.z_field)**2  )
    
    def field_amp_xy(self):
        return math.sqrt( float(self.x_field)**2 +  float(self.y_field)**2 )
    
    def detect_error(self) : 
        activex = self.field_active(self.x_field)
        activey = self.field_active(self.y_field)
        vector_mode = activex or activey
        
        field_amp = self.field_amp()

        if vector_mode and field_amp > 1.001:
            if not ( abs(float(self.z_field)) < 1.5 and self.field_amp_xy() < 0.42 ):
                self.mag_error = True
        
        try :
            if float(self.mag_temp) > 4.6 and field_amp > 0.003: 
                self.mag_error = True
        except ValueError:
            pass
            # self.mag_error = True

    def lock_magnet(self): 
        f = open(magnet_error_filename, 'w')
        f.write("Help !!!\n")
        f.write("X field " + self.x_field + "\n")
        f.write("Y field " + self.y_field + "\n")
        f.write("Z field " + self.z_field + "\n")
        f.write("Mag temperature " + self.mag_temp + "\n")
        f.write("MC temperature " + self.mc_temp + "\n")
        f.close()


    def update(self) :
        try:
            self.x_field = self.amix.get("field")
            self.y_field = self.amiy.get("field")
            self.z_field = self.amiz.get("field")
            self.mag_temp = self.cryo.get("mag.temp")
            self.mc_temp = self.cryo.get("mc.temp")
            self.detect_error()


            if self.mag_error and not self.mag_locked: 
                """
                set all fields to zero at max rate
                """
                self.amix.set("field", 0)
                self.amiy.set("field", 0)
                self.amiz.set("field", 0)
                self.amix.set("rate", 0.05)
                self.amiy.set("rate", 0.05)
                self.amiz.set("rate", 0.1)
                self.lock_magnet()  
                self.mag_locked = True

            if not os.path.exists(magnet_error_filename):
                self.mag_error = False
                self.mag_locked = False
        except AttributeError:
            pass


class MagnetTest : 
    def __init__(self):
        self.experiment = hal.Experiment( [ hal.cryofast.BlueforsSoftware("http://localhost:49099/values", "bf"),
                                            hal.SRSIM("GPIB::10", "sim"),
                                            hal.SR830("GPIB::4", "sr1")
                                           ], display=None ) 
        self.mag_error = True
        self.experiment.measure("bf.compressor")
    
    def message(self):
        return self.measurement
    
    def update(self): 
        self.measurement = "Pulse tube: " + self.experiment.get()