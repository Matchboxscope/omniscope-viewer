import socket
import multiprocessing
import cv2
import numpy as np
import time


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
        self.listen_port = listen_port
        self.buffer_size = buffer_size
        self.queue_size = queue_size
        self.width = width
        self.height = height

        self.q = multiprocessing.Queue(self.queue_size)
        self.camera_ports = set()
        self.canvas = Canvas()

    def camera_listener(self, port):
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Bind the socket to a specific IP address and port
        s.bind(('0.0.0.0', port))

        # Listen for incoming connections
        s.listen(1)

        # Wait for a client to connect
        client_socket, client_address = s.accept()
        print("Connected to client: ", client_address)
        timeLastFrame = time.time()
        while True:
            try:
                data = client_socket.recv(self.buffer_size)
            except Exception as e: 
                print(e)
                self.camera_ports.remove(port)
                break
            try:
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if time.time() - timeLastFrame > 10:
                    print("No frame received for 5 seconds.")
                    self.camera_ports.remove(port)
                    break
                if frame is not None:
                    self.q.put((port, frame))
                    timeLastFrame = time.time()
            except:
                pass 
        s.close()

    def display_frames(self):
        while True:
            if not self.q.empty():
                port, frame = self.q.get()
                frameID = port-8001
                self.canvas.add_frame(frame, frameID)
            concatenated_frame = self.canvas.get_canvas()
            
            cv2.imshow("Cameras", concatenated_frame)
            cv2.waitKey(1)
            time.sleep(.1)

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
                
                # send back the port number to the camera
                reply_int = 8000+iCameras
                reply_bytes = reply_int.to_bytes(4, byteorder='big')  # 4 bytes for a 32-bit integer
                conn.send(reply_bytes)
                
                camera_port = int(data.decode().strip())
                if camera_port not in self.camera_ports:
                    self.camera_ports.add(camera_port)
                    print(f"Received port {camera_port} from {addr[0]}:{addr[1]}")
                    p = multiprocessing.Process(target=self.camera_listener, args=(camera_port,))
                    p.start()
                    
        finally:
            server_socket.close()
            p_display.terminate()

if __name__ == '__main__':
    server = CameraDisplayServer()
    server.run()
