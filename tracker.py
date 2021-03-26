#Standard Libs
import time
import datetime
import json
import os
import requests
import math
from ftplib import FTP

#Sensor Libs
from microstacknode.hardware.accelerometer.mma8452q import MMA8452Q
import microstacknode.hardware.gps.l80gps
import picamera


#Loop Control Variables
POLL_LOOP = 50
COMMAND_LOOP = 10000
TRACKING_LOOP = 10000
currentTime = int(round(time.time() * 1000))
commandLoop = currentTime
pollLoop = currentTime
trackingLoop = currentTime

#Tilt Thresholds
YThreshold = 10

#Armed Features
armed = False
tracking = False

#Sensors
gps = microstacknode.hardware.gps.l80gps.L80GPS()

G_RANGE = 2
accelCal = {}
accelCal['x'] = 0
accelCal['y'] = 0
accelCal['z'] = 0
angle = {}

def accelPoll():
    global tracking
    with MMA8452Q() as accelerometer:
        accel = accelerometer.get_xyz_ms2()
        R = math.sqrt(pow(accel['x'],2) + pow(accel['y'],2) + pow(accel['z'],2))
        angle['x'] = (math.acos(accel['x']/R) * 57.29578) - 90
        angle['y'] = (math.acos(accel['y']/R) * 57.29578) - 90
        angle['z'] = math.acos(accel['z']/R) * 57.29578

        angle['x'] -= accelCal['x']
        angle['y'] -= accelCal['y']
        angle['z'] -= accelCal['z']

        if (angle['y'] > YThreshold) or (angle['y'] < (YThreshold * -1)):
            t = 0
            print('Exceded threshold, taking pictures')
            takePic()
            tracking = True
    return

def accelCalibrate():
    with MMA8452Q() as accelerometer:
        accelerometer.standby()
        accelerometer.set_g_range(G_RANGE)
        accelerometer.activate()

        for i in range(0,50):
            accel = accelerometer.get_xyz_ms2()
            R = math.sqrt(pow(accel['x'],2) + pow(accel['y'],2) + pow(accel['z'],2))
            angle['x'] = (math.acos(accel['x']/R) * 57.29578) - 90
            angle['y'] = (math.acos(accel['y']/R) * 57.29578) - 90
            angle['z'] = math.acos(accel['z']/R) * 57.29578
            accelCal['x'] += angle['x']
            accelCal['y'] += angle['y']
            accelCal['z'] += angle['z']
            time.sleep(0.05)
        accelCal['x'] /= 50
        accelCal['y'] /= 50
        accelCal['z'] /= 50
    return    
def takePic():
    print("taking picture")
    with picamera.PiCamera() as camera:
            camera.resolution = (640, 480)
            #camera.resolution = (1024, 768)
            camera.start_preview()
            start = time.time()
            camera.capture_sequence((
                '/home/pi/images/image%03d.jpg' % i
                for i in range(5)
            ), use_video_port=True)
            #print('captured 10 images at %.2ffps' % (10 /(time.time() - start)))
            camera.stop_preview()
            #uploadPics()
            uploadFtp()
    return

def uploadFtp():
    ftp = FTP()
    ftp.connect('SERVER_NAME')
    ftp.login('root','password')
    ftp.cwd('/var/www/html/uploads')

    for root, dirs, files in os.walk('/home/pi/images'):
        for fname in files:
            full_name = os.path.join(root, fname)
            ftp.storbinary('STOR ' + fname, open(full_name, 'rb'))
            ftp.sendcmd("SITE CHMOD 777 " + fname)
            os.remove('/home/pi/images/' + fname)

    ftp.close()
    return

def checkActions():
    global armed
    global tracking
    response = requests.get(url="http://SERVER_NAME/api.php?action=arm")
    if (response.json()):
        if not armed:
            print ("Arming Accel")
            armed = True
            setParkingLocation()
            accelCalibrate()
    else:
        if not response.json():
            if armed:
                print("Disarming Accel")
                armed = False
                tracking = False

    response = requests.get(url="http://SERVER_NAME/api.php?action=takepicture")
    if (response.json()):
        takePic()
        requests.get(url="http://SERVER_NAME/api.php?action=picturetaken")
        
        
    return

def setParkingLocation():
    print ("Setting Parking Location");
    data = gps.get_gpgga()
    response = requests.get(url="http://SERVER_NAME/api.php?action=setparking&latitude=" + str(data['latitude']) + "&longitude=" + str(data['longitude']))
    return

def uploadGPSCoords():
    print ("Uploading GPS coords");
    data = gps.get_gpgga()
    response = requests.get(url="http://SERVER_NAME/api.php?action=uploadcoords&latitude=" + str(data['latitude']) + "&longitude=" + str(data['longitude']))
    return    

while 1:
    currentTime = int(round(time.time() * 1000))
    
    if (currentTime > commandLoop):
        print("Checking for actions");
        checkActions()
        commandLoop = currentTime + COMMAND_LOOP
        
    if (currentTime > pollLoop):
        if (armed):
            accelPoll()
        pollLoop = currentTime + POLL_LOOP

    if (currentTime > trackingLoop):
        if (tracking):
            uploadGPSCoords()
        trackingLoop = currentTime + TRACKING_LOOP
            
            
            
    
