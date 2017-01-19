"""
todo:

old:
    return more contextual data from classifier
      confidence values
      parsed image id

    create new images for feedback

new features:

    detect / fix overlap
    periodic inventory
    email report
        slick formatting
        inventory
        map
        strangers
        changes / patterns



"""
import sys
sys.path.append('/usr/local/lib/python2.7/site-packages')

import cv2
import datetime
import json
import numpy as np
import os
from os import environ
from os import walk
from os.path import join, dirname
import RPi.GPIO as GPIO
import tensorflow as tf
import time
#import zipfile


class Camera():
        def __init__(self, images_folder, cam_id, pin, x_offset, y_offset):
            self.images_folder = images_folder
            self.cam_id = cam_id
            self.pin = pin
            self.x_offset = x_offset
            self.y_offset = y_offset
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        def take_photo(self):
            print  'Camera {} taking picture'.format(self.cam_id)

            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(1)
            #filename = '{}/image_{}.png'.format(self.images_folder,self.cam_id)
            filename = '%s/image_%s.png' % (self.images_folder,self.cam_id)
            
            try: 
                cap = cv2.VideoCapture(0)
                cap.set(3,1280)
                cap.set(4,720)
                if not cap.isOpened():
                    while not cap.isOpened():
                        print "Camera capture not open ... trying to fix it..."
                        cap.open()
                        time.sleep(1)
                else:
                    print filename
                    ret, frame = cap.read()
                    cv2.imwrite(filename,frame)
                    cap.release()
                    print "Picture taken"
            except Exception as e:
                  print "Oops! something went wrong %s" % (e)
            finally:
                 GPIO.output(self.pin, GPIO.LOW)
            time.sleep(1)
            return [filename, self.x_offset, self.y_offset]

class Cameras():
        def __init__(self):
            GPIO.setmode(GPIO.BCM)
            self.pins = [2,3,4,14,15,17,18,27,22,23,24,10]
            self.x_offsets = [0,800,1600,0,800,1600,0,800,1600,0,800,1600]
            self.y_offsets = [0,0,0,450,450,450,900,900,900,1350,1350,1350]
            now = datetime.datetime.now()
            self.images_folder_name = ("%s/camera_capture_images/%s") % (os.path.dirname(os.path.realpath(__file__)), now.strftime("%Y-%m-%d-%H-%M-%S"))
            os.makedirs(self.images_folder_name)
            self.cameras = [Camera(self.images_folder_name, c, self.pins[c], self.x_offsets[c], self.y_offsets[c]) for c in range(12)]
            self.lastImages = []
        def take_all_photos(self):
            self.set_all_pins_low() # just in case
            for cam in self.cameras:
                metadata = cam.take_photo()
                self.lastImages.append(metadata)
        def set_all_pins_low(self):
            for pin in self.pins:
                GPIO.output(pin, GPIO.LOW)
        def get_images_folder(self):
            return self.images_folder_name
        def get_capture_data(self):
            return self.lastImages
        def get_offset_from_id(self, id):
            id = int(id)
            return [self.x_offsets[id],self.y_offsets[id]]

 

class ImageParser(): # class not necessary.  used for organization
    def __init__(self):
        self.parsedCaptures = [] # 2D list of capture:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        now = datetime.datetime.now()
        realnow = now.strftime("%Y-%m-%d-%H-%M-%S")
        self.foldername = ("%s/cropped/%s") %(dir_path, realnow)
        os.makedirs(self.foldername)

    def get_foldername(self):
        return self.foldername

    def get_parsed_images(self):
        return self.parsedCaptures

    def undistort_image(self, image):
        width = image.shape[1]
        height = image.shape[0]
        distCoeff = np.zeros((4,1),np.float64)
        k1 = -6.0e-5; # negative to remove barrel distortion
        k2 = 0.0;
        p1 = 0.0;
        p2 = 0.0;
        distCoeff[0,0] = k1;
        distCoeff[1,0] = k2;
        distCoeff[2,0] = p1;
        distCoeff[3,0] = p2;
        # assume unit matrix for camera
        cam = np.eye(3,dtype=np.float32)
        cam[0,2] = width/2.0  # define center x
        cam[1,2] = height/2.0 # define center y
        cam[0,0] = 10.        # define focal length x
        cam[1,1] = 10.        # define focal length y
        # here the undistortion will be computed
        return cv2.undistort(image,cam,distCoeff)

    def process_image(self, filepath, camera_id):
        print "Processing image...", camera_id, filepath
        parsedImageMetadata = [] 
        self.parsedCaptures.append(parsedImageMetadata)# images are introduce in order of cap_id, so list index == cap_id
        img_for_cropping = cv2.imread(filepath)
        img_for_cropping = cv2.resize(img_for_cropping, (800,450), cv2.INTER_AREA)
        img_for_cropping = self.undistort_image(img_for_cropping)

        img_for_circle_detection = cv2.imread(filepath,0)
        img_for_circle_detection = cv2.resize(img_for_circle_detection, (800,450), cv2.INTER_AREA)
        img_for_circle_detection = self.undistort_image(img_for_circle_detection)
        # cv2.imshow('dst', img_for_circle_detection)
        height, width = img_for_circle_detection.shape
        img_for_circle_detection = cv2.medianBlur(img_for_circle_detection,21)
        img_for_circle_detection = cv2.blur(img_for_circle_detection,(1,1))
        img_for_circle_detection = cv2.Canny(img_for_circle_detection, 0, 23, True)
        img_for_circle_detection = cv2.adaptiveThreshold(img_for_circle_detection,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,17,2)

        print "Detecting circles..."
        circles = cv2.HoughCircles(img_for_circle_detection,cv2.HOUGH_GRADIENT,1,150, param1=70,param2=28,minRadius=30,maxRadius=80)
        circles = np.uint16(np.around(circles))
        margin = 30
        for x, y, radius in circles[0,:]:


            leftEdge = int(x)-int(radius)-int(margin)
            rightEdge = int(x)+int(radius)+int(margin)
            topEdge = int(y)-int(radius)-int(margin)
            bottomEdge = int(y)+int(radius)+int(margin)

            if leftEdge < 0 or  rightEdge > width or topEdge < 0 or bottomEdge > height:
                continue

            #leftEdge = x-radius-margin if x-radius-margin >= 0 else 0
            #rightEdge = x+radius+margin if x+radius+margin <= width else width
            #topEdge = y-radius-margin if y-radius-margin >=0 else 0
            #bottomEdge = y+radius+margin if y+radius+margin <= height else height

            crop_img = img_for_cropping[topEdge:bottomEdge, leftEdge:rightEdge]

            imageName = 'image_%s_%s_%s.jpg'%(camera_id,x, y)
            pathName = '%s/%s'%(self.foldername, imageName)
            cv2.imwrite(pathName,crop_img)
            # draw the outer circle
            cv2.circle(img_for_cropping,(x,y),radius,(0,255,0),2)
            # draw the center of the circle
            cv2.circle(img_for_cropping,(x,y),2,(0,0,255),3)
            #print len(circles)
            parsedImageMetadata.append( {
                'capture':camera_id,
                'imageName':imageName,
                'pathName':pathName,
                'x':x,
                'y':y,
                'radius':radius,
                'leftEdge':leftEdge,
                'rightEdge':rightEdge,
                'topEdge':topEdge,
                'bottomEdge':bottomEdge,
                'label':"",
                'confidence':0
            } )
            #print "detected circle:", repr(x), repr(y), repr(radius), leftEdge, rightEdge, topEdge, bottomEdge

        # cv2.imshow('detected circles',img_for_cropping)

        cv2.destroyAllWindows()
        #print parsedImageMetadata
        print "Processing image done"

    def processImages(self, captureLIst):
        for index, cap_metadata in enumerate(captureLIst):
            self.process_image(cap_metadata[0],index)


