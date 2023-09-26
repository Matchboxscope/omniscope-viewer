import cv2
import numpy as np
from dataclasses import replace
from omniscopeViewer.common import ROI, ColorType
from omniscopeViewer.control.devices.interface import (
    ICamera,
    NumberParameter,
    ListParameter
)
from typing import Union, Any
import cv2
import numpy as np
import time
import NanoImagingPack as nip      
import serial
import time
import serial.tools.list_ports
import numpy as np
import cv2
import math
import base64


npixelX = 320
npixelY = 240

nCameras = 24


class esp32camserial(ICamera):
    
    def __init__(self, name: str, deviceID: Union[str, int]) -> None:
        """ESP32 camera serial wrapper.

        Args:
            name (str): user-defined camera name.
            deviceID (Union[str, int]): camera identifier.
        """
        # read omniscope parameters
        width = npixelX
        height = npixelY
        
        # hologram reconstruction parameters
        self.dz = 0
        
        # initialize region of interest
        # steps for height, width and offsets
        # are by default 1. We leave them as such
        sensorShape = ROI(offset_x=0, offset_y=0, height=height, width=width)
        parameters = {}

        # open camera and start the frame-stream        
        self.camera = ESPCamera(manufacturer='Espressif')
        
        # initialize parameters
        parameters["Exposure time"] = NumberParameter(value=100., 
                                                        unit="ms",
                                                        valueLimits=(0, 1200), 
                                                        editable=True),
        parameters["Gain"] = NumberParameter(value=0., unit="a.u.",
                                                        valueLimits=(0, 30),
                                                        editable=True),
        parameters["Refocussing Distance"] = NumberParameter(value=0., unit="mum",
                                                        valueLimits=(0, 1000),
                                                        editable=True)
       
        # exposure time in omniscope is treated differently on Windows, 
        # as exposure times may only have a finite set of values
        super().__init__(name, deviceID, parameters, sensorShape)
        
    def setAcquisitionStatus(self, started: bool) -> None:
        pass 
    
    def grabFrame(self, isSnap=False) -> np.ndarray:
        # Read the first frame
        # Get the concatenated frame
        frame = self.camera.get_frame()
        if self.dz>0:
            frame = self.computeHoloImage(frame)
        return frame

    def changeParameter(self, name: str, value: Any) -> None:
        if name == "Exposure time":
            value = self.camera.set_exposure_time(value)
        elif name == "Gain":
            value = self.camera.set_analog_gain(value)
        elif name == "Refocussing Dis":
            self.dz = value*1e-3
            self.setHoloRefocusDistance(self.dz)
        else:
            raise ValueError(f"Unrecognized value \"{value}\" for parameter \"{name}\"")
    
    def changeROI(self, newROI: ROI):
        if newROI <= self.fullShape:
            self.roiShape = newROI
    
    def close(self) -> None:
        # Stop capturing frames
        self.camera.close()
        
    def setHoloRefocusDistance(self, dz):
        self.dz = dz

    def reconholo(self, image, PSFpara, N_subroi=1024, pixelsize=1e-3, dz=50e-3):
        mimage = nip.image(np.sqrt(image))
        mimage = nip.extract(mimage, [N_subroi,N_subroi])
        mimage.pixelsize=(pixelsize, pixelsize)
        mpupil = nip.ft(mimage)         
        #nip.__make_propagator__(mpupil, PSFpara, doDampPupil=True, shape=mpupil.shape, distZ=dz)
        cos_alpha, sin_alpha = nip.cosSinAlpha(mimage, PSFpara)
        PhaseMap = nip.defocusPhase(cos_alpha, dz, PSFpara)
        propagated = nip.ft2d((np.exp(1j * PhaseMap))*mpupil)
        return np.squeeze(propagated)

    def computeHoloImage(self, image):
        self.valueRangeMin=0
        self.valueRangeMax=0
        self.pixelsize = 3.45*1e-6   
        self.mWavelength = 488*1e-9
        self.NA=.3
        self.k0 = 2*np.pi/(self.mWavelength)

        self.PSFpara = nip.PSF_PARAMS()
        self.PSFpara.wavelength = self.mWavelength
        self.PSFpara.NA=self.NA
        self.PSFpara.pixelsize = self.pixelsize

        # Prepare image computation worker
        holorecon = np.flip(np.abs(self.reconholo(image, PSFpara=self.PSFpara, N_subroi=1024, pixelsize=self.pixelsize, dz=self.dz)),1)
            
        return holorecon

    


