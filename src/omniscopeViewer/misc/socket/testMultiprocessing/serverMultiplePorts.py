'''
pip3 install opencv-python
pip3 install simple-websocket-server
'''
import socket
import multiprocessing
import cv2
import requests
import numpy as np
import time
import json
#import multiprocessing.shared_memory as shm
import array
#!pip install SimpleWebSocketServer
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import threading
import socket
import requests
import threading
import time 

DEBUG=False
class ESP32Scanner(object):

    def __init__(self):
        self.cameraURLs = []  # Initialize a list to store camera URLs
        self.cameraIDs = []  # Initialize a list to store camera IDs
        # Define the range of IP addresses to scan
        start_ip = 1
        end_ip = 255

        # Get all available host IP addresses
        allHostIpAdresses = self.get_all_ip_addresses()
        for ipAddress in allHostIpAdresses:
            # Base URL formation (excluding the last segment of the IP address)
            baseUrl = ".".join(ipAddress.split('.')[:-1]) + "."

            # Scanning IP addresses within the defined range
            scannedIPs = self.scan_ips(baseUrl, start_ip, end_ip)
            if DEBUG: print("Scanned IP addresses:", scannedIPs)

            # Create a list of URLs from the scanned IPs
            for iIP in scannedIPs:
                self.cameraURLs.append(iIP["IP"])
                self.cameraIDs.append(iIP["ID"])

    def get_all_ip_addresses(self):
        """
        Retrieves all IP addresses associated with the host machine.
        """
        ip_addresses = []

        # Get the host name
        host_name = socket.gethostname()

        # Get all IP addresses associated with the host name
        try:
            ip_addresses = socket.gethostbyname_ex(host_name)[-1]
        except socket.gaierror:
            pass  # Ignore errors in name resolution

        return ip_addresses


    def get_unique_id(self, server_ip):
        """
        Sends a GET request to the server to retrieve a unique ID.
        
        Args:
        - server_ip (str): The IP address of the ESP32 server.

        Returns:
        - int: The unique ID received from the server, or None if the request fails.
        """
        url = f"http://{server_ip}/getId"
        try:
            if DEBUG: print("Scanning IP:", server_ip)
            response = requests.get(url, timeout=0.5)
            response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code.

            # Assuming the server responds with a JSON in the format: {"id": "<uniqueId>"}
            data = response.json()
            return data.get("id")

        except Exception as e:
            pass
        return None
    
    def scan_ip(self, ip_address, results):
        """
        Scans a single IP address for a specific service and records if found.
        """
        try:
            responseID = self.get_unique_id(ip_address) 
            if responseID is not None:
                
                if DEBUG: print(f"Connected device found at IP: {ip_address}")
                if DEBUG: print("Status:", responseID)
                results.append({"IP": ip_address, "ID": responseID})

            else:
                if DEBUG: print(f"No device found at IP: {ip_address}")

        except requests.exceptions.RequestException:
            print(f"No response from IP: {ip_address}")

    def scan_ips(self, baseUrl, start_ip, end_ip):
        """
        Scans a range of IPs within the subnet to identify available devices.
        """
        results = []
        threads = []
        for i in range(start_ip, end_ip + 1):
            ip_address = baseUrl + str(i)
            thread = threading.Thread(target=self.scan_ip, args=(ip_address, results))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        return results

class CameraListener(WebSocket):

    @classmethod
    def setStartCameraThreadCallback(cls, callback):
        """Set a callback function at the class level."""
        cls._startCameraCallback = staticmethod(callback)
        
    def handleConnected(self):
        print(f"Port Announcer {self.address} connected")
        # return with an accept message
        self.sendMessage("accept".encode())
        
    def handleClose(self):
        print(f"Port Announcer  {self.address} closed")

    def handleMessage(self):
        if hasattr(self.__class__, '_startCameraCallback'):
            print(f"Announcing the port: {self.data}")
            self._startCameraCallback(self, self.data)
                

