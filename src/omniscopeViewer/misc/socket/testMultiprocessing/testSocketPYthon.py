import socket

def send_message(host, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Connect to server and send data
        sock.connect((host, port))
        sock.sendall(str(message).encode("utf-8"))

        # Optionally receive a response
        received = sock.recv(1024)
        return received.decode("utf-8")

if __name__ == "__main__":
    host = "192.168.0.176"
    port = 4444
    message = 8001

    response = send_message(host, port, message)
    print("Server response:", response)
