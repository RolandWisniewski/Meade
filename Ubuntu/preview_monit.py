import os
import time
import redis
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from astropy.io import fits
import datetime as dt
from configparser import ConfigParser


config = ConfigParser()
config.read("config_temp.ini")
config_data = config["OFFICIAL"]

HOST_IP = config_data["host_ip"]
REDIS_PORT = config_data["redis_port"]
r = redis.Redis(host=HOST_IP, port=REDIS_PORT)
PATH = config_data["ubuntu_path"]


def redis_activate(r):
    try:
        r.ping() == True
        print("Redis is already running.")
    except:
        os.system("sudo sysctl vm.overcommit_memory=1")
        exit_code = os.system("sudo redis-server --daemonize yes")
        if exit_code == 0:
            print("Redis activated.")
        else:
            print(f"Error starting Redis. Exit code: {exit_code}")


def header_read():
    fits_image_filename = config_data["fits_image_filename"]
    print("open file")
    try:
        hdul = fits.open(fits_image_filename)
        hdr = hdul[0].header
        return hdr
    except OSError as e:
        print("Error:", e)
        return None


def date_time(hdr):
    date = hdr['DATE-OBS']
    time = dt.datetime.strptime(hdr['TIME-OBS'], '%H:%M:%S.%f')
    exp_time = hdr['EXPTIME']
    time += dt.timedelta(seconds=exp_time)
    time = str(time.time())
    if '.' not in time:
        time += '.000000'
    return f'{date}T{time}'


def str_create(hdr, check_time):
    can_observe = '1'
    date_time = str(check_time)
    mode = str(hdr['OBJECT'])
    filtr = str(hdr['FILTER'])
    exp_time = str(hdr['EXPTIME']).split('.')[0]
    data_str = '#'.join([can_observe, date_time, mode, filtr, exp_time])
    result = {'result': data_str}
    return result


def send_data(str_create, r):
    r.mset(str_create)
    result = r.get('result').decode("utf-8")
    print(f"Data sent to Redis: {result}")
    print("Waiting...", end='\r')
    return result


class Handler(PatternMatchingEventHandler):

    def on_created(self, event):
        print("created")
        time.sleep(1)
        hdr = header_read()
        while hdr is None:
            hdr = header_read()
        print("header read")
        check_time = date_time(hdr)
        print("time checked")
        link_create = str_create(hdr, check_time)
        print("str created")
        send_data(link_create, r)


if __name__ == "__main__":
    redis_activate(r)
    observer = Observer()
    event_handler = Handler(
        patterns=[config_data["patterns"]],
        ignore_directories=True)
    observer.schedule(event_handler, PATH, recursive=False)
    observer.start()
    print("Waiting...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

os.system("redis-cli shutdown")
