import cv2
import numpy as np
from omniscopeViewer.control.devices import omniscope

# Create an instance of the OmniScope camera
camera = omniscope.omniscope("OmniScope Camera", 0)

# Set acquisition status to start capturing frames
camera.setAcquisitionStatus(True)

try:
    while True:
        # Continuously grab frames
        frame = camera.grabFrame()

        # Display the frame in a cv2 window
        cv2.imshow("OmniScope Frame", np.uint8(frame/np.max(frame)*255))

        # Check for user input to exit the loop
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

finally:
    # Release the camera and close the cv2 window
    camera.close()
    cv2.destroyAllWindows()