class Classifier():
    def __init__(self):
        # Loads label file, strips off carriage return
        self.label_lines = [line.rstrip() for line 
            in tf.gfile.GFile("image_classifier/tf_files/retrained_labels.txt")]

    def classify_images(self, imageMetadataList):
        with tf.gfile.FastGFile("image_classifier/tf_files/retrained_graph.pb", 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            _ = tf.import_graph_def(graph_def, name='')
        with tf.Session() as sess:
            for camera in  imageMetadataList:
                for imageMetadata in camera:
        
                    image_data = tf.gfile.FastGFile(imageMetadata["pathName"], 'rb').read()
                    
                    softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')# Feed the image_data as input to the graph and get first prediction
                    predictions = sess.run(softmax_tensor, \
                             {'DecodeJpeg/contents:0': image_data})
                    top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]# Sort to show labels of first prediction in order of confidence
                    print "top_k=", repr(top_k)
                    for node_id in top_k:
                        human_string = self.label_lines[node_id]
                        score = predictions[0][node_id]
                        print('%s (score = %.5f)' % (human_string, score))
                    # print(self.label_lines[top_k[0]])
                    imageMetadata["label"] = self.label_lines[top_k[0]]
                    imageMetadata["confidence"] = predictions[0][top_k[0]]

    def guess_images(self, foldername):
        files = []
        results = []
        for (dirpath, dirnames, filenames) in walk(foldername):
            files.extend(filenames)
            break
        print("Found " + str(len(files)) + " files")            
        # change this as you see fit
        # image_path = sys.argv[1]
        # image_path = img
        # Unpersists graph from file
        with tf.gfile.FastGFile("image_classifier/tf_files/retrained_graph.pb", 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            _ = tf.import_graph_def(graph_def, name='')
        with tf.Session() as sess:
            for image in files:
                # Read in the image_data
                image_data = tf.gfile.FastGFile(foldername + "/" + image, 'rb').read()
                # Feed the image_data as input to the graph and get first prediction
                softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')
                predictions = sess.run(softmax_tensor, \
                         {'DecodeJpeg/contents:0': image_data})
                # Sort to show labels of first prediction in order of confidence
                top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]
                for node_id in top_k:
                    human_string = self.label_lines[node_id]
                    score = predictions[0][node_id]
                    print('%s (score = %.5f)' % (human_string, score))
                # print(self.label_lines[top_k[0]])
                results.append(self.label_lines[top_k[0]])
            return results

def data_viz(img_metadata):
    canvas = np.zeros((1800,2400,3), np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for cap_images in img_metadata:
        offsets = cameras.get_offset_from_id(cap_images['capture'])
        x_plus_offset = int(cap_images['x'])+offsets[0]
        y_plus_offset = int(cap_images['y'])+offsets[1]
        canvas = cv2.circle(canvas, x_plus_offset,y_plus_offset,40, (255,255,255), -1)
        cv2.putText(canvas, cap_images['label'], (x_plus_offset-30,y_plus_offset-30), font, 0.5,(255,255,255),2,cv2.LINE_AA)
        cv2.imwrite('results.png',img)
        cv2.destroyAllWindows()



cameras = Cameras()

cameras.take_all_photos()
time.sleep(1)

capture_list = cameras.get_capture_data()

imageparser = ImageParser()
imageparser.processImages(capture_list)

parsed_images = imageparser.get_parsed_images()
parsed_folder_name = imageparser.get_foldername()

classifier = Classifier()

classifier.classify_images(parsed_images)

print parsed_images

data_viz(parsed_images)
