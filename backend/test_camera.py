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

# Both candidate passwords
passwords = ["Admin123!", "Admin@123"]

# Comprehensive RTSP paths for CP PLUS Vedaan / RaySharp / Uniview / Tiandy
paths = [
    # RaySharp / CP PLUS Vedaan paths:
    "/live/ch0",
    "/live/ch1",
    "/ch01/0",
    "/ch01/1",
    "/ch0",
    "/ch1",
    "/11",
    "/12",
    "/h264/ch1/main/av_stream",
    "/h264/ch1/sub/av_stream",
    "/unicast/c1/s0/live",
    "/unicast/c1/s1/live",
    "/video1",
    "/video2",
    "/stream1",
    "/stream2",
    "/live",
    "/onvif1",
    "/onvif2",
    "/cam/realmonitor?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
    "/Streaming/Channels/101",
    "/Streaming/Channels/102",
    "/ch0_0.264",
    "/ch0_1.264",
    "/av0_0",
    "/av0_1"
]

print("=" * 65)
print(f"CP PLUS Vedaan Scanner (Testing {len(paths)} RTSP Paths)")
print(f"Target: {IP}:{PORT}")
print("=" * 65)

# Fast socket check
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1.5)
try:
    s.connect((IP, PORT))
    s.close()
    print(f"[OK] Port {PORT} is open and ready!\n")
except Exception as e:
    print(f"[FAIL] Port {PORT} unreachable: {e}")
    sys.exit(1)

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;1000000"

found_url = None

for pwd in passwords:
    print(f"--- Testing with Password: '{pwd}' ---")
    for path in paths:
        url = f"rtsp://{USER}:{pwd}@{IP}:{PORT}{path}"
        print(f"  Path: {path:<32}", end="")
        start_t = time.time()
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        opened = cap.isOpened()
        elapsed = round(time.time() - start_t, 2)
        if opened:
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                print(f" -> [MATCH! SUCCESS ({w}x{h}) in {elapsed}s]")
                found_url = url
                break
            else:
                print(f" -> (Opened, no frame {elapsed}s)")
        else:
            print(f" -> (Failed {elapsed}s)")
            try:
                cap.release()
            except Exception:
                pass
    if found_url:
        break

print("\n" + "=" * 65)
if found_url:
    print("SUCCESS! FOUND WORKING STREAM URL:")
    print(f"  {found_url}")
    print("\nSaving working stream to backend/.env...")
    env_path = Path(__file__).resolve().parent / ".env"
    lines = env_path.read_text().splitlines()
    new_lines = []
    for l in lines:
        if l.startswith("CAMERA_SOURCE="):
            new_lines.append(f"CAMERA_SOURCE={found_url}")
        else:
            new_lines.append(l)
    env_path.write_text("\n".join(new_lines))
    print("DONE! Now run: uvicorn app.main:app --reload --port 8000")
else:
    print("None of the automated paths matched.")
    print("HOW TO FIND IT IN 10 SECONDS IN THE CAMERA PAGE:")
    print("1. In your browser at https://192.168.0.100, click 'Network Settings'.")
    print("2. Look for 'RTSP' or 'Port'. It will list the exact RTSP URL or Path!")
print("=" * 65)