class CameraSocket(WebSocket):
    
    def __init__(self, server, sock, address):
        super().__init__(server, sock, address)
        self.tLastFrame = time.time()
        self.timeoutChecker = threading.Thread(target=self.checkTimeout)
        self.timeoutChecker.start()

    @classmethod
    def removePortCallback(cls, callback):
        cls._removePortCallback = staticmethod(callback)
          
    @classmethod
    def setFrameCallback(cls, callback):
        """Set a callback function at the class level."""
        cls._frameCallback = staticmethod(callback)

    def handleConnected(self):
        print(f"Client {self.address} connected")
        # try retreiving the camera id by get-requesting IP/getId
        # Construct the URL
        port = self.address[1]
        self.cameraID = port - 8000

    def handleClose(self):
        print(f"Client {self.address} closed")
        if hasattr(self.__class__, '_removePortCallback'):
            self._removePortCallback(self, self.cameraID)
       
    def handleMessage(self):
        self.tLastFrame = time.time()  # Update the time when a new frame is received
        
        # The data received is stored in self.data
        # Convert the bytes to numpy array and decode the image
        nparr = np.frombuffer(self.data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Display the image
        #cv2.imshow(f'Camera {self.address[1]}', image)  # Using port number as an ID
        #cv2.waitKey(1)
        # If a callback is set, call it
        if hasattr(self.__class__, '_frameCallback'):
            self._frameCallback(self, image)
            
    def checkTimeout(self):
        while True:
            time.sleep(1)  # Check every second
            if time.time() - self.tLastFrame > 3:
                self.close()

class Canvas:
    def __init__(self, width=320, height=240, rows=6, cols=4):
        self.cell_width = width
        self.cell_height = height
        self.rows = rows
        self.cols = cols

        # Create a black canvas
        self.canvas = np.zeros((height * rows, width * cols, 3), dtype=np.uint8)

    def add_frame(self, frame, id):
        if frame.shape[0] != self.cell_height or frame.shape[1] != self.cell_width:
            raise ValueError("Frame dimensions don't match cell dimensions.")

        if id < 0 or id > (self.rows * self.cols - 1):
            raise ValueError("Invalid ID. ID should be between 0 and 23.")

        row = id // self.cols
        col = id % self.cols

        start_y = row * self.cell_height
        end_y = start_y + self.cell_height

        start_x = col * self.cell_width
        end_x = start_x + self.cell_width

        self.canvas[start_y:end_y, start_x:end_x] = frame

    def get_canvas(self):
        return self.canvas


class CameraDisplayServer:

    def __init__(self, allCameraPorts=None, listen_port=3333, buffer_size=2**17, queue_size=100, width=320, height=240):
        # look-up table for camera IDs and their corresponding locations in the 24-tiled canvas
        self.cameraID_to_canvasID = None

        self.listen_port = listen_port
        self.buffer_size = buffer_size
        self.queue_size = queue_size
        self.width = width
        self.height = height
        self.timeoutLastFrame = 5
        self.iCameras = 0
        self.allCameraPorts = allCameraPorts

        # Create a shared memory segment
        # Create an array of 16-bit signed integers initialized to -1
        arr = array.array('h', [-1]*24)
        #self.segment = shm.SharedMemory(create=True, size=2*24)
        # Initialize all slots as -1 (or 255 in bytes)
        #self.segment.buf[:2*24] = arr.tobytes()

        self.q = multiprocessing.Queue(self.queue_size)
        self.camera_ports = set()
        self.canvas = Canvas()
        self.lock = multiprocessing.Lock()

    def frame_listener(self, port, cameraID, lock):
        '''
        here we start a socket server that waits for all frames that chime in 
        '''
        print("start the frame_listener")
        with lock:
            canvasID = self.getCanvasID(port-8000)

        def addToQueue(socket_instance, image=None):
            #print(f"Received image from {socket_instance.address}")
            #port = socket_instance.address[1]
            self.q.put((canvasID, image))
            
        def removePort(socket_instance, cameraID=1):
            print("Removing port %i", cameraID)
            
        # Set the callback for CameraSocket class
        CameraSocket.setFrameCallback(addToQueue)
        CameraSocket.removePortCallback(removePort)
        server = SimpleWebSocketServer('0.0.0.0', port, CameraSocket)
        print(f"Server started on port {port}")
        server.serveforever()

    def getCanvasID(self, cameraID):
        # we need to map the random, yet unique (per ESP) camera ID to the 0-23 canvas ID

        # Read shared memory data into an array
        if 0:
            arr = array.array('h')
            arr.frombytes(self.segment.buf[:])

            # check if cameraID is already in the shared memory
            for idx in range(24):
                if arr[idx] == cameraID:
                    print(f"CameraID {cameraID} already in canvasID {idx}")
                    return idx
            # if not, add it to the shared memory in an available slot
            for idx in range(24):
                if arr[idx] == -1:
                    arr[idx] = idx  # Just assigning idx for now, but you can use any value to mark it as used
                    # Write back the updated data to shared memory
                    self.segment.buf[:] = arr.tobytes()
                    print(f"Added cameraID {cameraID} to canvasID {idx}")
                    return idx
        return cameraID
    
    def display_frames(self):
        while True:
            while not self.q.empty():
                canvasID, frame = self.q.get()
                self.canvas.add_frame(frame, canvasID)
            concatenated_frame = self.canvas.get_canvas()

            cv2.imshow("Cameras", concatenated_frame)
            cv2.waitKey(1)
            

    def run(self):
        '''
        Here we start a socket server that listens to all cameras that are connecting and then start the
        display server in case a camera is connected. Additionally, we dispatch the port number and assign
        it to the Display ID in the 2D grid 
        '''
        
        def addToQueue(socket_instance, port=None):
            camera_port = int(port)
            if camera_port not in self.allCameraPorts:
                print(f"Received port {camera_port}")
                p = multiprocessing.Process(target=self.frame_listener, args=(camera_port+8000,self.iCameras,self.lock,))
                p.start()
                self.iCameras += 1
                self.allCameraPorts.append(camera_port)
            else: 
                print("camrea already connected ")

        # Start display process
        p_display = multiprocessing.Process(target=self.display_frames)
        p_display.start()
            
        # need to serve this forever 
        
        if self.allCameraPorts is not None:
            allProcesses = []
            # we have the ports available alreaady 
            for camera_port in self.allCameraPorts:
                print(f"Received port {camera_port}")
                allProcesses.append(multiprocessing.Process(target=self.frame_listener, args=(int(camera_port)+8000,self.iCameras,self.lock,)))
                allProcesses[-1].start()
                
            for p in allProcesses:
                p.join()
        else:                
            # Set the callback for CameraSocket class
            CameraListener.setStartCameraThreadCallback(addToQueue)
            CameraListenerServer = SimpleWebSocketServer('0.0.0.0', self.listen_port, CameraListener)
        
        
            print(f"Server started on port {self.listen_port}")
            CameraListenerServer.serveforever()
        
        

        '''
        finally:
            server_socket.close()
            self.segment.close()
            self.segment.unlink()
            p_display.terminate()
        '''
        
if __name__ == '__main__':
    scanner = ESP32Scanner()  # Create an instance of the scanner
    print("Detected Cameras:", scanner.cameraURLs)  # Print the detected camera URLs
    allCameraPorts = scanner.cameraIDs
    server = CameraDisplayServer(allCameraPorts)
    server.run()
