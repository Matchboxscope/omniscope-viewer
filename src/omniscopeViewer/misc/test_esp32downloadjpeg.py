import requests
import threading
import os

def download_jpeg(url):
    response = requests.get(url)
    if response.status_code == 200:
        content = response.content
        # adding timestamp to filename
        import datetime
        timeStamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = timeStamp+"_"+url.split("/")[-1]+".jpeg"
        with open(filename, "wb") as f:
            f.write(content)
        print(f"Downloaded: {filename}")

def download_frames(urls):
    threads = []
    for url in urls:
        thread = threading.Thread(target=download_jpeg, args=(url,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

# Specify the list of URLs
url_list = [
    "http://192.168.0.131/capture"
]

# Create a directory to store the downloaded frames
output_directory = "downloaded_frames"
os.makedirs(output_directory, exist_ok=True)
os.chdir(output_directory)

# Download the frames using threading
download_frames(url_list)
