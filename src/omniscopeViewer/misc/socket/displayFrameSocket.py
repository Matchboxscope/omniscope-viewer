import asyncio
import websockets
import cv2
import numpy as np

async def frame_processor(websocket, path):
    while True:
        # Receive frame from ESP32 as binary
        data = await websocket.recv()

        # The first 12 bytes appear to contain some ID. Let's skip them.
        jpg_data = data[12:]

        # Convert binary data to numpy array
        nparr = np.frombuffer(jpg_data, np.uint8)

        # Decode numpy array to image
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Display image using OpenCV
        cv2.imshow('ESP32 Cam', img)
        cv2.waitKey(1)  # This allows the frame to be displayed for 1ms before the next frame

start_server = websockets.serve(frame_processor, "localhost", 8888)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
