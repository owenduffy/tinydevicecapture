# tinydevicecapture
A python utility for screen capture from certain tiny devices.

The default device type is extracted from the executed script name. For
example if you make a copy of the script and call it
capture_tinysaultra.py, it will run with a default device type of 
tinysaultra.

The default device type can be overridden with the -d option.

It is convenient to have a copy of the script for each of the devices 
in use as one can just run the script (eg double click) without any
switches.

For example:
copy capture_.py capture_nanovnah4.py
copy capture_.py capture_tinysaultra.py

Images are scaled, depending on the device type.

Two images are emitted, a 'normal' image and one with inverted colours
which is more suited to printing (uses less toner, ink etc).
