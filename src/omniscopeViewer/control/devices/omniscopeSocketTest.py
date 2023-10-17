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
import cv2
import numpy as np
import socket
import struct
import threading
import time
import cv2
import numpy as np
import socket
import struct


import cv2
import numpy as np
import socket
import struct
import threading
import time

class CameraServer:

    def __init__(self, npixelX, npixelY, nCameras):
        self.npixelX = npixelX
        self.npixelY = npixelY
        self.nCameras = nCameras

    def generate_frame(self, shiftX, shiftY):
        while True:
            frame = np.random.randint(0, 256, (self.npixelY-20, self.npixelX-20, 3), dtype=np.uint8)
            
            # ... (Other frame processing code remains the same)
            border_size = 10
            cv2.putText(frame, str(123), (shiftX,shiftY), cv2.FONT_HERSHEY_SIMPLEX, 
                        2, (255,255,255), 2, lineType=2)

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

            time.sleep(.01)
            yield jpeg.tobytes()
            time.sleep(.01)

    def send_frame(self, conn, shiftX, shiftY):
        for frame in self.generate_frame(shiftX, shiftY):
            size = len(frame)
            size_pack = struct.pack(">L", size)
            conn.sendall(size_pack)
            conn.sendall(frame)

    def start_server(self, port):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(5)
        print(f"Listening on port {port}")

        while True:
            conn, addr = server_socket.accept()
            print(f"Connection from {addr}")
            threading.Thread(target=self.send_frame, args=(conn, np.random.randint(50,150), np.random.randint(50,150))).start()

    def start_cameras(self):
        for i in range(self.nCameras):
            threading.Thread(target=self.start_server, args=(8001+i,)).start()


class MultiCameraCapture:
    def __init__(self, urls):
        self.urls = urls
        self.frames = [None] * len(urls)
        self.stop_event = threading.Event()

    def start(self):
        # Create and start a thread for each camera
        for i, url in enumerate(self.urls):
            print(f"Starting thread for camera {i}")
            t = threading.Thread(target=self._capture_frame, args=(url, i))
            t.start()

    def stop(self):
        # Set the stop event to terminate the threads
        self.stop_event.set()

    def _capture_frame(self, url, index):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(1)
        try:
            print(f"Connecting to url {url}")
            client_socket.connect(url)
        except socket.timeout:
            print(f"Connection attempt to url {url} timed out.")
            return
        except Exception as e:
            print(f"An error occurred while connecting to port {url}: {str(e)}")
            return
                    
        print(f"Connection to url {url} established")
        while not self.stop_event.is_set():
            # Receive the size of the frame
            size_pack = client_socket.recv(4)
            if not size_pack:
                break
            size = struct.unpack(">L", size_pack)[0]

            # Receive the frame
            frame_data = b""
            while len(frame_data) < size:
                more_data = client_socket.recv(size - len(frame_data))
                if not more_data:
                    break
                frame_data += more_data

            # Decode the frame
            frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)

            # Store the frame in the corresponding index
            self.frames[index] = frame

        client_socket.close()


    def get_concatenated_frame(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None
        width = frame_list[0].shape[1]
        height = frame_list[0].shape[0]
        num_frames = len(frame_list)
        rows = 4
        cols = 6

        # Create an empty grid to store the frames
         #grid = np.empty((0, frame_list[0].shape[1]*cols, 3), dtype=np.uint8)

        # Create a 4x6 numpy array to hold the images
        grid = np.zeros((rows, cols, height, width, 3), dtype=np.uint8)

        # Check if the number of frames matches the grid size
        #if num_frames != rows * cols:
        #    print('Error: Number of frames does not match the grid size.')
        #    return frame_list[0]
            
        # Loop through the ids from 0 to 23
        for i in range(num_frames):
            # Load the image with the corresponding id
            
            # Resize the image to 320x240
            try:
                img = frame_list[i]

                # Calculate the row and column indices for the image based on its id
                row = i // 6
                col = i % 6

                # Place the image in the corresponding position in the numpy array
                grid[row, col] = np.array(img)
            except Exception as e:
                print(e)
                
        # Concatenate frames row by row
        #for i in range(0, num_frames, cols):
        #    row = np.concatenate(frame_list[i:i + cols], axis=1)
        #    try:
        #        grid = np.concatenate((grid, row), axis=0)
        #    except:
        #        break
        
        
        # Get the dimensions of the input array
        N, M, X, Y, _ = grid.shape

        # Initialize an empty canvas
        canvas = np.empty((N * X, M * Y, 3), dtype=grid.dtype)

        # Concatenate the images along the N and M dimensions
        for i in range(N):
            for j in range(M):
                canvas[i * X:(i + 1) * X, j * Y:(j + 1) * Y, :] = grid[i, j, :, :, :]

        return canvas


    

class omniscopeSocketTest(ICamera):
    
    def __init__(self, name: str, deviceID: Union[str, int]) -> None:
        """omniscopeTest VideoCapture wrapper.

        Args:
            name (str): user-defined camera name.
            deviceID (Union[str, int]): camera identifier.
        """
        
        # start the fake mjpeg cameras (0.0.0.0:8001...80025)
        npixelX = 320
        npixelY = 240
        nCameras = 24

        camera_server = CameraServer(npixelX, npixelY, nCameras)
        camera_server.start_cameras()

        
        # URLs of the MJPEG streams
        stream_urls = []
        for i in range(nCameras):
            stream_urls.append(("localhost",8001+i))
    
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
        if frame is None or (frame.shape[0] == 0 and frame.shape[1] == 0):
            print("No frame")
        return frame
    
    def changeParameter(self, name: str, value: Any) -> None:
        pass 
    
    def changeROI(self, newROI: ROI):
        if newROI <= self.fullShape:
            self.roiShape = newROI
    
    def close(self) -> None:
        # Stop capturing frames
        self.capture.stop()
        
if __name__ == '__main__':
    
    npixelX = 320
    npixelY = 240
    nCameras = 24

    camera_server = CameraServer(npixelX, npixelY, nCameras)
    camera_server.start_cameras()

    
    allCameras = []
    for i in range(nCameras):
        allCameras.append(("localhost",8001+i))
    
    allCameras = MultiCameraCapture(allCameras)
    allCameras.start()
    time.sleep(1) # let cameras warm up
    while 1: #for iFrame in range(100):
        frame = allCameras.get_concatenated_frame()
        if frame is None or (frame.shape[0] == 0 and frame.shape[1] == 0):
            print("No frame")
            continue
        cv2.imshow("frame", frame)
        cv2.waitKey(1)
        time.sleep(0.01)
    
    allCameras.stop()
    