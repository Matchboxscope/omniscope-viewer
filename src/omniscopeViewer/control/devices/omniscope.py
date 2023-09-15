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
import cv2
import numpy as np
import threading
import time
import requests
import requests
import threading
import os
import imageio
import socket
import datetime
            
''' DUMMY FRAME PRODUCER '''

npixelX = 320
npixelY = 240

nCameras = 24

class MultiCameraCapture:
    def __init__(self, urls):
        self.urls = urls
        self.frames = [None] * len(urls)
        self.isRunning = False
        self.HDframes = [None] * len(urls)

    def start(self):
        self.streamingThreads = []
        # Create and start a thread for each camera
        if not self.isRunning:
            for i, url in enumerate(self.urls):
                self.streamingThreads.append(threading.Thread(target=self._capture_frame, args=(i, url)))
                self.streamingThreads[-1].start()

    def stop(self):
        # Set the stop event to terminate the threads
        self.isRunning = False
        # wait until all threads have terminated
        for t in self.streamingThreads:
            t.join()
        
    def _capture_frame(self, index, url):
        self.isRunning = True
        while self.isRunning:
            try:
                stream = requests.get(url+":81", stream=True)#, timeout=)
                bytes_ = bytes()
                for chunk in stream.iter_content(chunk_size=8*1024):
                    bytes_ += chunk
                    a = bytes_.find(b'\xff\xd8')
                    b = bytes_.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = bytes_[a:b+2]
                        bytes_ = bytes_[b+2:]
                        try:
                            self.frames[index] = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            #print(np.mean(self.frames[index]))
                            #time.sleep(.1) # limit fps
                        except:
                            pass #self.frames[index] = np.zeros((npixelY, npixelX, 3), dtype=np.uint8)
                        if not self.isRunning:
                            break
            except (requests.exceptions.RequestException) as e:
                print("Error occurred:", e)
                print("Reconnecting in 5 seconds...")
                time.sleep(1)

    def snap(self, output_directory="downloaded_frames"):
        
        # Create a directory to store the downloaded frames
        # FIXME: Hardcoded location - we want that adaptable!
        os.makedirs(output_directory, exist_ok=True)
        os.chdir(output_directory)

        # initiate a download high-res image from each camera
        threads = []
        
        for i, url in enumerate(self.urls):
            thread = threading.Thread(target=self.download_jpeg, args=(i, url))
            thread.start()
            threads.append(thread)
  
        # Wait for all threads to finish
        for thread in threads:
            thread.join()   
        return self.HDframes
    
    def download_jpeg(self, index, url):
        url = url+"/capture"
        mImage = imageio.imread(url) 
        if type(mImage)==np.ndarray:
            # adding timestamp to filename
            timeStamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = timeStamp+"_"+url.split("/")[-1]+".jpeg"
            self.HDframes[index] = mImage
            
            # save image
            cv2.imwrite(filename, mImage)

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
        #FIXME: What if we scan a second time? Napari will crash!
        # FIXME: What if we have LAN and WIFI or multiple WIFI and therefore multiple addresses?
        # URLs of the MJPEG streams
        cameraURLs = []
        
        # Define the range of IP addresses to scan
        start_ip = 1
        end_ip = 255

        # get all available host ip addresses
        allHostIpAdresses = self.get_all_ip_addresses()
        for ipAddress in allHostIpAdresses:
            baseUrl = ""
            mHostname = ipAddress.split('.')[0:-1]
            for i in mHostname:
                baseUrl += i + '.'
            streamingPort = 81
            scannedIPs = self.scan_ips(baseUrl, start_ip, end_ip)
            print("Scanned IP addresses:", scannedIPs)

            # Create a list of URLs from the scanned IPs
            for iIP in scannedIPs: 
                cameraURLs.append(iIP["IP"])

        # Create an instance of MultiCameraCapture
        self.capture = MultiCameraCapture(cameraURLs)

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
        if started:
            # Start capturing frames from the cameras asynchronously
            self.capture.start()

            # Wait for a while to capture frames
            time.sleep(1)
        else:
            self.capture.stop()
    
    def grabFrame(self, isSnap=False) -> np.ndarray:
        # Read the first frame
        # Get the concatenated frame
        if isSnap:
            frame = self.capture.snap()
        else:
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
    

    def get_all_ip_addresses(self):
        ip_addresses = []
        
        # Get the host name
        host_name = socket.gethostname()
        
        # Get all IP addresses associated with the host name
        try:
            ip_addresses = socket.gethostbyname_ex(host_name)[-1]
        except socket.gaierror:
            pass  # Handle any exceptions here if needed
        
        return ip_addresses
    
    def scan_ip(self, ip_address, results):
        url = f"http://{ip_address}/status"

        try:
            # below 5s we will likely miss devices!
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                omniscopeID = response.json()['omniscope']
                omniscopeIP = response.json()['stream_url'].split(":8")[0]
                
                print(f"Connected device found at IP: {ip_address}")
                print("Status:", data)
                results.append({"IP":omniscopeIP,
                    "ID":omniscopeID})  # Store the scanned IP address in the results list

            else:
                print(f"No device found at IP: {ip_address}")


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

