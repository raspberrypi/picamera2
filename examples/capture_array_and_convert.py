#!/usr/bin/python3

from datetime import datetime,timezone
import os
from PiCamera2.PiCamera2 import *
from PiCamera2.converters import *


user = os.getlogin() #Get the current user.
save_dir = f'/home/{user}/Pictures' #Let's save images to this directory.

picam2 = PiCamera2()
config = picam2.still_configuration()
picam2.configure(config)
picam2.start_preview()

picam2.start()

filename = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
rgb = picam2.capture_array()

picam2.stop_preview()
picam2.stop()
picam2.close()


#Convert captured rgb values to different filetypes.
npy = rgb2npy(rgb,filename,save_dir)
print(f'Saved .npy file to {npy}.')

jpg = rgb2jpg(rgb,filename,save_dir)
print(f'Saved .jpg file to {jpg}.')

tif = rgb2tif(rgb,filename,save_dir)
print(f'Saved .tif file to {tif}.')

print('Saving rgb array as png...')
png = rgb2png(rgb,filename,save_dir)
print(f'Saved .png file to {png}.')



