import cv2
import numpy as np
from multiprocessing import Process, Queue, Value
import websockets
import asyncio

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
    



class CameraServer:
    def __init__(self, max_cameras=1):
        self.max_cameras = max_cameras
        self.queues = [Queue() for _ in range(max_cameras)]
        self.next_queue_idx = Value('i', 0)
        self.canvas = Canvas()

    async def camera_listener(self):
        server = await websockets.serve(self.handle_camera, "0.0.0.0", 12345)
        await server.wait_closed()

    async def handle_camera(self, websocket, path):
        if self.next_queue_idx.value >= self.max_cameras:
            print("Max cameras reached.")
            return

        q = self.queues[self.next_queue_idx.value]
        current_idx = self.next_queue_idx.value
        self.next_queue_idx.value += 1

        while True:
            try:
                frame_data = await websocket.recv()
                if not frame_data: break
                
                # Extract the encoded ID from the 10th byte of the frame data
                decoded_id = frame_data[9]
                if decoded_id > 23:
                    decoded_id = 0
                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                frame[0][0][0] = decoded_id
                
                q.put(frame)

            except Exception as e:
                print(f"Error occurred for camera {current_idx}: {e}")
                break
    def run(self):
        listener = Process(target=self.start_asyncio_loop)
        listener.start()

        while True:
            frames = [q.get() for q in self.queues if not q.empty()]
            if frames:
                try:
                    for frame in frames:
                        frameID = frame[0][0][0]
                        self.canvas.add_frame(frame, frameID)
                    concatenated_frame = self.canvas.get_canvas()
                    cv2.imshow("Concatenated Frames", concatenated_frame)
                except:
                    pass
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        listener.terminate()
        cv2.destroyAllWindows()

    def start_asyncio_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.camera_listener())
        loop.close()

if __name__ == "__main__":
    server = CameraServer()
    server.run()
