import asyncio
import websockets
import binascii
from io import BytesIO
import numpy as np 
import cv2

from PIL import Image, UnidentifiedImageError

def is_valid_image(image_bytes):
    try:
        Image.open(BytesIO(image_bytes))
        return True
    except UnidentifiedImageError:
        print("image invalid")
        return False

async def handle_connection(websocket, path):
    while True:
        try:
            message = await websocket.recv()
            ip, port = websocket.remote_address
            if len(message) > 5000:
                  if is_valid_image(message):
                    #print(message)
                    # we want to convert the message into a jpeg encoded numpy array and display it using cv2
                    mImage = cv2.imdecode(np.frombuffer(message, np.uint8), cv2.IMREAD_COLOR)
                    #print(mImage[10:12,10:12])
                    cv2.imshow(ip, mImage)
                    cv2.waitKey(1)  # This allows the frame to be displayed for 1ms before the next frame
                    #with open("image.jpg", "wb") as f:
                    #      f.write(message)


        except websockets.exceptions.ConnectionClosed:
            break

async def main():
    server = await websockets.serve(handle_connection, '0.0.0.0', 12345)
    await server.wait_closed()

asyncio.run(main())
