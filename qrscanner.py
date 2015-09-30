#1.Import block#
import io
import time
import zbar #with or without GUI
import picamera
import RPi.GPIO as GPIO
import serial
from PIL import Image
from xbee import XBee,ZigBee
from threading import Thread
from timeit import default_timer

#2.Variable Initialisation#

#Xbee Initialiastion
ser=serial.Serial('/dev/zigbee_usb',9600)
rx_data=0
dest_addr_long_local=b'\x00\x00\x00\x00\x00\x00\xFF\xFF'
dest_addr_local='\xFF\xFE'
dest_addr_long=b'\x00\x00\x00\x00\x00\x00\xFF\xFF'
dest_addr='\xFF\xFE'

#GPIO Initialisation
green_led=5
red_led=26
button=23
flash_led=17
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(green_led,GPIO.OUT)
GPIO.setup(red_led,GPIO.OUT)
GPIO.setup(button,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(flash_led,GPIO.OUT)

#Variables,Flags and delay Initialisation
condition=1
maindata="0000"
mainqrflag=0
ack_counter=0
ack_flag=0
ping_flag=0
pingDelay=5
qrThreadRunning = False
pingThreadRunning = False
pingCounter = 0
tog_led = ""
sta='start'
pin='ping failure'
qr='qr success?'
mc='mc success?'
timer_flag =0
#3.Function Definitions#

#3.1.QRDecoder#
def qr_decode():
	counter=0    
	qrflag=0
	qrdata="0000"
	global timer_flag
	global start
	while qrflag==0 and counter < 10:#set 1 for failure test    
		#Create the in-memory stream
		GPIO.output(flash_led,True)
		stream = io.BytesIO()
		with picamera.PiCamera() as camera:
			#camera.start_preview()	#not needed during actual operation,keep till final release for debugging and performance check
			#pic=open('img.jpeg','w+')
			#camera.capture(pic)	#for preview only
			time.sleep(2)#to reduce the speed of test\counter increased
			camera.capture(stream,format='jpeg')
					
			#"Rewind"
			stream.seek(0)
			pil=Image.open(stream)

			#seek barcode
			scanner=zbar.ImageScanner()
				
			#configure the reader
			scanner.parse_config('enable')
			pil=pil.convert('L')
			width,height=pil.size
			raw=pil.tostring()

			#wrap image data
			image=zbar.Image(width,height,'Y800',raw)

			#scan the image for barcodes
			scanner.scan(image)

			#extract results
			for symbol in image:
				qrdata=symbol.data

			if(qrdata!="0000"):
				qrflag=1
				start = default_timer()######
				timer_flag=1
			counter=counter+1
			
			del(image)
			print '	QR-Tracer--qrflag: '+str(qrflag)
			GPIO.output(flash_led,False)
			#camera.stop_preview()
						
	return (qrdata,qrflag)
	
#3.2 LED control# can be reduced-must be reduced
def led(led_color,device):
	global led_busy
	if	led_color==green_led and device==qr:
		for x in xrange(5):
			GPIO.output(green_led,True)
			time.sleep(.25)
			GPIO.output(green_led,False)
			time.sleep(.25)
	elif led_color==green_led and device==mc:
		GPIO.output(green_led,True)
		time.sleep(2)
		GPIO.output(green_led,False)
		time.sleep(1)
	elif led_color==red_led and device==qr:
		for x in xrange(5):
			GPIO.output(red_led,True)
			time.sleep(.25)
			GPIO.output(red_led,False)
			time.sleep(.25)
	elif led_color==red_led and device==mc:
		GPIO.output(red_led,True)
		time.sleep(2)
		GPIO.output(red_led,False)
		time.sleep(1)
	elif led_color==tog_led and device==pin:
		for x in xrange(2):
			GPIO.output(red_led,True)
			time.sleep(.05)
			GPIO.output(red_led,False)
			GPIO.output(green_led,True)
			time.sleep(.05)
			GPIO.output(green_led,False)
			time.sleep(.05)
	elif led_color==tog_led and device==sta:
		for x in xrange(2):
			GPIO.output(red_led,True)
			GPIO.output(green_led,True)
			GPIO.output(flash_led,True)
			time.sleep(.5)
			GPIO.output(red_led,False)
			GPIO.output(green_led,False)
			GPIO.output(flash_led,False)
			time.sleep(.5)
			
#3.3 Xbee Transmission	  
def xbee_tx(maindata):
	global ack_flag
	global ack_counter
	ack_counter_val=10
	if dest_addr_local==b'\xFF\xFE' and dest_addr_long_local==b'\x00\x00\x00\x00\x00\x00\xFF\xFF':
		print 'XB-Tracer--Broadcasting...'
	else:
		print 'XB-Tracer--Transmitting to gateway...'
	if maindata>='1'and maindata<='99':#for QR,dont convert before this loop
		maindata=int(maindata)
		if maindata>=1 and maindata<=9:
			data_local='\x09\x01'+chr(maindata)#works dont change
		elif maindata>=10 and maindata<=99:
			data_local='\x09\x10'+chr(maindata)#only sends in hex.
		xbee.send('tx',dest_addr_long=dest_addr_long_local,dest_addr=dest_addr_local,data=data_local)
		ack_flag=1
		ack_counter=ack_counter_val #set flag for expecting acknowledgement
	elif maindata=='ping_resp':
		xbee.send('tx',dest_addr_long=dest_addr_long_local,dest_addr=dest_addr_local,data='\x02\x00')
	elif maindata=='serv':
		xbee.send('tx',dest_addr_long=dest_addr_long_local,dest_addr=dest_addr_local,data='\x04\x01\x04')
	elif maindata=='ping_requ':
        	xbee.send('tx',dest_addr_long=dest_addr_long_local,dest_addr=dest_addr_local,data='\x01\x00')
		
#3.4 Receive via xbee callback-parallel threading#refer xbee doc for explaination
def xbee_Receive_Callback(response):
	global ack_flag
	global timer_flag
	global ack_counter
	global start
	global dest_addr_local
	global dest_addr_long_local
	global ping_flag 
	global pingDelay
	print 'XB-Tracer--Frame received'
	id=response['id']
	if ack_flag==1:#:--Keep this
		print '	QR-Tracer--ack_flag: '+str(ack_flag)
		if ack_counter==0:
			led(red_led,mc)
			
			ack_flag=0
			print '	QR-Tracer--Acknowledgement failed!'
		else:	
			ack_counter=ack_counter-1
			print '	QR-Tracer--ack_counter: '+str(ack_counter)

	if id == 'rx':
		data=str(repr(response['rf_data']))
		data=data[1:-1]
		print data
		tdata=''.join("{:02X}".format(ord(c)) for c in data)#workaround
		data_ping=data[0:8]
		print 'TDATA:'+str(tdata)
		if data==('\\x0b\\x00' or '\\x0B\\x00'):#workaround for gatewaypush #0B00 
			dest_addr_local=response['source_addr']
			dest_addr_long_local=response['source_addr_long']
			print 'XB-Tracer--Gateway Push received'
		elif data==('\\x03\\x00') :#workaround #0300 \x03\\x00
			xbee_tx('serv')
			print 'XB-Tracer--Self Description Request received'
		elif data==('\\x01\\x00'):#workaround #0100
        		xbee_tx('ping_resp')
            		print 'XB-Tracer--Ping received'
                elif data==('\\x02\\x00'):
        		global pingCounter
        		pingCounter = 0
        		print 'XB-Tracer--Gateway Alive'
		elif data_ping==('\\x10\\x01'):#workaround #1001XX##ignored
			print data_ping
			data_pingDelay=data[-2:]
			print data_pingDelay
			pingDelay=float(data_pingDelay)#global variable for ping delay in paralell thread.
			print 'XB-Tracer--========='+str(pingDelay)
			ping_flag=1
			print 'XB-Tracer--Ping Configuration received'
		elif tdata=='5C6E5C783030':#workaround for acknowledgement #0A00
			print '	QR-Tracer--QR Acknowledgement received'
			led(green_led,mc)
			if timer_flag==1:
				duration = default_timer() - start
				print '		Eval-Tracer--'+str(duration)
				timer_flag=0
			ack_flag=0
	else:
		print 'XB-Tracer--Response Received with Id: ' + str(id)+ ' and ignored'
#3.5 Thread that controls qr execution
def qr_Thread():	
	try:#reinstate
		global qrThreadRunning
		
		maindata,mainflag = qr_decode()
		mainflag=str(mainflag)
		print '	QR-Tracer--mainflag: '+mainflag
		if	mainflag=='1':
			led(green_led,qr)
			
		else:
			led(red_led,qr)
			
		xbee_tx(maindata)
		qrThreadRunning = False
		print '	QR-Tracer--qrThreadRunning: ' + str(qrThreadRunning)
	except:
		qrThreadRunning = False

#3.6 Thread that sends continous ping responses,to show that that device is alive
def ping_Thread():
	global pingDelay
	global pingCounter

	while True:
		if pingCounter < 3: 
			xbee_tx('ping_requ')
			pingCounter = pingCounter +1
			print 'XB-Tracer--Pinged'
			time.sleep(pingDelay)
		else:
			led(tog_led,pin)
			pingCounter = 0

#4.Main Control flow#
print "#-#-#-#-QR Decoder Started-#-#-#-#"
led(tog_led,sta)
xbee=ZigBee(ser, callback=xbee_Receive_Callback)
while True:
	time.sleep(0.001)
	if GPIO.input(button) == False:##CHANGE IT TO FALSE FOR ACTUAL OPERATION
		try:
			if qrThreadRunning == False:
				print '	QR-Tracer--starting new qrThread '
				qrThread = Thread(target = qr_Thread)
				qrThread.start()	
				qrThreadRunning = True
				print '	QR-Tracer-qrThreadRunning: ' + str(qrThreadRunning)
		except:
				qrThreadRunning=False
	try:
		if pingThreadRunning == False:
			pingThread = Thread(target= ping_Thread)
			print 'XB-Tracer--starting new pingThread'
			pingThread.start()
			pingThreadRunning = True
			print 'XB-Tracer--pingThreadRunning:' + str(pingThreadRunning)	
	except:
		pingThreadRunning=False
