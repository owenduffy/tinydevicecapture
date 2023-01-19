#!/usr/bin/python
# SPDX-License-Identifier: GPL-3.0-or-later
'''
Command line tool to capture a screen shot from NanoVNA or tinySA
connect via USB serial, issue the command 'capture'
and fetch 320x240 or 480x320 rgb565 pixel.
These pixels are converted to rgb888 values
that are stored as an image (e.g. png)
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

# ChibiOS/RT Virtual COM Port
VID = 0x0483 #1155
PID = 0x5740 #22336

app=Path(__file__).stem
print(f'{app}_v0.2')

# Get nanovna device automatically
def getdevice() -> str:
    device_list = list_ports.comports()
    for device in device_list:
        if device.vid == VID and device.pid == PID:
            return device.device
    raise OSError("device not found")

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument( '-d', '--device', dest = 'device',
    help = 'connect to device' )
typ = ap.add_mutually_exclusive_group()
typ.add_argument( '-n', '--nanovna', action = 'store_true',
    help = 'use with NanoVNA-H' )
typ.add_argument( '--h4', action = 'store_true',
    help = 'use with NanoVNA-H4 (default)' )
typ.add_argument( '-t', '--tinysa', action = 'store_true',
    help = 'use with tinySA' )
typ.add_argument( '--ultra', action = 'store_true',
    help = 'use with tinySA Ultra' )
typ.add_argument( '-p', '--tinypfa', action = 'store_true',
    help = 'use with tinyPFA' )
ap.add_argument( "-o", "--out",
    help="write the data into file OUT" )
ap.add_argument( "-s", "--scale",
    help="scale image s*",default=2 )

options = ap.parse_args()
outfile = options.out
nanodevice = options.device or getdevice()
sf=float(options.scale)

# The size of the screen (4" devices)
width = 480
height = 320

if options.tinysa:
    devicename = 'tinySA'
elif options.ultra:
    devicename = 'tinySA Ultra' # 4" device
    width = 480
    height = 320
elif options.nanovna:
    devicename = 'NanoVNA-H4' # 2.8" device
    width = 320
    height = 240
elif options.tinypfa:
    devicename = 'tinyPFA' # 4" device
    width = 480
    height = 320
else:
    devicename = 'NanoVNA-H'

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
