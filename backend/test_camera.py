import os
import sys
import time
import socket
import cv2
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env")

IP = os.getenv("CAMERA_IP", "192.168.0.100")
PORT = int(os.getenv("CAMERA_PORT", "554"))
USER = os.getenv("CAMERA_USER", "admin")
PASS = os.getenv("CAMERA_PASSWORD", "Admin123!")

print("=" * 60)
print(f"CP PLUS Camera Diagnostic Tool")
print(f"Target: {USER}:*****@{IP}:{PORT}")
print("=" * 60)

# 1. Socket Check
print(f"\n[1/3] Testing Network Reachability to {IP}:{PORT}...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect((IP, PORT))
    s.close()
    print(f"  --> SUCCESS: Port {PORT} is OPEN on {IP}!")
except Exception as e:
    print(f"  --> FAILED: Cannot reach {IP}:{PORT} ({e})")
    print("  --> Please ensure your PC is connected to the router Wi-Fi (Shakham_5G).")
    sys.exit(1)

# 2. HTTP Port Check (Web UI)
print(f"\n[2/3] Testing Camera Web UI Port 80...")
s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s2.settimeout(1.5)
try:
    s2.connect((IP, 80))
    s2.close()
    print(f"  --> SUCCESS: Web UI Port 80 is OPEN at http://{IP}")
except Exception as e:
    print(f"  --> NOTE: Port 80 not responding ({e})")

# 3. Test All CP PLUS RTSP URL Variations
test_paths = [
    # Standard Dahua / CP PLUS paths
    ("/cam/realmonitor?channel=1&subtype=1", "CP PLUS Sub-stream (720p)"),
    ("/cam/realmonitor?channel=1&subtype=0", "CP PLUS Main-stream (High Res)"),
    ("/cam/realmonitor?channel=1&subtype=2", "CP PLUS Mobile-stream"),
    ("/live", "Generic RTSP Live"),
    ("/onvif1", "ONVIF Stream 1"),
    ("/onvif2", "ONVIF Stream 2"),
    ("/Streaming/Channels/101", "Hikvision/Generic Profile 1"),
    ("/Streaming/Channels/102", "Hikvision/Generic Profile 2"),
    ("/h264Preview_01_main", "H.264 Preview Main"),
    ("/media/video1", "Media Video 1")
]

print(f"\n[3/3] Probing RTSP Stream URLs with OpenCV...")

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

working_url = None

for path, desc in test_paths:
    url = f"rtsp://{USER}:{PASS}@{IP}:{PORT}{path}"
    print(f"\n  Testing {desc}:")
    print(f"  URL: {url}")
    
    start_t = time.time()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    
    opened = cap.isOpened()
    elapsed = round(time.time() - start_t, 2)
    
    if opened:
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  >>> SUCCESS! Connected in {elapsed}s! Frame resolution: {w}x{h}")
            working_url = url
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
if working_url:
    print("RESULT: FOUND WORKING STREAM URL!")
    print(f"  {working_url}")
    print("\nUpdating .env with working URL...")
    # Update CAMERA_SOURCE in .env
    env_path = Path(__file__).resolve().parent / ".env"
    lines = env_path.read_text().splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("CAMERA_SOURCE="):
            new_lines.append(f"CAMERA_SOURCE={working_url}")
        else:
            new_lines.append(line)
    env_path.write_text("\n".join(new_lines))
    print("  Updated backend/.env successfully!")
else:
    print("RESULT: NONE OF THE RTSP PATHS CONNECTED.")
    print("\nPossible Causes:")
    print("1. In Camera Web Page (http://192.168.0.100):")
    print("   Go to: Setting -> Camera -> Video -> Encode")
    print("   Change Compression from 'H.265' / 'Smart Codec' to 'H.264'.")
    print("2. Go to: Setting -> Network -> Access Platform -> ONVIF")
    print("   Ensure 'Enable ONVIF' is checked, and Add user 'admin' with 'Admin123!'.")
    print("3. Go to: Setting -> System -> Safety -> System Service")
    print("   Ensure 'RTSP' is enabled.")
print("=" * 60)
