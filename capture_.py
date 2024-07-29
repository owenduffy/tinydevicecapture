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
import re
import time
import struct
#from crc import Calculator, Crc16

# ChibiOS/RT Virtual COM Port
VID = 0x0483 #1155
PID = 0x5740 #22336

app=Path(__file__).stem
print(f'{app}_v1.02')

# Get nanovna device automatically
def getdevice() -> str:
    device_list = list_ports.comports()
    for device in device_list:
        if device.vid == VID and device.pid == PID:
            return device.device
    raise OSError("device not found")

def decoderle8(bytestream,width,height,hdrpsize):
  sptr=0xa
  size=width*height
  palette=struct.unpack_from('<{:d}H'.format(hdrpsize),bytestream,sptr)
  sptr=sptr+hdrpsize
  bitmap=bytearray(size*2)
  dptr=0
  row=0
  while(row<height):
    #process RLE block
    bsize=struct.unpack_from('<H',bytestream,sptr)[0]
    sptr=sptr+2
    nptr=sptr+bsize
    while(sptr<nptr):
      count=struct.unpack_from('<b',bytestream,sptr)[0]
      sptr+=1
      if(count<0):
        color=palette[bytestream[sptr]]
        sptr+=1
        while(count<=0):
          count=count+1
          struct.pack_into('<H',bitmap,dptr,color)
          dptr+=2
      else:
        while(count>=0):
          count=count-1
          struct.pack_into('<H',bitmap,dptr,palette[bytestream[sptr]])
          dptr+=2
          sptr+=1
    row+=1
  return bitmap

#extract default device name from script name
devicename=re.sub(r'capture_(.*)\.py',r'\1',(Path(__file__).name).lower())

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument( '-b', '--baud', dest = 'baudrate',
    help = 'com port',default=500000 )
ap.add_argument( '-c', '--com', dest = 'comport',
    help = 'com port' )
ap.add_argument( "-d", "--device",
    help="device type" )
ap.add_argument( "-o", "--out",
    help="write the data into file OUT" )
ap.add_argument( "-s", "--scale",
    help="scale image s*",default=2 )
ap.add_argument( "-f", "--format",
    help="image format [rle | rgb565]" )

options = ap.parse_args()
nanodevice = options.comport or getdevice()
if options.device!=None:
  devicename = options.device
outfile = options.out
sf=float(options.scale)

print(devicename)

if devicename == 'tinysa':
    width = 320
    height = 240
elif devicename == 'nanovnah':
    width = 320
    height = 240
elif devicename == 'tinysaultra': # 4" device
    width = 480
    height = 320
elif devicename == 'nanovnah4': # 4" device
    width = 480
    height = 320
elif devicename == 'tinypfa': # 4" device
    width = 480
    height = 320
else:
    sys.exit('Unknown device name.');

crlf = b'\r\n'
prompt = b'ch> '

#start talking
with serial.Serial( nanodevice, baudrate=options.baudrate, timeout=5 ) as nano_tiny: # open serial connection
  nano_tiny.write( b'pause\r' )  # stop screen update
  echo = nano_tiny.read_until( b'pause' + crlf + prompt ) # wait for completion
  if(len(echo)==0):
    raise Exception('Timed out, zero bytes received waiting for "pause" command response, check communications settings (incl on NanoVNA).')
  #print( echo )

  if(options.format=='rgb565'):
    nano_tiny.write( b'capture\rresume\r' )  # request screen capture, type ahead resume
    echo = nano_tiny.read_until( b'capture' + crlf ) # wait for start of transfer
  else:
    nano_tiny.write( b'capture rle\rresume\r' )  # request screen capture, type ahead resume
    echo = nano_tiny.read_until( b'capture rle' + crlf ) # wait for start of transfer
#  print( echo )

  bytestream = nano_tiny.read(0x0a) # is this a RLE header?
  hdrmagic,hdrwidth, hdrheight,hdrbpp,hdrcompression,hdrpsize=struct.unpack_from('<HHHBBH',bytestream,0)
  if(hdrmagic == 0x4d42):
    if(hdrbpp!=8):
      raise Exception('Unsupported compression bpp.')
    options.format='rle'
    width=hdrwidth
    height=hdrheight
  size = width * height
  baudrate=int(options.baudrate)
  stimeout=int(size*2*2/baudrate*10)
  if(options.format=='rle'):
    stimeout/=4
  print('fmt: ',options.format)
  print('Setting image download timeout to {0:0.1f}s'.format(stimeout))
  nano_tiny.timeout=stimeout

  if(options.format=='rle'):
    starttime=time.time()
    waitfor=prompt + b'resume' + crlf + prompt
    bytestream = bytestream + nano_tiny.read_until(waitfor) # wait for completion
    endtime=time.time()
    print('RLE: time: {:0.3f}s, transferred: {:,d}B, throughput: {:,d}bps'.format(endtime-starttime,len(bytestream),int(len(bytestream)*8/(endtime-starttime))))
    if(bytestream[-len(waitfor):]!=waitfor):
      raise Exception('Communications timeout.')
#CRC feature requested, not yet implemented... OD 20240727
#    calculator = Calculator(Crc16.KERMIT)
#    assert expected == calculator.checksum(bytestream)
#    print('CRC16-CCITT (KERMIT): 0x{:04x}'.format(calculator.checksum(bytestream)))
    try:
      bytestream=decoderle8(bytestream,width,height,hdrpsize)
    except:
      raise Exception('RLE decoding failed, appears corrupt structure.')
  elif (options.format=='rgb565'):
    nano_tiny.timeout=stimeout
    starttime=time.time()
    waitfor=prompt + b'resume' + crlf + prompt
    print('read now...')
    bytestream = bytestream + nano_tiny.read_until(waitfor) # wait for completion
    if(bytestream[-len(waitfor):]!=waitfor):
      raise Exception('Communications timeout.')
    bytestream=bytestream[0:-len(waitfor)]
    endtime=time.time()
    print('RGB: time: {:0.3f}s, transferred: {:d}B, throughput: {:d}bps'.format(endtime-starttime,len(bytestream),int(2*size*8/(endtime-starttime))))
 #   nano_tiny.timeout=1

if(len(bytestream)!=2*size):
  raise Exception('Capture error - wrong screen size?')

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
image=image.resize((int(sf*width),int(sf*height)))
inverted_image=PIL.ImageOps.invert(image)
#save files
filename = options.out or datetime.now().strftime( f'{devicename}_%Y%m%d_%H%M%S' )
image.save(filename + '.png')
inverted_image.save(filename + 'i.png')
