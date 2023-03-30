# dbus-mqtt-pv-grott
Growatt grott MQTT feeding DBus PV-Inverter for Victron GX monitoring

You can use [grott](https://github.com/johanmeijer/grott) proxy to side feed a MQTT. From there I've adapted the [dbus-venus-mqtt-pvinverter.py](https://github.com/tbinias/dbus-venus-mqqt-pvinverter/blob/main/dbus-venus-mqtt-pvinverter.py) code subscribing to the Growatt MIN2500TL 1 phase inverter MQTT feed and convert it feed the Victron [DBus](https://github.com/victronenergy/venus/wiki/dbus#pv-inverters). 

This is a great solution, which does not need any firmware change on the Growatt shine stick, only changing the growatt-server IP to point to the proxy.

This is working like a charm!

