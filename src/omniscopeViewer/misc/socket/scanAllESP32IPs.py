import socket
import requests
import threading
import time 
class ESP32Scanner(object):

    def __init__(self):
        self.cameraURLs = []  # Initialize a list to store camera URLs
        # Define the range of IP addresses to scan
        start_ip = 1
        end_ip = 255

        # Get all available host IP addresses
        allHostIpAdresses = self.get_all_ip_addresses()
        for ipAddress in allHostIpAdresses:
            # Base URL formation (excluding the last segment of the IP address)
            baseUrl = ".".join(ipAddress.split('.')[:-1]) + "."

            # Scanning IP addresses within the defined range
            scannedIPs = self.scan_ips(baseUrl, start_ip, end_ip)
            print("Scanned IP addresses:", scannedIPs)

            # Create a list of URLs from the scanned IPs
            for iIP in scannedIPs:
                self.cameraURLs.append(iIP["IP"])

    def get_all_ip_addresses(self):
        """
        Retrieves all IP addresses associated with the host machine.
        """
        ip_addresses = []

        # Get the host name
        host_name = socket.gethostname()

        # Get all IP addresses associated with the host name
        try:
            ip_addresses = socket.gethostbyname_ex(host_name)[-1]
        except socket.gaierror:
            pass  # Ignore errors in name resolution

        return ip_addresses


    def get_unique_id(self, server_ip):
        """
        Sends a GET request to the server to retrieve a unique ID.
        
        Args:
        - server_ip (str): The IP address of the ESP32 server.

        Returns:
        - int: The unique ID received from the server, or None if the request fails.
        """
        url = f"http://{server_ip}/getId"
        try:
            print("Scanning IP:", server_ip)
            response = requests.get(url, timeout=0.5)
            response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code.

            # Assuming the server responds with a JSON in the format: {"id": "<uniqueId>"}
            data = response.json()
            return data.get("id")

        except Exception as e:
            pass
        return None
    
    def scan_ip(self, ip_address, results):
        """
        Scans a single IP address for a specific service and records if found.
        """
        try:
            responseID = self.get_unique_id(ip_address) 
            if responseID is not None:
                
                print(f"Connected device found at IP: {ip_address}")
                print("Status:", responseID)
                results.append({"IP": ip_address, "ID": responseID})

            else:
                print(f"No device found at IP: {ip_address}")

        except requests.exceptions.RequestException:
            print(f"No response from IP: {ip_address}")

    def scan_ips(self, baseUrl, start_ip, end_ip):
        """
        Scans a range of IPs within the subnet to identify available devices.
        """
        results = []
        threads = []
        for i in range(start_ip, end_ip + 1):
            ip_address = baseUrl + str(i)
            thread = threading.Thread(target=self.scan_ip, args=(ip_address, results))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        return results

# Main execution block
if __name__ == "__main__":
    scanner = ESP32Scanner()  # Create an instance of the scanner
    print("Detected Cameras:", scanner.cameraURLs)  # Print the detected camera URLs
