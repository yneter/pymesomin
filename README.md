# Introduction

This is a python code to interact and automatize measurements on a collection of instruments.
We have used it mainly on cryogenic magnets (commericial systems from Bluefors/Cryogenics limited
and home made systems). This is the result of an evolution of Labview/python codes developed in the Meso group at Laboratoire de physique des solides 
( https://equipes2.lps.u-psud.fr/meso/ )

Particularities of this code are the following : 

**Minimal coding requirements to add new instruments** 

A typical class defining a GPIB instrument just gives a text configuration files with the SCPI instructions:

```
class SR830( GPIB_Instrument ) : instruction_file = "instrufiles/sr830.txt" 
```
the file sr830.txt contains the GPIB read/write commands from the Stanford research SR830 lockin-detection:
```
% oscillator frequency
freq	R	FREQ?
freq	W	FREQ $data
```

similar classes are available for instrument communicating through Serial/Socket interfaces. It is also possible to import instruments from other libraries (pyMeasure, ...)

**Scripted experiment control** 

The experiment is controlled by python scripts which are sequences of standard instructions, 

- get and set values from instruments (output voltage, frequency, ...) 
- moving some parameter smoothly at a fixed rate to a given value 
- record a set of parameter as function of time 
- sweep recording a set of parameter as function a control value (gate voltage etc...)

these elementary building blocks can be extended to provide additional features: 
- record_magnet_ramp : records values from a list of instruments while the magnetic field is ramped by 
the magnet power supply 

the control script works as a single process but can use asynchronous calls to reduce intput/output delays when communicating with several instruments 

**Display of experimental traces through an independent plotting server** 

Visual control of the state of the experiment is provided through a dash/plotly sever which shows the measured traces, can enforce some safety checks on the system, and visualization of key parameters (magnetic fields/temperatures) 

The communication between the control scirpt and the plot server allows to :
- change some parameters from the server side when a long measurement sequence is running without having to interrupt it 
- load and control some instruments from the server side allowing to communicate with them from several client scripts, this is specially useful to share communication with serial port instruments which can be opened by a single program at the same time.


# Examples interface on a Cryogenics Limited system

**Starting the plot-server**
```
import pymesomin.plotserver as hal_server
hal_server.run_server(magnet_safety=False)
```
The plot-server is accessible through: http://127.0.0.1:8050/


```
import pymesomin as hal
from pymeasure.instruments.keithley import Keithley6221
from pymeasure.instruments.keithley import Keithley2000
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.srs import SR830 

hexp = hal.Experiment( [ hal.Lakeshore350("COM5", "Ls350"),
                         hal.Lakeshore335("COM4", "Ls335"),
                         hal.Lakeshore218("COM3", "Ls218"),
                         hal.CryoMagnetSource("COM6", "cmag"),
                         hal.PyMeasure( Keithley2400("GPIB::24"), "K2"  ), 
                         hal.PyMeasure( Keithley6221("GPIB::20"), "K6"  ), 
                         hal.Keithley2182("GPIB::8", "nV"),
                         hal.PyMeasure( SR830("GPIB::5"), "sr1" )
                       ] 
                     )
```

Add in this list the intruments to use, with their GPIB or port COM numbers
To add a new instrument: if in pymeasure (look in doc) just import it
if not, you need to write the useful instructions in a txt file dedicated to the instrument placed in
C:\Data\Anaconda\Lib\site-packages\pymesomin\instrufiles

Each line in the instrufiles corresponds to an instruction, with structure:
name you choose for the parameter \tab R or W (for Read or Write) \tab the SCPI instruction found in the instrument manual

it's ok if: No module named 'lecroyparser'; No module named 'usb'
if problem here start NImax, scan instruments connected through gpib, close NImax, retry

list the parameters you want to record when you do a measurement
```
hexp.measure("nV.sense, sr1.x, sr1.y, cmag.field, Ls350.Tvti, Ls350.Tsample")
```

This gives a list of parameters to measure once at the beginning of a record/sweep instruction 
```
hexp.log("Ls350.Tvti, Ls350.Tsample, Ls218.T1stage, \
Ls218.T2stage, Ls218.TpMag, Ls218.TmMag, Ls218.THe4pot, \
Ls335.Tmainsorb, Ls335.Tminisorb, cmag.rate, sr1.frequency, sr1.time_constant")
```

Temperature: 
```
hexp.get("Ls350.Tvti, Ls350.Tsample")
hexp.set("Ls350.Tvti" , 1.5)
hexp.set("Ls350.heater_vti_off")
hexp.set("Ls350.heater_sample_on")
# examples of T reading and control - if He3 probe there are two heaters,
# one for the sample, one for the VTI - if He4 probe only one heater on VTI
# list of possible T readings names in log above

hexp.instrument("Ls350").write_dev("RANGE 2,4") 
# this set the range of the heater of channel 2 on LS350 (sample heater in He3 probe) to range 4
# range 0=heater off; ranges 1 to 5 heater max power increases
```

```
hexp.set("Ls335.heater_mainsorb_off")
hexp.set("Ls335.ramp_minisorb", 300)
hexp.set("Ls335.Tminisorb", 320)
hexp.set("Ls335.heater_minisorb_on")
hexp.set("Ls335.Tminisorb", 327)
# Minisorb desorption at room temperature
# max T minisorb=330 K - if T>330 K heater shuts down and thermometer reads Tover. 
#It's better to reach 330 slowly 
hexp.set("Ls335.heater_mainsorb_high")
# mainsorb range 0 = off, range 1 to 3: low, medium,high
hexp.set("Ls335.heater_mainsorb_manualOUT", 4)
Ls335.heater_mainsorb_high
```

Magnetic field:
```
hexp.set("cmag.heateron")
hexp.set("cmag.field", 0)
hexp.get("cmag.field")
hexp.set("cmag.rate", 0.03)
```

Measure:
```
hexp.record(1, 1000000, "test.dat", reset_plot=True)
hexp.sweep("K6.source_current", None, 8e-4, 101, "test2.dat" , wait=2, reset_plot=True)
import numpy as np

hexp.test_mode = False
hexp.set("cmag.rate", 0.03)
hexp.set("cmag.heateron")

for B in np.arange(0, 0.5, 0.01):
    hexp.set("cmag.field", B)
    hexp.sleep (60)
    hexp.sweep("K6.source_current", None, 8e-4, 101, "test3_B%.3f.up" % B, wait=1, reset_plot=True)

import numpy as np


for T in np.arange(2, 10, 0.1):
    hexp.set("Ls350.Tsample", T)
    hexp.sleep(120)
    hexp.sweep("K6.source_current", None, 4e-4, 801, "test4_T%.3f.up" % T , wait=1, reset_plot=True)
```

Keithley 2440

```
hexp.instrument("K2").vi.apply_voltage()
hexp.instrument("K2").vi.measure_current()
hexp.set("K2.source_enabled" , 1)
hexp.set("K2.source_mode" , "voltage")
hexp.set("K2.source_voltage" , 0.00)
hexp.set("K2.compliance_current", 1e-6)
hexp.set("K2.current_range", 1e-6)
hexp.get("K2.current")
hexp.set("K2.source_voltage_range", 40)
hexp.set("K2.ramp_to_voltage", -1)
hexp.move("K2.source_voltage", 0, 1)
```

Keithley 6220
```
hexp.set("K6.source_current", 0)
hexp.set("K6.source_compliance", 1)
hexp.set("K6.source_enabled", 1)
hexp.move("K6.source_current", 0, 5e-5)
hexp.set("K6.source_auto_range", 1)
```

SR830 lock-in
```
hexp.set("sr1.frequency" , 117)
hexp.set("sr1.time_constant" , 1)   # integration time
hexp.get("sr1.dac1") # this is DC voltage output 1 on the back = AUXout1 - 
#output can also be read directly on right lockin display
hexp.get("sr1.x") # real part
hexp.get("sr1.y") # imaginary part
```

Keithley 2182A
```
hexp.get("nV.sense")
```

# Examples interface for a Bluefors system


**initializing**

```
import pymesomin as hal
from pymesomin.magnetsafety import MagnetCheck
from pymeasure.instruments.srs import SR830
hexp = hal.Cryofast( [ hal.SR830("GPIB::8", "sr1"),
	hal.PyMeasure(SR830("GPIB::10"), "R1b"),
] )
```

**Recording**
```
hexp.measure("cryo.fse.temp, cryo.mc.temp, cryo.mag.temp, amiX.field, amiY.field, amiZ.field, R1a.x, R1a.y")
hexp.log("hal.comment")
```

**Test mode**
```
hexp.test_mode = True
hexp.test_mode = False
```

**Magnet**
```
hexp.set("amiZ.ramp")
hexp.get("amiZ.state")

#target field
hexp.target_fields()

#set field
hexp.set("amiZ.rate 0.1")
#or
hexp.set("amiZ.rate", 0.1)
```



Going to the vector field in a straight line at vector rate (Tesla/min) - changes rates
```
hexp.set_fields_rate(Bx (None), By, Bz, rate)
```

Sets setpoints Bx, By, Bz for the vector field (doenst change rates)
```
hexp.set_fields(Bx (None), By, Bz)
```
```
# returns all 3 field components
hexp.fields()
```

**Changing vector magnetic field in the sample frame**
```
hexp.record_magnet_ramp(0, "name.dn")

#

alpha = 0.08462666666666674

hexp.set_sample_frame( np.array( [[ 1, 0, 0] , 
		[0, math.cos(alpha), math.sin(alpha)], \
		[0, -math.sin(alpha), math.cos(alpha)] ] ) )

#set fields and rate # the maximum rate for vector field is 0.0376 Amps/sec, 0.02 has been used

hexp.set_sample_fields_rate(Bx (None), By, Bz, rate)

#changes only the Bx, By, Bz component in sample frame -

# remaining sample field components are not changed

hexp.set_sample_Bz_rate(bz, rate)

hexp.set_sample_By_rate(0.3, rate)
``` 

```
#Recording

hexp.record_magnet_ramp(0, "name.dn")

#read field

hexp.sample_fields()

#Rotating magnetic field in the (X,Y) sample plane

def run_rotate_loop(bz, bperp, rate, sign=1., name = ""):
    hexp.set_sample_fields_rate(bperp, 0, bz, rate)
    hexp.record_magnet_ramp(0, "waitbxbybzrotate.up")
    filename = "rotate%sSBxBy%.2fAtSBz%.2f.up" % (name, bperp, bz)
    hexp.record_magnet_ramp(0, filename)

    for theta in np.arange(0, 2.*math.pi, 0.02):
    	hexp.set_sample_fields_rate(
		bperp * math.cos(sign * theta), 
		bperp * math.sin(sign * theta),
		bz, rate )
	hexp.record_magnet_ramp(0, filename, reset_plot = False)

    hexp.set_sample_fields_rate(bperp, 0, bz, rate)
    hexp.record_magnet_ramp(0, filename, reset_plot = False)
```

**Magnet error**
When a magnet error is triggered (when the temperature of the magnet is too high and magnetic field is non zero):

```
MagnetCheck().error()
MagnetCheck().reset_error()
```

**Mixing chamber temperature control**

```
# get and set heat power in MxC
hexp.get("cryo.mc.hpow")
hexp.set("cryo.mc.hpow", 7e-5)
hexp.get("cryo.mc.temp, cryo.fse.temp")
```

**Starting the plot-server**
```
#run_server

import pymesomin.plotserver as hal_server

hal_server.run_server(magnet_safety=True)

http://127.0.0.1:8050/
```
