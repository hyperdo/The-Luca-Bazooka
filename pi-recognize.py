from __future__ import division
from servo import Servo
import cv2
import imageio
import sys
import os
from os.path import expanduser as eu
import numpy as np
from scipy import ndimage
from picamera.array import PiRGBArray
from picamera import PiCamera
import servo
#PARAMETERS
vidfeed='/home/pi/The-Luca-Bazooka'+'/classic.mp4' #0 usually corresponds to webcam feed
outputToFile=False
filename='output.avi'
outputImage=True
outputImagePath = '/home/pi/The-Luca-Bazooka/capturedStills/'
confidenceLevel=400
debugStuff=True
debug=True
rotate=False
showImage=False
cascadePath='/home/pi'+'/The-Luca-Bazooka/data/haarcascade_frontalface_default.xml'
trainingFolders=['/home/pi'+'/The-Luca-Bazooka/training/luca']
changeResolution=True
size=(.2,.2)
resolution = (320,240)
size = (320,240)
framerate = 32
visualizeLBP=True

try:
    from skimage.feature import local_binary_pattern as lbp
except ImportError:
    print("WARNING: skimage.feature failed to import. Turning off LBP visualization")
    visualizeLBP=False

class FaceDetectionError(Exception):
    pass


def extractFace(img, train=False):
    """Self explanatory - extracts multiple faces from given numpy matrix using haar cascades"""
    path = cascadePath
    cascade = cv2.CascadeClassifier(path)
    if train == True: #slightly relaxed constraints so more faces detected on training and less errors thrown
        faces = cascade.detectMultiScale(
            img, scaleFactor=1.1,
            minNeighbors=4,
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE)
    else:
        faces = cascade.detectMultiScale(
            img, scaleFactor=1.11,
            minNeighbors=5,
            minSize=(40, 40),
            flags=cv2.CASCADE_SCALE_IMAGE)
    return faces


def crop(img, c):
    """Crops an image which 4-tuple c and acts on image img"""
    x, y, w, h = c[0], c[1], c[2], c[3]
    return img[y:y+h, x:x+w]


def predict(img):
    return recognizer.predict(img)


def faceProcess(img):
    """Mega method - extracts faces and crops them sorting them by facial area detected"""
    faces = extractFace(img, True)
    faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
    try:
        return crop(img, faces[0])
    except IndexError:
        cv2.imshow('Failed Detection',img) #hooray for throwing errors under the rug - in this vers, crashes are caught pretty much
        cv2.waitKey()
        #raise FaceDetectionError("No face was detected with img "+str(img))


def loadImagesFromFolder(folder):
    """Loads all images from specified path and transforms it to greyscale"""
    # based off of
    # http://stackoverflow.com/questions/30230592/loading-all-images-using-imread-from-a-given-folder
    images = []
    print(os.listdir(folder))
    for filename in os.listdir(folder):
        if debugStuff:
            print(os.path.join(folder, filename))
        img = cv2.imread(
            os.path.join(folder, filename), cv2.CV_LOAD_IMAGE_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images


def trainStep(folder, label):
    """Intermediate step for training, processes all images from folder then detects faces and prepares labels"""
    label = np.array(label)
    imgs = loadImagesFromFolder(folder)
    if debugStuff==True:
        print(len(imgs))
    return [[faceProcess(i) for i in imgs], np.array([label for x in imgs])]


def trainAll(folders):
    """Calls trainstep for all folders and puts it in to global recognizer class"""
    totalFaces = []
    totalLabels = []
    for i in enumerate(folders):
        working = trainStep(i[1], i[0])
        totalFaces.extend(working[0])
        totalLabels.extend(working[1])
        if debugStuff==True:
            print(totalLabels)
    recognizer.train(totalFaces, np.array(totalLabels))



def main(folders):
    """Pretty much self-explanatory thanks to python: sets up servos and then reads images from picamera array and does stuff based on params"""
    servo = Servo(12,23,60/320, 45/240,320,240,90,90)
    global recognizer
    recognizer = cv2.createLBPHFaceRecognizer()
    trainAll(folders)
    if showImage:
        cv2.namedWindow("The Luca Bazooka", cv2.cv.CV_WINDOW_AUTOSIZE)
    camera=PiCamera()
    camera.resolution=resolution
    camera.framerate=framerate
    rawCapture=PiRGBArray(camera,size=size)
    frameNumber = 0
    if outputToFile:
        video_writer=imageio.get_writer('~/The-Luca-Bazooka/'+filename,fps=24)
    for nonprocessed in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        frameNumber += 1
        if debug:
            print('VIDEO CAPTURE GOING')
        frame=nonprocessed.array
        if rotate:
            frame=ndimage.rotate(frame,270)
        if debug:
            #print(frame)
            pass
        faces = extractFace(frame)
        for i in faces:
            (x, y, w, h) = i
            predicted = predict(
                cv2.cvtColor(crop(frame, i), cv2.COLOR_RGB2GRAY))
            if showImage:
                cv2.imshow(
                'Detected Face', cv2.cvtColor(crop(frame, i), cv2.COLOR_RGB2GRAY))
                if visualizeLBP:
                    cv2.imshow('LBP Histogram',lbp(cv2.cvtColor(crop(frame,i),cv2.COLOR_RGB2GRAY)
                    ,1,15))
            if debugStuff:
                print(predicted)
            if predicted[1] <= confidenceLevel and (showImage or outputImage):
                print 'FOUND LUCA FACE'
                cv2.rectangle(frame, (x, y), (x+w, y+h), (227, 45, 45), 2)
                servo.update(x+w/2, y+h/2)
                if debug:
                    print('Updating servo with coords:')
                    print(x+w/2-160,y+h/2-120)
                charactersToCutOff=len('/home/pi')+len("/The-Luca-Bazooka/training/")
                cv2.putText(
                    frame, folders[predicted[0]][charactersToCutOff:-1], (x, y), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255))
            if predicted[1] <= confidenceLevel and not (showImage or outputImage):
                servo.update(x+w/2-160, y+h/2-120)
                if debug:
                    print 'UPDATING SERVO WITH COORDS:'
                    print (x+w/2,y+h/2)
                    print 'FOUND LUCA FACE'
                    print 'CONFIDENCE START'
                    print (predicted[1])
                    print 'CONFIDENCE END'
            else:
                if debug:
                    print 'FOUND NON-LUCA FACE'
                    print (x,y,x+w,y+h)
                if showImage or outputImage:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 191, 255), 2)
        if outputImage:
            cv2.imwrite(outputImagePath+str(frameNumber)+'.jpg',frame)
        if showImage:
            cv2.imshow("The Luca Bazooka", frame)
        if outputToFile==True:
            video_writer.append_data(frame)
        rawCapture.truncate(0)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    if outputToFile==True:
        video_writer.close()
    vidcap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
#called when called like python pi-recognize.py
    main(trainingFolders)
