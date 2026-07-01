import requests
import json
import os
import time
import sys

BASE_URL = "https://youtube-api-music.vercel.app"
API_KEY = "NISHKARSH_eTKQjVzWOQEB6aploRZ@r)X1A4(r)MC1"
HEADERS = {"X-API-Key": API_KEY}

def test_endpoint(method, endpoint, params=None):
    print(f"Testing {method} {endpoint}")
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                print(f"Success. Response keys: {list(data.keys())}")
                return data
            else:
                print(f"Success. (Non-JSON response, length: {len(response.text)})")
                return response.text
        else:
            print(f"Failed. Response: {response.text}")
    except Exception as e:
        print(f"Error testing {endpoint}: {e}")
    print("-" * 40)
    return None

def test_all_endpoints():
    print(f"Testing endpoints on {BASE_URL}")
    
    # 1. Health
    test_endpoint("GET", "/")
    test_endpoint("GET", "/health")
    
    # 2. Search
    print("Testing /search")
    search_data = test_endpoint("GET", "/search", params={"q": "Never gonna give you up", "max_results": 1})
    
    video_id = None
    if search_data and search_data.get("success") and search_data.get("results"):
        video_id = search_data["results"][0]["id"]
        print(f"Found video ID: {video_id}")
    else:
        video_id = "dQw4w9WgXcQ" # fallback to Rick Astley
        
    # 3. Video Info
    test_endpoint("GET", "/video", params={"id": video_id})
    
    # 4. Audio Stream
    test_endpoint("GET", "/audio", params={"id": video_id})
    
    # 5. Stream
    test_endpoint("GET", "/stream", params={"id": video_id})
    
    # 6. Related
    test_endpoint("GET", "/related", params={"id": video_id})
    
    # 7. Lyrics
    test_endpoint("GET", "/lyrics", params={"q": "Never gonna give you up rick astley"})
    
    # 8. Download
    print("Testing /download and downloading all formats...")
    download_data = test_endpoint("GET", "/download", params={"id": video_id})
    
    if download_data and download_data.get("success") and "download" in download_data:
        formats = download_data["download"].get("formats", [])
        print(f"Found {len(formats)} formats. Starting download tests...")
        
        os.makedirs("downloaded_formats_vercel", exist_ok=True)
        
        for i, fmt in enumerate(formats):
            fmt_id = fmt.get("format_id", "unknown")
            ext = fmt.get("ext", "bin")
            url = fmt.get("url")
            vcodec = fmt.get("vcodec", "none")
            acodec = fmt.get("acodec", "none")
            
            print(f"[{i+1}/{len(formats)}] Format ID: {fmt_id}, Ext: {ext}, VCodec: {vcodec}, ACodec: {acodec}")
            if not url:
                print("No URL found for this format, skipping.")
                continue
                
            file_name = f"downloaded_formats_vercel/{video_id}_{fmt_id}.{ext}"
            
            # Download first 1MB to verify it works (to avoid taking forever and using too much disk)
            try:
                # We use stream=True and read up to 1MB
                with requests.get(url, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    downloaded = 0
                    with open(file_name, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                            if downloaded >= 1024 * 512: # 512KB max per format to be faster
                                break
                print(f"  -> Successfully downloaded partial file to {file_name} ({downloaded} bytes)")
            except Exception as e:
                print(f"  -> Failed to download format {fmt_id}: {e}")
            sys.stdout.flush()
                
    print("Testing complete.")

if __name__ == "__main__":
    test_all_endpoints()
