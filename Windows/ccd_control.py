import os
import glob
import time
import redis
import signal
import numpy as np
import win32com.client
from astropy.io import fits
from astropy.visualization import ZScaleInterval
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from matplotlib.colors import LogNorm
from configparser import ConfigParser


config = ConfigParser()
config.read("config_temp.ini")
config_data = config["OFFICIAL"]

FOLDER_PATH = config_data["folder_path"]

HOST_IP = config_data["host_ip"]
REDIS_PORT = config_data["redis_port"]
r = redis.Redis(host=HOST_IP, port=REDIS_PORT)

driver_camera = config_data["driver_camera"]
driver_filter_wheel = config_data["driver_filter_wheel"]
driver_focuser = config_data["driver_focuser"]

camera = win32com.client.Dispatch(driver_camera)
filter_wheel = win32com.client.Dispatch(driver_filter_wheel)
focuser = win32com.client.Dispatch(driver_focuser)

info_list1 = 'result'
info_list2 = 'website_value'
keys1 = ['decide', 'datetime', 'mode', 'filter', 'exptime']
keys2 = ['datetime', 'exptime', 'filter', 'temp']

filters_list = config_data["filters_list"][2:-2].split("', '")


def connect(device):
    wait = True
    while wait:
        try:
            device.connected = True
            wait = False
            if device == camera:
                print("Camera connected")
            elif device == filter_wheel:
                print("Filter wheel connected")
            elif device == focuser:
                print("Focuser connected")
        except:
            if device == f"<COMObject {driver_camera}>":
                print("Camera connected error")
            elif device == f"<COMObject {driver_filter_wheel}>":
                print("Filter wheel connected error")
            elif device == f"<COMObject {driver_focuser}>":
                print("Focuser connected error")
        time.sleep(5)


def create_folder(FOLDER_PATH):
    date = datetime.now()
    if date.hour in range(0,12):
        date = date - timedelta(days = 1)
    date = str(date)[:-16]
    directory = f"{date}"
    path = os.path.join(FOLDER_PATH, directory)
    try:
        os.mkdir(path)
        print('New folder has been created')
    except FileExistsError:
        print('The directory already exists')
    return path


def redis_check(r):
    wait = True
    while wait:
        try:
            r.ping() == True
            print('\x1b[2K')
            print('\033[1A'+"Redis connection successful")
            wait = False
        except redis.exceptions.ConnectionError:
            print("Waiting for connection to Redis", end='\r')


def get_data(name, keys):
    info_list = r.get(name)
    dictionary = dict.fromkeys(keys)
    info_list = info_list.decode('utf-8')
    info_list = info_list.split('#')
    for i, k in enumerate(dictionary):
        dictionary[k] = info_list[i]
    return dictionary


def send_data(filters_list, temp):
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-4]
    filt = filters_list[filter_wheel.Position]
    exptime = str(camera.LastExposureDuration).split('.')[0]
    string = '#'.join([date, exptime, filt, temp])
    data_str = {'cam_info': string}
    r.mset(data_str)
    result = r.get('cam_info').decode("utf-8")
    print(f"Data sent to Redis: {result}")
    return result


def decide(date_time_obs, can_obs, exptime):
    now_time = datetime.now()
    if now_time >= date_time_obs:
        result = ((now_time - date_time_obs).seconds) / 60
    else:
        result = ((date_time_obs - now_time).seconds) / 60
    exptime = int(exptime) / 60
    if int(exptime) <= 0:
        exptime = 1
    if result <= exptime and can_obs:
        print('decide=1', end='\r')
        return True
    else:
        print("decide=0", end='\r')
        return False


def filter_wheel_control(x, filters_list):
    try:
        f = filters_list.index(x)
        filter_wheel.Position = f
    except:
        filter_wheel.Position = x


