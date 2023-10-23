import socket
import multiprocessing
import cv2
import numpy as np
import time
import requests
import json
import multiprocessing.shared_memory as shm
import array

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
        self._manager = None
        self.cameraID_to_canvasID = None

        self.listen_port = listen_port
        self.buffer_size = buffer_size
        self.queue_size = queue_size
        self.width = width
        self.height = height
        self.timeoutLastFrame = 5
 
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
        

    @property
    def manager(self):
        if self._manager is None:
            self._manager = multiprocessing.Manager()
        return self._manager
        

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
        # check if port is already blocked 
        portInUse = self.is_port_in_use(port)
        # check if port is already in use, if so, stop the process and remove it from the queue
        if port in self.camera_ports and portInUse:
            print(f"Port {port} is already in use. Not spinning up camera.")
            return 
           
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         
        # Bind the socket to a specific IP address and port
        s.bind(('0.0.0.0', port))

        # Listen for incoming connections
        s.listen(1)

        # Wait for a client to connect
        client_socket, client_address = s.accept()
        print("Connected to client: ", client_address)
        
        # try retreiving the camera id by get-requesting IP/getId
        # Construct the URL
        url = f"http://{client_address[0]}/getId"

        # Make the GET request
        response = requests.get(url)

        # Print the response
        if response.status_code == 200:
            # convert json response to int
            cameraID = json.loads(response.text)["id"]
            print(f"Camera ID: {cameraID}")
            with lock:
                canvasID = self.getCanvasID(cameraID)
        else:
            print(f"Request failed with status code: {response.status_code}")
            
        timeLastFrame = time.time()
        while True:
            if port not in self.camera_ports:
                break
            try:
                data = client_socket.recv(self.buffer_size)
            except Exception as e: 
                print(e)
                self.camera_ports.remove(port)
                break
            try:
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if time.time() - timeLastFrame > self.timeoutLastFrame:
                    print("No frame received for 5 seconds.")
                    client_socket.close()
                    self.camera_ports.remove(port)
                    break
                if frame is not None:
                    self.q.put((canvasID, frame))
                    timeLastFrame = time.time()
            except:
                pass 
        s.close()
        try:self.camera_ports.remove(port)
        except:pass
        

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
            if not self.q.empty():
                canvasID, frame = self.q.get()
                self.canvas.add_frame(frame, canvasID)
            concatenated_frame = self.canvas.get_canvas()
            
            cv2.imshow("Cameras", concatenated_frame)
            cv2.waitKey(1)

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(24)  # Expecting up to 24 connections
        iCameras = 0
        print(f"Listening for cameras on port {self.listen_port}")

        # Start display process
        p_display = multiprocessing.Process(target=self.display_frames)
        p_display.start()
        

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
                print(f"Received from ESP: {camera_port}")
                
                self.camera_ports.add(camera_port)
                print(f"Received port {camera_port} from {addr[0]}:{addr[1]}")
                p = multiprocessing.Process(target=self.camera_listener, args=(camera_port,iCameras,self.lock,))

                p.start()
                    
        finally:
            server_socket.close()
            self.segment.close()
            self.segment.unlink()
            p_display.terminate()

if __name__ == '__main__':  
    server = CameraDisplayServer()
    server.run()
    