class ESPCamera:
    def __init__(self, manufacturer="Espressif"):
        self.manufacturer = manufacturer
        self.serialdevice = self.connect_to_usb_device()
        self.init_cam()
        self.frame = None
        self.frame_index = 0
        self.frame_index_last = -1 
        self.iError = 0
        self.newCommand = ""

    def connect_to_usb_device(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.manufacturer == self.manufacturer or port.manufacturer == "Microsoft":
                try:
                    ser = serial.Serial(port.device, baudrate=2000000, timeout=1)
                    print(f"Connected to device: {port.description}")
                    ser.write_timeout = 1
                    return ser
                except serial.SerialException:
                    print(f"Failed to connect to device: {port.description}")
        print("No matching USB device found.")
        return None
    
    def close(self):
        if self.serialdevice is not None:
            self.serialdevice.close()

    @staticmethod
    def calculate_base64_length(width, height):
        num_bytes = width * height
        base64_length = math.ceil((num_bytes * 4) / 3)
        base64_length = base64_length + (4 - base64_length % 4) % 4
        return base64_length

    def init_cam(self):
        if self.serialdevice is not None:
            self.serialdevice.write(('t10\n').encode())
            while self.serialdevice.read(): # clear the buffer
                pass

    def set_exposure_time(self, exposureTime):
        self.newCommand = "t"+str(int(exposureTime))
        self.exposureTime = exposureTime

    def set_analog_gain(self, gain):
        self.newCommand = "g"+str(int(gain))
        self.gain = gain
        
        
    def get_frame(self):
        self.waitForNextFrame = True
        if self.serialdevice is None:
            self.frame = np.random.randint(0,255,(npixelY,npixelX),dtype=np.uint8)
        else:
            try:
                
                # send new comamand to change camera settings, reset command    
                if not self.newCommand == "":
                    self.serialdevice.write((self.newCommand+' \n').encode())
                    self.newCommand = ""
                    while 1:
                        # wait for buffer to be clear again - avoid reboots?
                        readline = self.serialdevice.read()
                        if readline is None or readline == b'\n' or readline == b'':
                            break

                self.serialdevice.write(('\n').encode())
                time.sleep(.05)

                base64_length = self.calculate_base64_length(320, 240)
                lineBreakLength = 2
                base64_image_string  = self.serialdevice.read(base64_length + lineBreakLength)

                image_bytes = base64.b64decode(base64_image_string)
                image_1d = np.frombuffer(image_bytes, dtype=np.uint8)
                self.frame = image_1d.reshape(240, 320)

                if self.waitForNextFrame:
                    self.waitForNextFrame = False
                else:
                    #cv2.imshow("image", frame)
                    #if cv2.waitKey(25) & 0xFF == ord('q'):
                    #    break
                    self.frame_index += 1
                    print("framerate: "+(str(1/(time.time()-t0))))
                    t0 = time.time()

                
            except Exception as e:
                print("Error")
                print(e)
                self.serialdevice.write(('r\n').encode())
                time.sleep(.5)
                while self.serialdevice.read():
                    pass
                self.init_cam()
                self.waitForNextFrame = True
                self.iError += 1

                # Commented out based on the original code
                # if iError % 20 == 0 and iError > 1:
                #     try:
                #         self.serialdevice.setDTR(False)
                #         self.serialdevice.setRTS(True)
                #         time.sleep(.1)
                #         self.serialdevice.setDTR(False)
                #         self.serialdevice.setRTS(False)
                #         time.sleep(.5)
                #     except Exception as e:
                #         pass
        return self.frame

# Example Usage
if __name__ == "__main__":
    camera = ESPCamera(manufacturer='Espressif')
    mFrame = camera.get_frame()
        