def get_frame(exptime, filt):
    openshutter = True # False will take a dark frame
    if exptime <= 0:
        exptime = 0.001
    camera.StartExposure(exptime, openshutter)
    wait = True
    while wait:
        if camera.ImageReady:
            wait = False
    image = camera.ImageArray
    data_rotated = np.rot90(image, k=1)
    temp = f'{camera.CCDTemperature:.2f}'

    hdr = fits.Header()
    hdr['EXPTIME'] = f'{camera.LastExposureDuration:.0f}'
    hdr.comments['EXPTIME'] = 'exposure duration in sec'
    hdr['DATE-OBS'] = camera.LastExposureStartTime.split('T')[0]
    hdr.comments['DATE-OBS'] = 'YYYY-MM-DD'
    hdr['TIME-OBS'] = camera.LastExposureStartTime.split('T')[1]
    hdr.comments['TIME-OBS'] = 'HH:MM:SS time of the exposure start'
    hdr['TIMESYS'] = 'UTC'
    hdr['FILTER'] = filt
    hdr.comments['FILTER'] = 'filter name'
    hdr['TEMP'] = temp
    hdr.comments['TEMP'] = 'current CCD temperature in degrees Celsius'
    hdr['XBINNING'] = camera.BinX
    hdr.comments['XBINNING'] = 'binning factor of X axis'
    hdr['YBINNING'] = camera.BinY
    hdr.comments['YBINNING'] = 'binning factor of Y axis'
    hdr['INSTRUME'] = camera.SensorName
    hdr.comments['INSTRUME'] = 'sensor name'

    hdu = fits.PrimaryHDU(data_rotated, header=hdr)
    save_time = datetime.now().strftime('%Y%m%dT%H%M%S')
    hdu.writeto(f'test_{save_time}.fits', overwrite=True)
    hduim = fits.open(f'test_{save_time}.fits')
    
    data = hduim[0].data
    z = ZScaleInterval()
    z1,z2 = z.get_limits(data)
    plt.figure()
    plt.imshow(data, vmin=z1, vmax=z2, cmap="gray")
    plt.axis('off')
    
    list_of_files = glob.glob(f'{config_data["image_path"]}/*.png')
    if len(list_of_files) >= 1:
        latest_file = max(list_of_files, key=os.path.getctime)
        for file in list_of_files:
            if file != latest_file:
                os.remove(file)

    plt.savefig(f'{config_data["image_path"]}/test_{save_time}.png', bbox_inches='tight', pad_inches=0)
    send_data(filters_list, temp)
    plt.close()
    print('Save')
    return True


def handler(signum, frame):
    res = input("Ctrl-c was pressed. Do you really want to exit? y/n ")
    if res == 'y':
        camera.connected = False
        print('Bye')
        exit(1)


def get_value(data_key, default_value):
    if data2[data_key] != 'None':
        return data2[data_key]
    else:
        return default_value



if __name__ == "__main__":
    print("Starting up...")
    redis_check(r)

    connect(camera)
    connect(filter_wheel)
    # connect(focuser)

    path = create_folder(FOLDER_PATH)
    os.chdir(path)

    signal.signal(signal.SIGINT, handler)
    camera.CoolerOn = False
    data = get_data(info_list1, keys1)
    data['datetime'] = datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M:%S.%f')
    first_image = data['datetime']
    filter_info = data['filter']
    exptime = int(data['exptime'])
    get_frame(exptime, filter_info)
    
    while True:
        camera.CoolerOn = True
        data = get_data(info_list1, keys1)
        data['datetime'] = datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M:%S.%f')
        can_observe = decide(data['datetime'], data['decide'], data['exptime'])
        if can_observe == True:
            data2 = get_data(info_list2, keys2)
            data2['datetime'] = datetime.strptime(data2['datetime'], '%Y-%m-%dT%H:%M:%S.%f')
            if first_image <= data2['datetime']:

                filter_info = get_value('filter', filter_wheel.Position)
                filter_wheel_control(filter_info, filters_list)

                exptime = int(get_value('exptime', camera.LastExposureDuration))

                temp = float(get_value('temp', camera.CCDTemperature))
                if camera.CanSetCCDTemperature == True:
                    camera.SetCCDTemperature = temp
                else:
                    print("SetCCDTemperature is not implemented in this driver.")

            get_frame(exptime, filter_info)
            
        time.sleep(5)

camera.connected = False
