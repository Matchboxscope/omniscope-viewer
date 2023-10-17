import requests
import socket

from subprocess import check_output

import socket
def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]
 
# The IP address of your ESP32
esp_ip_address = '192.168.2.224'  # Replace with your ESP32's IP address

# The new server IP you want to set on the ESP32
new_server_ip = get_ip_address()  # '192.168.0.110'  #'192.168.1.101'  # Replace with the desired IP address
#new_server_ip = '192.168.2.224'  # Replace with your ESP32's IP address

# Form the URL
url = f'http://{esp_ip_address}/setServer'

# Form the payload
payload = {'server': new_server_ip}

# Send the POST request
try:
    response = requests.get(url, params=payload)
    # Print the response from the ESP32
    print(response.text)
except Exception as e:
    print(e)


