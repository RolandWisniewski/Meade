import os
import time
import win32com.client
from configparser import ConfigParser

# if you don't know what your driver is called, use the ASCOM Chooser
#x = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
#x.DeviceType = 'Camera'
#driver_camera = x.Choose(None)
# x.DeviceType = 'FilterWheel'
#driver_filter_wheel = x.Choose(None)
# x.DeviceType = 'Focuser'
#driver_focuser = x.Choose(None)

# otherwise, just use it
driver_camera = "ASCOM.Simulator.Camera"
driver_filter_wheel = "ASCOM.Simulator.FilterWheel"
driver_focuser = "ASCOM.Simulator.Focuser"

camera = win32com.client.Dispatch(driver_camera)
filter_wheel = win32com.client.Dispatch(driver_filter_wheel)
focuser = win32com.client.Dispatch(driver_focuser)

def connect(device):
    device_name = str(device).split('.')[-1][:-1]
    wait = True
    while wait:
        try:
            device.connected = True
            wait = False
        except:
            print(f'{device_name} connected error')
        time.sleep(1)

connect(camera)
connect(filter_wheel)
connect(focuser)

config = ConfigParser()

config["OFFICIAL"] = {
    "patterns": "preview.fits", # set preview file name
    "folder_path": os.getcwd().replace('\\', '/'), # set the directory where images will be saved
    "ubuntu_path": "/home", # set the directory where the second telescope results will appear
    "fits_image_filename": "%(ubuntu_path)s/%(patterns)s",
    "host_ip": "localhost", # set redis ip
    "redis_port": 6379, # set redis port
    "driver_camera": driver_camera,
    "driver_filter_wheel": driver_filter_wheel,
    "driver_focuser": driver_focuser,
    "filters_list": [i for i in filter_wheel.Names],
    "image_path": "%(folder_path)s/assets/images"
}

with open("config_temp.ini", "w") as f:
    config.write(f)
