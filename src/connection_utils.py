import os
import requests
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

class CloudUploader:
    """Handles uploading secure files to temporary cloud hosting."""
    
    @staticmethod
    def upload_file(file_path):
        """Try multiple providers with secure fallback logic."""
        if not os.path.exists(file_path):
            return None
            
        filename = os.path.basename(file_path)
        print(f"   [Upload] Starting upload chain for {filename}...")
        
        # Priority Fallback Chain
        providers = [
            ("transfer.sh", CloudUploader._upload_transfersh),
            ("tmpfiles", CloudUploader._upload_tmpfiles),
            ("catbox", CloudUploader._upload_catbox),
            ("0x0", CloudUploader._upload_0x0),
            ("file.io", CloudUploader._upload_fileio)
        ]
        
        for name, func in providers:
            try:
                print(f"   [Upload] Trying {name}...")
                link = func(file_path)
                if link:
                    # Enforce HTTPS
                    if link.startswith("http://"):
                        link = link.replace("http://", "https://")
                    elif not link.startswith("https://"):
                        link = "https://" + link
                    print(f"   [Upload] {name} success: {link}")
                    return link
            except Exception as e:
                print(f"   [Upload] {name} failed: {e}")
                
        print("   [Upload] All providers failed.")
        return None

    @staticmethod
    def _upload_transfersh(file_path):
        filename = os.path.basename(file_path)
        url = f"https://transfer.sh/{filename}"
        with open(file_path, 'rb') as f:
            resp = requests.put(url, data=f, timeout=30)
        if resp.status_code == 200:
            return resp.text.strip()
        return None

    @staticmethod
    def _upload_tmpfiles(file_path):
        url = "https://tmpfiles.org/api/v1/upload"
        with open(file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(url, files=files, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            page_url = data['data']['url']
            return page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return None

    @staticmethod
    def _upload_catbox(file_path):
        url = "https://catbox.moe/user/api.php"
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload'}
            resp = requests.post(url, data=data, files=files, timeout=30)
        if resp.status_code == 200:
            return resp.text.strip()
        return None

    @staticmethod
    def _upload_0x0(file_path):
        url = "https://0x0.st"
        with open(file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(url, files=files, timeout=30)
        if resp.status_code == 200:
            return resp.text.strip()
        return None

    @staticmethod
    def _upload_fileio(file_path):
        url = "https://file.io"
        with open(file_path, 'rb') as f:
            resp = requests.post(url, files={"file": f}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return data.get("link")
        return None
