import socket
import cv2
import numpy as np
import time
from multiprocessing import Process
import uuid



def simulate_camera(ip, port, id):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))

        while True:
            # Generate a random image of size 320x240
            img = np.random.randint(0, 256, (240, 320, 3), dtype=np.uint8)

            # add black bounding box using cv2
            cv2.rectangle(img, (10, 10), (310, 230), (0, 0, 0), 1)
            
            # add text to image using cv2
            cv2.putText(img, f"Camera {id}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            # Convert the image to JPEG format for sending
            ret, buffer = cv2.imencode('.jpg', img)
            
            # here we need to modify the buffer to include the camera ID, we use the first byte
            # to store the camera ID
            buffer[9] = id

            # Send the length of the frame first
            s.sendall(len(buffer).to_bytes(4, byteorder='big'))

            # Send the frame
            s.sendall(buffer.tobytes())

            # Delay to simulate frame rate, e.g., 30fps would be a delay of approx. 1/30 seconds.
            time.sleep(1/30)

if __name__ == "__main__":
    # Server details
    ip = "127.0.0.1"
    port = 12345
    nCameras = 24

    # Start 4 simulated cameras
    processes = [Process(target=simulate_camera, args=(ip, port, id)) for id in range(nCameras)]
    for p in processes:
        p.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        for p in processes:
            p.terminate()
