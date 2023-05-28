import cv2
import numpy as np
import threading
import time

npixelY = 240
npixelX = 320

class MultiCameraCapture:
    def __init__(self, urls):
        self.urls = urls
        self.frames = [None] * len(urls)
        self.stop_event = threading.Event()

    def start(self):
        # Create and start a thread for each camera
        for i, url in enumerate(self.urls):
            t = threading.Thread(target=self._capture_frame, args=(i, url))
            t.start()

    def stop(self):
        # Set the stop event to terminate the threads
        self.stop_event.set()

    def _capture_frame(self, index, url):
        cap = cv2.VideoCapture(url)

        while not self.stop_event.is_set():
            # Read the frame from the camera
            ret, frame = cap.read()

            if ret:
                # Store the frame in the corresponding index
                self.frames[index] = frame
            else:
                self.frames[index] = np.zeros((npixelY, npixelX, 3), dtype=np.uint8)

    def get_concatenated_frame2(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None

        # Concatenate the frames horizontally
        concatenated_frame = np.concatenate(frame_list, axis=1)

        return concatenated_frame

    def get_concatenated_frame(self):
        # Create a list of frames from all cameras
        frame_list = [frame for frame in self.frames if frame is not None]

        if len(frame_list) == 0:
            return None

        num_frames = len(frame_list)
        rows = 4
        cols = 6

        # Check if the number of frames matches the grid size
        if num_frames != rows * cols:
            print('Error: Number of frames does not match the grid size.')
            return None

        # Create an empty grid to store the frames
        grid = np.empty((0, frame_list[0].shape[1]*cols, 3), dtype=np.uint8)

        # Concatenate frames row by row
        for i in range(0, num_frames, cols):
            row = np.concatenate(frame_list[i:i + cols], axis=1)
            grid = np.concatenate((grid, row), axis=0)

        return grid


# Example usage
if __name__ == '__main__':
    # URLs of the three MJPEG streams
    nCameras = 24
    stream_urls = []
    for i in range(nCameras): 
        stream_urls.append('http://0.0.0.0:'+str(8001+i))

    # Create an instance of MultiCameraCapture
    capture = MultiCameraCapture(stream_urls)

    # Start capturing frames from the cameras asynchronously
    capture.start()

    # Wait for a while to capture frames
    time.sleep(1)

    for _ in range(10):
        # Get the concatenated frame
        concatenated_frame = capture.get_concatenated_frame()

        if concatenated_frame is not None:
            # Display the concatenated frame
            cv2.imshow('Concatenated Frame', concatenated_frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    # Stop capturing frames
    capture.stop()
