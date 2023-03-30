#!/usr/bin/env python
from gi.repository import GLib
import platform
import logging
import sys
import os
import time
import json
import paho.mqtt.client as mqtt
import configparser # for config/ini file
import _thread

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))
from vedbus import VeDbusService

path_UpdateIndex = '/UpdateIndex'

# get values from config.ini file
config = configparser.ConfigParser()
config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

# MQTT setup
MQTT_broker_address = config['MQTT']['broker_address']
MQTT_topic          = config['MQTT']['topic']
MQTT_client_name    = "MqttPV"

# set variables
connected = 0

pv_power = 0
pv_current = 0
pv_voltage = 0
pv_forward = 0

pv_L1_power = None
pv_L1_current = None
pv_L1_voltage = None
pv_L1_forward = None

pv_L2_power = None
pv_L2_current = None
pv_L2_voltage = None
pv_L2_forward = None

pv_L3_power = None
pv_L3_current = None
pv_L3_voltage = None
pv_L3_forward = None


# MQTT requests
def on_disconnect(client, userdata, rc):
    global connected
    print("Client got disconnected")
    if rc != 0:
        print('Unexpected MQTT disconnection. Will auto-reconnect')

    else:
        print('rc value:' + str(rc))

    try:
        print("Trying to reconnect")
        client.connect(MQTT_broker_address)
        connected = 1
    except Exception as e:
        logging.exception("Error in retrying to connect with broker")
        print("Error in retrying to connect with broker")
        connected = 0
        print(e)

def on_connect(client, userdata, flags, rc):
    global connected
    if rc == 0:
        print("Connected to MQTT broker!")
        connected = 1
        client.subscribe(MQTT_topic)
    else:
        print("Failed to connect, return code %d\n", rc)



def on_message(client, userdata, msg):
    try:
        # Growatt MIN2500
        # {"device": "TCG2A4707E", "time": "2022-11-29T22:51:32", "buffered": "no", "values": {"recortype1": 3000, "recortype2": 3124, "pvstatus": 0, "pvpowerin": 0, "pv1voltage": 0, "pv1current": 0, "pv1watt": 0, "pv2voltage": 0, "pv2current": 0, "pv2watt": 0, "pvpowerout": 0, "pvfrequentie": 0, "pvgridvoltage": 0, "pvgridcurrent": 0, "pvgridpower": 0, "pvgridvoltage2": 0, "pvgridcurrent2": 0, "pvgridpower2": 0, "pvgridvoltage3": 0, "pvgridcurrent3": 0, "pvgridpower3": 0, "totworktime": 42984395, "pvenergytoday": 7, "pvenergytotal": 35229, "epvtotal": 36394, "epv1today": 0, "epv1total": 120, "epv2today": 8, "epv2total": 36274, "pvtemperature": 0, "pvipmtemperature": 111}}
        #t = js['time']
        #return js.get('values').get('totworktime')
        
        global pv_power, pv_current, pv_voltage, pv_forward, pv_L1_power, pv_L1_current, pv_L1_voltage, pv_L1_forward, pv_L2_power, pv_L2_current, pv_L2_voltage, pv_L2_forward, pv_L3_power, pv_L3_current, pv_L3_voltage, pv_L3_forward
        # get JSON from topic
        if msg.topic == MQTT_topic:
            js = json.loads(msg.payload)
            pv_power   = float(js['values']['pvpowerout']) / 10
            pv_forward = float(js['values']['pvenergytotal']) / 10

            # check if L1 and L1 -> power exists
            if config['DEFAULT']['pv_line'] == '1':
                pv_L1_power   = float(js['values']['pvgridpower']) / 10
                pv_L1_current = float(js['values']['pvgridcurrent']) / 10
                pv_L1_voltage = float(js['values']['pvgridvoltage']) / 10
                pv_L1_forward = float(js['values']['pvenergytoday']) / 10

            elif config['DEFAULT']['pv_line'] == '2':
                pv_L2_power   = float(js['values']['pvgridpower']) / 10
                pv_L2_current = float(js['values']['pvgridcurrent']) / 10
                pv_L2_voltage = float(js['values']['pvgridvoltage']) / 10
                pv_L2_forward = float(js['values']['pvenergytoday']) / 10

            else:
                pv_L3_power   = float(js['values']['pvgridpower']) / 10
                pv_L3_current = float(js['values']['pvgridcurrent']) / 10
                pv_L3_voltage = float(js['values']['pvgridvoltage']) / 10
                pv_L3_forward = float(js['values']['pvenergytoday']) / 10

    except Exception as e:
        logging.exception("Failed to parse MQTT message. (on message function)")
        print(e)
        print("Failed to parse MQTT message")



