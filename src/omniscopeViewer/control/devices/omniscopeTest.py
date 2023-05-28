import cv2
import numpy as np
from dataclasses import replace
from omniscopeViewer.common import ROI, ColorType
from omniscopeViewer.control.devices.interface import (
    ICamera,
    NumberParameter,
    ListParameter
)
from typing import Union, Any
from sys import platform
import cv2
import numpy as np
from flask import Flask, Response
import threading
import time

''' DUMMY FRAME PRODUCER '''
app = Flask(__name__)
npixelX = 320
npixelY = 240

nCameras = 24

def run(port):
    app.run(host='0.0.0.0', port=port)
        
def startServer( mCameras):
    for i in range(mCameras):
        threading.Thread(target=run, args=(8001+i,)).start()

def generate_frame(shiftX, shiftY):
    
    while True:
        border_size = 10
        frame = np.random.randint(0, 256, (npixelY-2*border_size, npixelX-2*border_size, 3), dtype=np.uint8)
        font                   = cv2.FONT_HERSHEY_SIMPLEX
        bottomLeftCornerOfText = (shiftX,shiftY)
        fontScale              = 2
        fontColor              = (255,255,255)
        thickness              = 2
        lineType               = 2

        number=123
        cv2.putText(frame,str(number), 
            bottomLeftCornerOfText, 
            font, 
            fontScale,
            fontColor,
            thickness,
            lineType)

        border_size = 10
        frame = cv2.copyMakeBorder(
            frame,
            top=border_size,
            bottom=border_size,
            left=border_size,
            right=border_size,
            borderType=cv2.BORDER_CONSTANT,
            value=[255, 255, 255]
        )
        _, jpeg = cv2.imencode('.jpg', frame)
                
        time.sleep(.1)
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

@app.route('/')
def stream():
    return Response(generate_frame( np.random.randint(50,150), np.random.randint(50,150)), mimetype='multipart/x-mixed-replace; boundary=frame')


class MultiCameraCapture:
    def __init__(self, urls):
        self.urls = urls
        self.frames = [None] * len(urls)
        self.stop_event = threading.Event()

    def start(self):
        # Create and start a thread for each camera
        for i, url in enumerate(self.urls):
            t = threading.Thread(target=self._capture_frame, args=(i, url))
            t.start()

    def stop(self):
        # Set the stop event to terminate the threads
        self.stop_event.set()

    def _capture_frame(self, index, url):
        cap = cv2.VideoCapture(url)

        while not self.stop_event.is_set():
            # Read the frame from the camera
            ret, frame = cap.read()

            if ret:
                # Store the frame in the corresponding index
                self.frames[index] = frame
            else:
                self.frames[index] = np.zeros((npixelY, npixelX, 3), dtype=np.uint8)

    def get_concatenated_frame2(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None

        # Concatenate the frames horizontally
        concatenated_frame = np.concatenate(frame_list, axis=1)

        return concatenated_frame


    def get_concatenated_frame(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None

        num_frames = len(frame_list)
        rows = 4
        cols = 6

        # Check if the number of frames matches the grid size
        if num_frames != rows * cols:
            print('Error: Number of frames does not match the grid size.')

        # Create an empty grid to store the frames
        grid = np.empty((0, frame_list[0].shape[1]*cols, 3), dtype=np.uint8)

        # Concatenate frames row by row
        for i in range(0, num_frames, cols):
            row = np.concatenate(frame_list[i:i + cols], axis=1)
            try:
                grid = np.concatenate((grid, row), axis=0)
            except:
                break

        return grid


    

class omniscopeTest(ICamera):
    
    def __init__(self, name: str, deviceID: Union[str, int]) -> None:
        """omniscopeTest VideoCapture wrapper.

        Args:
            name (str): user-defined camera name.
            deviceID (Union[str, int]): camera identifier.
        """
        
        # start the fake mjpeg cameras (0.0.0.0:8001...80025)
        startServer(nCameras)
        
        # URLs of the MJPEG streams
        stream_urls = []
        for i in range(nCameras): 
            stream_urls.append('http://0.0.0.0:'+str(8001+i))

        # Create an instance of MultiCameraCapture
        self.capture = MultiCameraCapture(stream_urls)

        # Start capturing frames from the cameras asynchronously
        self.capture.start()

        # Wait for a while to capture frames
        time.sleep(1)

        # read omniscopeTest parameters
        width = npixelX
        height = npixelY
        
        # initialize region of interest
        # steps for height, width and offsets
        # are by default 1. We leave them as such
        sensorShape = ROI(offset_x=0, offset_y=0, height=height, width=width)
        
        parameters = {}

        # exposure time in omniscopeTest is treated differently on Windows, 
        # as exposure times may only have a finite set of values
        super().__init__(name, deviceID, parameters, sensorShape)
        
    def setAcquisitionStatus(self, started: bool) -> None:
        pass
    
    def grabFrame(self) -> np.ndarray:
        # Read the first frame
        # Get the concatenated frame
        frame = self.capture.get_concatenated_frame()
        return frame
    
    def changeParameter(self, name: str, value: Any) -> None:
        pass 
    
    def changeROI(self, newROI: ROI):
        if newROI <= self.fullShape:
            self.roiShape = newROI
    
    def close(self) -> None:
        # Stop capturing frames
        self.capture.stop()
        