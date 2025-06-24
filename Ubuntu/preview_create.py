import os
import glob
import numpy as np
from astropy.io import fits
from datetime import datetime
from configparser import ConfigParser


config = ConfigParser()
config.read("config_temp.ini")
config_data = config["OFFICIAL"]

fits_image_filename = config_data["patterns"]
file_path = config_data["ubuntu_path"]
path = f'{file_path}/{fits_image_filename}'
files = glob.glob(f'{file_path}/*')

[os.remove(i) for i in files]

data = np.random.rand(1024, 1024)

header = fits.Header()
header['OBJECT'] = "bias"
header['OBSERVER'] = "RW"
header['EXPTIME'] = 10
header['FILTER'] = "R"
header['DATE-OBS'] = str(datetime.now().date())
header['TIME-OBS'] = str(datetime.now().strftime('%H:%M:%S.%f')[:-4])

hdu = fits.PrimaryHDU(data, header=header)
hdul = fits.HDUList([hdu])
hdul.writeto(path, overwrite=True)

hdul = fits.open(path)
hdr = hdul[0].header

[print(f"{k}: {v}") for k, v in hdr.items()]