class DbusMqttPvService:
    def __init__(self, servicename, deviceinstance, paths, productname='MQTT PV', connection='MQTT PV service'):

        global config

        self._dbusservice = VeDbusService(servicename)
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0xFFFF) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0.1)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/Position', int(config['DEFAULT']['pv_position'])) # normaly only needed for pvinverter
        self._dbusservice.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter.

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue
                )

        GLib.timeout_add(1000, self._update) # pause 1000ms before the next request


    def _update(self):
        self._dbusservice['/Ac/Power'] =  round(pv_power, 2)
        self._dbusservice['/Ac/Current'] = round(pv_current, 2)
        self._dbusservice['/Ac/Voltage'] = round(pv_voltage, 2)
        self._dbusservice['/Ac/Energy/Forward'] = round(pv_forward, 2)

        #self._dbusservice['/StatusCode'] = 7
        
        if config['DEFAULT']['pv_line'] == '1' and  pv_L1_power != None:
            self._dbusservice['/Ac/L1/Power'] = round(pv_L1_power, 2)
            self._dbusservice['/Ac/L1/Current'] = round(pv_L1_current, 2)
            self._dbusservice['/Ac/L1/Voltage'] = round(pv_L1_voltage, 2)
            self._dbusservice['/Ac/L1/Energy/Forward'] = round(pv_L1_forward, 2)

        elif config['DEFAULT']['pv_line'] == '2' and  pv_L2_power != None:
            self._dbusservice['/Ac/L2/Power'] = round(pv_L2_power, 2)
            self._dbusservice['/Ac/L2/Current'] = round(pv_L2_current, 2)
            self._dbusservice['/Ac/L2/Voltage'] = round(pv_L2_voltage, 2)
            self._dbusservice['/Ac/L2/Energy/Forward'] = round(pv_L2_forward, 2)

        elif config['DEFAULT']['pv_line'] == '3' and  pv_L3_power != None:
            self._dbusservice['/Ac/L3/Power'] = round(pv_L3_power, 2)
            self._dbusservice['/Ac/L3/Current'] = round(pv_L3_current, 2)
            self._dbusservice['/Ac/L3/Voltage'] = round(pv_L3_voltage, 2)
            self._dbusservice['/Ac/L3/Energy/Forward'] = round(pv_L3_forward, 2)

        logging.info("PV: {:.1f} W - {:.1f} V - {:.1f} A".format(pv_power, pv_voltage, pv_current))
        if pv_L1_power:
            logging.info("|- L1: {:.1f} W - {:.1f} V - {:.1f} A".format(pv_L1_power, pv_L1_voltage, pv_L1_current))
        if pv_L2_power:
            logging.info("|- L2: {:.1f} W - {:.1f} V - {:.1f} A".format(pv_L2_power, pv_L2_voltage, pv_L2_current))
        if pv_L3_power:
            logging.info("|- L3: {:.1f} W - {:.1f} V - {:.1f} A".format(pv_L3_power, pv_L3_voltage, pv_L3_current))


        # increment UpdateIndex - to show that new data is available
        index = self._dbusservice[path_UpdateIndex] + 1  # increment index
        if index > 255:   # maximum value of the index
            index = 0       # overflow from 255 to 0
        self._dbusservice[path_UpdateIndex] = index
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change



def main():
    logging.basicConfig(level=logging.INFO) # use INFO for less logging, DEBUG for debugging
    _thread.daemon = True # allow the program to quit

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    #formatting
    _kwh = lambda p, v: (str(round(v, 2)) + 'kWh')
    _a = lambda p, v: (str(round(v, 2)) + 'A')
    _w = lambda p, v: (str(round(v, 2)) + 'W')
    _v = lambda p, v: (str(round(v, 2)) + 'V')
    _n = lambda p, v: (str(round(v, 0)))

    paths_dbus = {
        '/Ac/Power': {'initial': 0, 'textformat': _w},
        '/Ac/Current': {'initial': 0, 'textformat': _a},
        '/Ac/Voltage': {'initial': 0, 'textformat': _v},
        '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh},

        '/Ac/MaxPower': {'initial': int(config['DEFAULT']['pv_max']), 'textformat': _w},
        '/Ac/Position': {'initial': int(config['DEFAULT']['pv_position']), 'textformat': _n},
        '/Ac/StatusCode': {'initial': 0, 'textformat': _n},
        path_UpdateIndex: {'initial': 0, 'textformat': _n},
    }

    if config['DEFAULT']['pv_line'] == '1':
        paths_dbus.update({
            '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
            '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': _kwh},
        })
    
    elif config['DEFAULT']['pv_line'] == '2':
        paths_dbus.update({
            '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
            '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
        })

    elif config['DEFAULT']['pv_line'] == '3':
        paths_dbus.update({
            '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
            '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh},
        })

    pvac_output = DbusMqttPvService(
        servicename='com.victronenergy.pvinverter.mqtt_pv',
        deviceinstance=31,
        paths=paths_dbus,
        productname=config['DEFAULT']['device_name']
        )

    logging.info('Connected to dbus and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()



# MQTT configuration
client = mqtt.Client(MQTT_client_name) # create new instance
client.on_disconnect = on_disconnect
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_broker_address)  # connect to broker

client.loop_start()

# wait to receive first data, else the JSON is empty
time.sleep(5)

if __name__ == "__main__":
  main()
