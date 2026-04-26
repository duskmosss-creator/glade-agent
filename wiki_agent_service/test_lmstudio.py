import requests
import socket
import sys

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 1234
TARGET_URL = f"http://{TARGET_HOST}:{TARGET_PORT}/v1/models"

print(f"--- DIAGNOSTIC: Testing Connection to LM Studio ---")
print(f"Target: {TARGET_HOST}:{TARGET_PORT}")

# 1. Test Raw Socket
print("\n[1] Testing TCP Socket...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
result = sock.connect_ex((TARGET_HOST, TARGET_PORT))
if result == 0:
    print("    SUCCESS: Socket is OPEN and listening.")
else:
    print(f"    FAILURE: Socket is CLOSED or BLOCKED. Error Code: {result}")
    print("    -> LM Studio Server is NOT running or NOT on port 1234.")
    sys.exit(1)
sock.close()

# 2. Test HTTP API
print("\n[2] Testing HTTP API (/v1/models)...")
try:
    response = requests.get(TARGET_URL, timeout=5)
    print(f"    Status Code: {response.status_code}")
    if response.status_code == 200:
        print("    SUCCESS: API is responding correctly.")
        try:
            models = response.json()
            print(f"    Available Models: {len(models.get('data', []))}")
            for m in models.get('data', [])[:3]:
                print(f"    - {m['id']}")
        except:
            print("    Warning: Could not parse JSON response.")
    else:
        print(f"    FAILURE: API returned error code.")
except Exception as e:
    print(f"    FAILURE: HTTP Request Failed: {e}")

print("\n--- END DIAGNOSTIC ---")
