from connection_utils import CloudUploader
import os

# Create a dummy file
with open("test_upload.txt", "w") as f:
    f.write("Hello World")

link = CloudUploader.upload_file("test_upload.txt")
print(f"Link: {link}")

if os.path.exists("test_upload.txt"):
    os.remove("test_upload.txt")
