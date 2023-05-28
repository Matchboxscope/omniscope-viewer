import cv2
import numpy as np
from flask import Flask, Response
import threading
import time
app = Flask(__name__)

npixelX = 320
npixelY = 240

def generate_frame(number, shiftX, shiftY):
    
    while True:
        
        border_size = 10

        frame = np.random.randint(0, 256, (npixelY-2*border_size, npixelX-2*border_size, 3), dtype=np.uint8)
        font                   = cv2.FONT_HERSHEY_SIMPLEX
        bottomLeftCornerOfText = (shiftX,shiftY)
        fontScale              = 2
        fontColor              = (255,255,255)
        thickness              = 2
        lineType               = 2

        cv2.putText(frame,str(number), 
            bottomLeftCornerOfText, 
            font, 
            fontScale,
            fontColor,
            thickness,
            lineType)
        frame = cv2.copyMakeBorder(
            frame,
            top=border_size,
            bottom=border_size,
            left=border_size,
            right=border_size,
            borderType=cv2.BORDER_CONSTANT,
            value=[255, 255, 255]
        )
        _, jpeg = cv2.imencode('.jpg', frame)
                
        time.sleep(.1)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

@app.route('/')
def stream():
    port = app.config['port']
    return Response(generate_frame(port, np.random.randint(50,150), np.random.randint(50,150)), mimetype='multipart/x-mixed-replace; boundary=frame')

def run(port):
    app.config['port'] = port
    app.run(host='0.0.0.0', port=port)
        
if __name__ == '__main__':
    for i in range(24):
        threading.Thread(target=run, args=(8001+i,)).start()