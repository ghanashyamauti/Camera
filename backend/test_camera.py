import os
import sys
import time
import socket
import cv2
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env")

IP = os.getenv("CAMERA_IP", "192.168.0.100")
PORT = int(os.getenv("CAMERA_PORT", "554"))
USER = os.getenv("CAMERA_USER", "admin")
PASS = os.getenv("CAMERA_PASSWORD", "Admin123!")

print("=" * 60)
print(f"CP PLUS Camera Dual-Engine Diagnostic Tool")
print(f"Target: {USER}:*****@{IP}")
print("=" * 60)

# 1. Socket Check
print(f"\n[1/3] Testing Network Reachability to {IP}:{PORT}...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect((IP, PORT))
    s.close()
    print(f"  --> SUCCESS: RTSP Port {PORT} is OPEN on {IP}!")
except Exception as e:
    print(f"  --> RTSP Port {PORT} is closed or unreachable: {e}")

# 2. HTTP Port Check (Web UI & Snapshot API)
print(f"\n[2/3] Testing Camera Web UI & HTTP Snapshot API (Port 80)...")
http_working = False
endpoints = [
    f"http://{IP}/cgi-bin/snapshot.cgi?channel=1",
    f"http://{IP}/cgi-bin/snapshot.cgi"
]
for ep in endpoints:
    for auth_type, auth in [("Digest", HTTPDigestAuth(USER, PASS)), ("Basic", HTTPBasicAuth(USER, PASS))]:
        try:
            r = requests.get(ep, auth=auth, timeout=2.0)
            if r.status_code == 200 and len(r.content) > 1000:
                print(f"  >>> SUCCESS! CP PLUS HTTP Snapshot API is WORKING with {auth_type} Auth!")
                print(f"      Endpoint: {ep}")
                print(f"      Image bytes received: {len(r.content)} bytes")
                http_working = True
                break
        except Exception as e:
            pass
    if http_working:
        break

if not http_working:
    print("  --> HTTP Snapshot API did not respond with 200 OK.")

# 3. Test CP PLUS RTSP URL Variations
test_paths = [
    ("/cam/realmonitor?channel=1&subtype=1", "CP PLUS Sub-stream (720p)"),
    ("/cam/realmonitor?channel=1&subtype=0", "CP PLUS Main-stream (High Res)"),
    ("/live", "Generic RTSP Live"),
    ("/onvif1", "ONVIF Stream 1"),
    ("/Streaming/Channels/101", "Hikvision/Generic Profile 1")
]

print(f"\n[3/3] Probing RTSP Stream URLs with OpenCV...")
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

working_rtsp = None
for path, desc in test_paths:
    url = f"rtsp://{USER}:{PASS}@{IP}:{PORT}{path}"
    print(f"  Testing {desc}...")
    start_t = time.time()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    opened = cap.isOpened()
    elapsed = round(time.time() - start_t, 2)
    
    if opened:
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  >>> SUCCESS! RTSP Connected ({elapsed}s)! Resolution: {w}x{h}")
            working_rtsp = url
            break
        else:
            print(f"  >>> Opened stream but failed to read initial frame.")
    else:
        print(f"  >>> Connection failed ({elapsed}s)")
        try:
            cap.release()
        except Exception:
            pass

print("\n" + "=" * 60)
if working_rtsp or http_working:
    print("DIAGNOSTIC RESULT: CAMERA FEED IS READY!")
    if working_rtsp:
        print(f"Working RTSP: {working_rtsp}")
    if http_working:
        print(f"Working HTTP: http://{IP}/cgi-bin/snapshot.cgi?channel=1")
    print("\nRestart your backend: uvicorn app.main:app --reload --port 8000")
    print("Your stream will now display in http://localhost:5173!")
else:
    print("DIAGNOSTIC RESULT: Check camera settings in browser at http://192.168.0.100")
print("=" * 60)
