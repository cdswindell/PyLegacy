#!/usr/bin/python

# .-------------------------------------------------------------------------.
# | This program monitors for changes in 'lusb' reports and files in the    |
# | /dev directory when a USB device is connected or removed. It saves      |
# | having to manually run 'lsusb' and 'ls' and having to compare the       |
# | results.                                                                |
# `-------------------------------------------------------------------------'

import os
import time


def get_usb_list(): return os.popen("lsusb").read().strip().split("\n")


def get_dev_list(): return os.listdir("/dev")


def changed(old, now):
    add = []
    rem = []
    for x in now:
        if x not in old:
            add.append(x)
    for x in old:
        if x not in now:
            rem.append(x)
    return add, rem


try:
    print("Monitoring for USB changes and changes in /dev directory")
    usbOld, devOld = get_usb_list(), get_dev_list()
    while True:
        time.sleep(1)
        usbNow = get_usb_list()
        devNow = get_dev_list()
        usbAdd, usbRem = changed(usbOld, usbNow)
        devAdd, devRem = changed(devOld, devNow)
        if len(usbAdd) + len(usbRem) + len(devAdd) + len(devRem) > 0:
            print("-------------------")
            t = time.strftime("%Y-%m-%d %H:%M:%S - ")
            for d in usbAdd:
                print(t + "Added   : " + d)
            for d in usbRem:
                print(t + "Removed : " + d)
            for d in devAdd:
                print(t + "Added   : /dev/" + d)
            for d in devRem:
                print(t + "Removed : /dev/" + d)
            usbOld, devOld = usbNow, devNow
except KeyboardInterrupt:
    print("")
