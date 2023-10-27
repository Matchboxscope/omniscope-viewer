import socket
import multiprocessing
import cv2
import requests
import numpy as np
import time
import json
import multiprocessing.shared_memory as shm
import array
#!pip install SimpleWebSocketServer
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import threading

class CameraListener(WebSocket):

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

    def handleMessage(self):
        self.tLastFrame = time.time()  # Update the time when a new frame is received
        print(self.data)
       
        # If a callback is set, call it
        if hasattr(self.__class__, '_frameCallback'):
                self._frameCallback(self, self.data)
                

class CameraSocket(WebSocket):
    
    def __init__(self, server, sock, address):
        super().__init__(server, sock, address)
        self.tLastFrame = time.time()
        self.timeoutChecker = threading.Thread(target=self.checkTimeout)
        self.timeoutChecker.start()

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

    def __init__(self, listen_port=3333, buffer_size=2**17, queue_size=100, width=320, height=240):
        # look-up table for camera IDs and their corresponding locations in the 24-tiled canvas
        self.cameraID_to_canvasID = None

        self.listen_port = listen_port
        self.buffer_size = buffer_size
        self.queue_size = queue_size
        self.width = width
        self.height = height
        self.timeoutLastFrame = 5
        self.iCameras = 0

        # Create a shared memory segment
        # Create an array of 16-bit signed integers initialized to -1
        arr = array.array('h', [-1]*24)
        self.segment = shm.SharedMemory(create=True, size=2*24)
        # Initialize all slots as -1 (or 255 in bytes)
        self.segment.buf[:2*24] = arr.tobytes()

        self.q = multiprocessing.Queue(self.queue_size)
        self.camera_ports = set()
        self.canvas = Canvas()
        self.lock = multiprocessing.Lock()

    @staticmethod
    def is_port_in_use(port):
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Attempt to bind the socket to the port
            s.bind(('0.0.0.0', port))
            return False  # Port is available
        except OSError:
            return True  # Port is already in use
        finally:
            s.close()  # Close the socket

    def camera_listener(self, port, cameraID, lock):
        print("start the camera_listener")
        with lock:
            canvasID = self.getCanvasID(port-8000)

        def addToQueue(socket_instance, image=None):
            #print(f"Received image from {socket_instance.address}")
            #port = socket_instance.address[1]
            self.q.put((canvasID, image))
            
        # Set the callback for CameraSocket class
        CameraSocket.setFrameCallback(addToQueue)
        server = SimpleWebSocketServer('0.0.0.0', port, CameraSocket)
        print(f"Server started on port {port}")
        server.serveforever()

    def getCanvasID(self, cameraID):
        # we need to map the random, yet unique (per ESP) camera ID to the 0-23 canvas ID

        # Read shared memory data into an array
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


    def display_frames(self):
        while True:
            while not self.q.empty():
                canvasID, frame = self.q.get()
                self.canvas.add_frame(frame, canvasID)
            concatenated_frame = self.canvas.get_canvas()

            cv2.imshow("Cameras", concatenated_frame)
            cv2.waitKey(1)
            

    def run(self):
        
        def addToQueue(socket_instance, port=None):
            #print(f"Received image from {socket_instance.address}")
            #port = socket_instance.address[1]
            
            camera_port = int(port)
            print(f"Received port {camera_port}")
            p = multiprocessing.Process(target=self.camera_listener, args=(camera_port,self.iCameras,self.lock,))
            p.start()
            self.iCameras += 1

        # Start display process
        p_display = multiprocessing.Process(target=self.display_frames)
        p_display.start()
            
        # Set the callback for CameraSocket class
        CameraListener.setFrameCallback(addToQueue)
        CameraListenerServer = SimpleWebSocketServer('0.0.0.0', self.listen_port, CameraListener)
        
        
        print(f"Server started on port {self.listen_port}")
        CameraListenerServer.serveforever()
        
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(24)  # Expecting up to 24 connections
        iCameras = 0
        print(f"Listening for cameras on port {self.listen_port}")



        try:
            while True:
                iCameras += 1
                conn, addr = server_socket.accept()
                data = conn.recv(self.buffer_size)
                print(f"Incoming connecton from {addr}")

                # send back the port number to the camera
                #camera_port = 8000+iCameras
                #conn.send(str(camera_port).encode())

                try:
                    camera_port  = int(data.decode().strip())
                except Exception as e:
                    print(e)
                    continue


                p.start()

        finally:
            server_socket.close()
            self.segment.close()
            self.segment.unlink()
            p_display.terminate()

if __name__ == '__main__':
    server = CameraDisplayServer()
    server.run()
