import socket

def get_all_ip_addresses():
    ip_addresses = []
    
    # Get the host name
    host_name = socket.gethostname()
    
    # Get all IP addresses associated with the host name
    try:
        ip_addresses = socket.gethostbyname_ex(host_name)[-1]
    except socket.gaierror:
        pass  # Handle any exceptions here if needed
    
    return ip_addresses

if __name__ == "__main__":
    all_ip_addresses = get_all_ip_addresses()
    for ip in all_ip_addresses:
        print(f"IP Address: {ip}")
