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
import requests
import requests
import threading
import os

''' DUMMY FRAME PRODUCER '''
app = Flask(__name__)
npixelX = 320
npixelY = 240

nCameras = 24

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
        while True:
            try:
                stream = requests.get(url+":81", stream=True)#, timeout=)
                bytes_ = bytes()
                for chunk in stream.iter_content(chunk_size=1024):
                    bytes_ += chunk
                    a = bytes_.find(b'\xff\xd8')
                    b = bytes_.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = bytes_[a:b+2]
                        bytes_ = bytes_[b+2:]
                        try:
                            self.frames[index] = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            print(np.mean(self.frames[index]))
                            time.sleep(.1) # limit fps
                        except:
                            self.frames[index] = np.zeros((npixelY, npixelX, 3), dtype=np.uint8)
            except (requests.exceptions.RequestException) as e:
                print("Error occurred:", e)
                print("Reconnecting in 5 seconds...")
                time.sleep(1)


    def download_jpeg(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            content = response.content
            filename = url.split("/")[-1]
            with open(filename, "wb") as f:
                f.write(content)
            print(f"Downloaded: {filename}")

    def download_frames(self, urls):
        threads = []
        for url in urls:
            thread = threading.Thread(target=self.download_jpeg, args=(url,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to finish
        for thread in threads:
            thread.join()
    
    
            # Create a directory to store the downloaded frames
            output_directory = "downloaded_frames"
            os.makedirs(output_directory, exist_ok=True)
            os.chdir(output_directory)

            # Specify the list of URLs
            url_list = [
                "http://example.com/capture1.jpeg",
                "http://example.com/capture2.jpeg",
                "http://example.com/capture3.jpeg"
            ]
            # Create a list of URLs from the scanned IPs
            for iIP in scannedIPs: 
                stream_urls.append(iIP["IP"]+":"+str(streamingPort))



            self.download_frames(url_list)
        
             

    def get_concatenated_frame(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None

        rows = 4
        cols = 6
        
        # fill up with dummy frames
        for _ in range(rows*cols- len(frame_list)):
            frame_list.append(np.zeros((npixelY, npixelX, 3), dtype=np.uint8))
        num_frames = len(frame_list)

        # FIXME: Need to assign IDs to x/y locations..
        
        # Check if the number of frames matches the grid size
        if num_frames != rows * cols:
            print('Error: Number of frames does not match the grid size.')

        # Create an empty grid to store the frames
        grid = np.zeros((0, frame_list[0].shape[1]*cols, 3), dtype=np.uint8)

        # Concatenate frames row by row
        for i in range(0, num_frames, cols):
            row = np.concatenate(frame_list[i:i + cols], axis=1)
            try:
                grid = np.concatenate((grid, row), axis=0)
            except:
                break

        return grid


    

class omniscope(ICamera):
    
    def __init__(self, name: str, deviceID: Union[str, int]) -> None:
        """omniscope VideoCapture wrapper.

        Args:
            name (str): user-defined camera name.
            deviceID (Union[str, int]): camera identifier.
        """
        
        # URLs of the MJPEG streams
        stream_urls = []
        
        # Define the range of IP addresses to scan
        start_ip = 1
        end_ip = 255

        baseUrl = "192.168.43."
        streamingPort = 81
        scannedIPs = self.scan_ips(baseUrl, start_ip, end_ip)
        print("Scanned IP addresses:", scannedIPs)

        # Create a list of URLs from the scanned IPs
        for iIP in scannedIPs: 
            stream_urls.append(iIP["IP"]+":"+str(streamingPort))

        # Create an instance of MultiCameraCapture
        self.capture = MultiCameraCapture(stream_urls)

        # Start capturing frames from the cameras asynchronously
        self.capture.start()

        # Wait for a while to capture frames
        time.sleep(1)

        # read omniscope parameters
        width = npixelX
        height = npixelY
        
        # initialize region of interest
        # steps for height, width and offsets
        # are by default 1. We leave them as such
        sensorShape = ROI(offset_x=0, offset_y=0, height=height, width=width)
        
        parameters = {}

        # exposure time in omniscope is treated differently on Windows, 
        # as exposure times may only have a finite set of values
        super().__init__(name, deviceID, parameters, sensorShape)
        
    def setAcquisitionStatus(self, started: bool) -> None:
        pass
    
    def grabFrame(self, isSnap=False) -> np.ndarray:
        # Read the first frame
        # Get the concatenated frame
        
        if isSnap:
            self.capture.downloadFrames()
            
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
    
    def scan_ip(self, ip_address, results):
        url = f"http://{ip_address}/status"

        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                omniscopeID = response.json()['omniscope']
                omniscopeIP = response.json()['stream_url'].split(":8")[0]
                
                print(f"Connected device found at IP: {ip_address}")
                print("Status:", data)
            else:
                print(f"No device found at IP: {ip_address}")

            results.append({"IP":omniscopeIP,
                                "ID":omniscopeID})  # Store the scanned IP address in the results list

        except requests.exceptions.RequestException:
            print(f"No response from IP: {ip_address}")

    # scan all ips to retreive streaming URLs
    def scan_ips(self, baseUrl, start_ip, end_ip):
        results = []  # List to store the scanned IP addresses
        threads = []
        for i in range(start_ip, end_ip + 1):
            ip_address = baseUrl+str(i)
            thread = threading.Thread(target=self.scan_ip, args=(ip_address, results))
            thread.start()
            threads.append(thread)

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        return results

