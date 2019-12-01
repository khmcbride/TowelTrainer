# This file is executed on every boot (including wake-boot from deepsleep)
import esp
#esp.osdebug(None)
#import webrepl
import network
import tt

try:
  import usocket as socket
except:
  import socket

import gc
gc.collect()

def expose_ap():
	ssid = 'TT-AP'
	password = 'towel'
	authmode = network.AUTH_WPA_WPA2_PSK

	ap = network.WLAN(network.AP_IF)
	ap.active(True)
	ap.config(essid=ssid, password=password)#, authmode=authmode)

	while ap.active() == False:
	  pass

	print('Connection successful')
	print(ap.ifconfig())

def do_connect():
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect('McBride-Net', '********')
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())

#do_connect()
expose_ap();
#webrepl.start()

