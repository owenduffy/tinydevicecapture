#!/usr/bin/python
# SPDX-License-Identifier: GPL-3.0-or-later

#from Ho-Ro's nanovna-tools, modified by Owen Duffy.

'''
Command line tool to capture a screen shot from NanoVNA or tinySA
connect via USB serial.
Name the script capture_<devicetype>.py and the default device type
as specified in the script will be extraced from the script name, etg
capture_tinysaultra.py.
The script emits a png file, and one with inverted colours for printing etc.
'''

import argparse
from datetime import datetime
import serial
from serial.tools import list_ports
import struct
import sys
import numpy
from PIL import Image
import PIL.ImageOps
from pathlib import Path
import re

# ChibiOS/RT Virtual COM Port
VID = 0x0483 #1155
PID = 0x5740 #22336

app=Path(__file__).stem
print(f'{app}_v0.3')
#extract default device name from script name
devicename=re.sub(r'capture_(.*)\.py',r'\1',(Path(__file__).name).lower())

# Get nanovna com device automatically
def getdevice() -> str:
    device_list = list_ports.comports()
    for device in device_list:
        if device.vid == VID and device.pid == PID:
            return device.device
    raise OSError("device not found")

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument( '-c', '--com', dest = 'comport',
    help = 'com port' )
ap.add_argument( "-d", "--device",
    help="device type" )
ap.add_argument( "-o", "--out",
    help="write the data into file OUT" )
ap.add_argument( "-s", "--scale",
    help="scale image s*",default=2 )

options = ap.parse_args()
nanodevice = options.comport or getdevice()
if options.device!=None:
  devicename = options.device
outfile = options.out
sf=float(options.scale)


if devicename == 'tinysa':
    width = 480
    height = 320
elif devicename == 'nanovnah':
    width = 480
    height = 320
elif devicename == 'tinysaultra': # 4" device
    width = 480
    height = 320
elif devicename == 'nanovnah4': # 4" device
    width = 320
    height = 240
elif devicename == 'tinypfa': # 4" device
    width = 480
    height = 320
else:
    sys.exit('Unknown device name.');

print('Using device =',devicename)


# NanoVNA sends captured image as 16 bit RGB565 pixel
size = width * height

crlf = b'\r\n'
prompt = b'ch> '

# do the communication
with serial.Serial( nanodevice, timeout=1 ) as nano_tiny: # open serial connection
    nano_tiny.write( b'pause\r' )  # stop screen update
    echo = nano_tiny.read_until( b'pause' + crlf + prompt ) # wait for completion
    # print( echo )
    nano_tiny.write( b'capture\r' )  # request screen capture
    echo = nano_tiny.read_until( b'capture' + crlf ) # wait for start of transfer
    # print( echo )
    bytestream = nano_tiny.read( 2 * size )
    echo = nano_tiny.read_until( prompt ) # wait for cmd completion
    # print( echo )
    nano_tiny.write( b'resume\r' )  # resume the screen update
    echo = nano_tiny.read_until( b'resume' + crlf + prompt ) # wait for completion
    # print( echo )

if len( bytestream ) != 2 * size:
    print( 'capture error - wrong screen size?' )
    sys.exit()

# convert bytestream to 1D word array
rgb565 = struct.unpack( f'>{size}H', bytestream )

#create new image array
a=[0]*3
a=[a]*width
a=[a]*height
a=numpy.array(a, dtype=numpy.uint8)
for x in range (0,height):
  for y in range (0,width):
    index = y+width*x
    pixel = rgb565[index]
    a[x,y,0]=(pixel&0xf800)>>8
    a[x,y,1]=(pixel&0x07e0)>>3
    a[x,y,2]=(pixel&0x001f)<<3
image=Image.fromarray(a,"RGB")
#some transforms
image=image.resize((int(sf*width),int(sf*height)))
inverted_image=PIL.ImageOps.invert(image)
#save files
filename = options.out or datetime.now().strftime( f'{devicename}_%Y%m%d_%H%M%S' )
image.save(filename + '.png')
inverted_image.save(filename + 'i.png')
