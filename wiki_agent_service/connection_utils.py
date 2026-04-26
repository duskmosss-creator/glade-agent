import requests
import json
import time

def smart_post(url, json_data, timeout=300, retries=2):
    """
    Robust POST request handler that handles IPv6 loopback issues commonly found on Windows.
    Forces [::1] for Lemonade if localhost/127.0.0.1 fails.
    """
    targets = [url]
    
    # If using localhost/127.0.0.1 on port 8000, add IPv6 as a fallback/priority
    if ":8000" in url and ("localhost" in url or "127.0.0.1" in url):
        ipv6_url = url.replace("localhost", "[::1]").replace("127.0.0.1", "[::1]")
        if ipv6_url not in targets:
            targets.insert(0, ipv6_url) # Try IPv6 first as it's the known winner
            
    last_error = None
    for target in targets:
        for attempt in range(retries + 1):
            try:
                print(f"   [Connection] Attempting {target} (Attempt {attempt+1})...")
                response = requests.post(target, json=json_data, timeout=timeout)
                
                # Check for success
                if response.status_code == 200:
                    return response
                
                # If we got a real HTTP error, log it but maybe don't retry immediately
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"   [Connection] {target} returned {last_error}")
                
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection Error: {e}"
                print(f"   [Connection] {target} failed: Connection Refused/Timeout")
            except Exception as e:
                last_error = f"Unexpected Error: {type(e).__name__}: {e}"
                print(f"   [Connection] {target} failed: {last_error}")
            
            if attempt < retries:
                time.sleep(1) # Brief pause before retry
                
    # If we get here, all targets/retries failed
    raise IOError(f"AI Backend Unreachable. Last error: {last_error}")

def smart_get(url, timeout=5):
    """Robust GET request handler for model discovery."""
    targets = [url]
    if ":8000" in url and ("localhost" in url or "127.0.0.1" in url):
        ipv6_url = url.replace("localhost", "[::1]").replace("127.0.0.1", "[::1]")
        if ipv6_url not in targets:
            targets.insert(0, ipv6_url)
            
    for target in targets:
        try:
            return requests.get(target, timeout=timeout)
        except:
            continue
    return None
