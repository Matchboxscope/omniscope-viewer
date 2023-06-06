import cv2
import requests
import numpy as np
import threading

def read_mjpeg(url):
    
        stream = requests.get(url, stream=True)#, timeout=)
        bytes_ = bytes()
        for chunk in stream.iter_content(chunk_size=1024):
            bytes_ += chunk
            a = bytes_.find(b'\xff\xd8')
            b = bytes_.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes_[a:b+2]
                bytes_ = bytes_[b+2:]
                try:
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    #import matplotlib.pyplot as plt
                    #plt.imshow(frame), plt.show()
                    print(np.mean(frame))
                except:
                    pass
                #cv2.imshow('MJPEG Frame', frame)
                #if cv2.waitKey(1) == 27:  # Press Esc key to exit
                #                break

    
# Specify the MJPEG stream URL
mjpeg_url = "http://192.168.43.235:81"

# Start a thread to read and display MJPEG frames
thread = threading.Thread(target=read_mjpeg, args=(mjpeg_url,))
thread.start()

# Wait for the thread to finish
thread.join()
