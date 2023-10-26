import requests

# Define the endpoint and parameters
server_address = "http://192.168.137.7"  # Replace with the IP address of your ESP server
endpoint = "/setUniqueID"
params = {
    "uid": "1"  # Replace 12345 with the desired Unique ID
}

# Construct the full URL
url = f"{server_address}{endpoint}"

# Send the GET request
response = requests.get(url, params=params)

# Print the response
print(response.text)