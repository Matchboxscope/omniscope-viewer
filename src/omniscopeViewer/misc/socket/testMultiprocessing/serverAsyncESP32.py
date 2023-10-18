import asyncio
import websockets
from io import BytesIO
import numpy as np 
import cv2
from PIL import Image, UnidentifiedImageError

class CameraServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.cameras = {}  # To store the latest image from each camera based on IP

    @staticmethod
    def is_valid_image(image_bytes):
        try:
            Image.open(BytesIO(image_bytes))
            return True
        except UnidentifiedImageError:
            print("image invalid")
            return False

    async def handle_connection(self, websocket, path):
        ip, _ = websocket.remote_address
        while True:
            try:
                message = await websocket.recv()
                if len(message) > 5000 and self.is_valid_image(message):
                    try:
                        mImage = cv2.imdecode(np.frombuffer(message, np.uint8), cv2.IMREAD_COLOR)
                        self.cameras[ip] = mImage  # Store the image based on the IP address
                    except:
                        pass
            except websockets.exceptions.ConnectionClosed:
                if ip in self.cameras:
                    del self.cameras[ip]  # Remove camera if connection is closed
                break

    async def display_images(self):
        while True:
            for ip, img in self.cameras.items():
                cv2.imshow(ip, img)
            cv2.waitKey(1)
            await asyncio.sleep(0.01)  # Sleep a bit to avoid excessive CPU usage

    async def start(self):
        server = websockets.serve(self.handle_connection, self.host, self.port)

        # Using the correct method to wait for server to close based on the version
        await asyncio.gather(server, self.display_images())
        
if __name__ == '__main__':
    camera_server = CameraServer()
    asyncio.run(camera_server.start())
