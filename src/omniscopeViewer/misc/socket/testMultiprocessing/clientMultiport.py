import socket

# Server settings
server_ip = "192.168.2.191"  # Replace with the IP address of the Python server
server_port = 3333             # Replace with the port used by the Python server

# Create a socket object
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
client_socket.connect((server_ip, server_port))
print(f"Connected to server at {server_ip}:{server_port}")

# Receive data from the server
data = client_socket.send(str(1024).encode())
print(f"Received data from server: {data}")

# Close the socket
client_socket.close()
