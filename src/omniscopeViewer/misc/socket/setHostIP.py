import requests
import socket

class ESP32Controller:
    def __init__(self, esp_ip):
        self.esp_ip = esp_ip

    @staticmethod
    def get_local_ip_address():
        """
        Get the IP address of the local machine.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip

    def set_server_ip(self, server_ip):
        """
        Set the server IP on the ESP32.

        Args:
        - server_ip (str): The new server IP to set on the ESP32.

        Returns:
        - str: The response text from the ESP32.
        """
        url = f'http://{self.esp_ip}/setServer'
        payload = {'server': server_ip}

        try:
            response = requests.get(url, params=payload)
            return response.text
        except Exception as e:
            return str(e)

# Usage example
esp_ip_address = '192.168.2.224'  # Replace with your ESP32's IP address
esp_controller = ESP32Controller(esp_ip_address)

# Use the local machine's IP address as the new server IP
new_server_ip = esp_controller.get_local_ip_address()

# Set the new server IP on the ESP32
response = esp_controller.set_server_ip(new_server_ip)
print(response)
