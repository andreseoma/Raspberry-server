# Raspberry-server

This project has a webserver written in Python using the Tornado webserver. The webserver displays information about the devices connected to it. Commands can be sent to the devices using the website and changes are updated automatically and dynamically. The webserver is in WebPageGen.py.

Devices connect to the server using sockets as described in the ClientHandler.py file.

The project also has code for an Atmega microcontroller that can connect to the server using the ESP8266 Wifi module. The code handles the communication with the Wifi module, reads commands into a buffer and responds to them.
