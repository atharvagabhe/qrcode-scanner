# qrcode-scanner
A python script for running a qrcode by stream scanner.
Uses raspicam,leds and a xbee module connected by usb as hardware.
Contains a protocol for xbee communication,as this was a part of a bigger project. 
The qr code reader is restricted to numbers from 0 to 99,can be easily modified for alphanumeric characters or urls.
Leds denote success and failure of communication and qr working.
Otherwise the code is simple enough for a py-man 
