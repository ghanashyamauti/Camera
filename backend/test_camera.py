import os
import sys
import time
import socket
import cv2
import requests
import urllib3
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from pathlib import Path
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env")

IP = os.getenv("CAMERA_IP", "192.168.0.100")
PORT = int(os.getenv("CAMERA_PORT", "554"))
USER = os.getenv("CAMERA_USER", "admin")

# Test both passwords
passwords_to_test = [
    os.getenv("CAMERA_PASSWORD", "Admin123!"),
    "Admin123!",
    "Admin@123",
    "admin123",
    "admin"
]
# Remove duplicates preserving order
passwords_to_test = list(dict.fromkeys(passwords_to_test))

print("=" * 65)
print(f"CP PLUS Camera Deep Diagnostic Tool")
print(f"Target: {IP} (User: {USER})")
print("=" * 65)

# 1. Port Checks
print(f"\n[1/3] Checking Ports on {IP}...")
for p, name in [(554, "RTSP"), (80, "HTTP"), (443, "HTTPS"), (37777, "Dahua Media")]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((IP, p))
        s.close()
        print(f"  --> Port {p:5d} ({name:11s}): OPEN")
    except Exception:
        print(f"  --> Port {p:5d} ({name:11s}): Closed/Filtered")

# 2. HTTP/HTTPS API & Password Tester
print(f"\n[2/3] Testing Camera Authentication & Web API...")
working_pwd = None
working_proto = None

for pwd in passwords_to_test:
    print(f"\n  Checking Password: '{pwd}'...")
    for proto, p in [("http", 80), ("https", 443)]:
        for ep in ["/cgi-bin/snapshot.cgi?channel=1", "/cgi-bin/magicBox.cgi?action=getSystemInfo"]:
            url = f"{proto}://{IP}:{p}{ep}"
            for auth_name, auth in [("Digest", HTTPDigestAuth(USER, pwd)), ("Basic", HTTPBasicAuth(USER, pwd))]:
                try:
                    r = requests.get(url, auth=auth, timeout=1.5, verify=False)
                    print(f"    [{proto.upper()}:{p}] {auth_name:6s} -> HTTP {r.status_code}", end="")
                    if r.status_code == 200:
                        print(f" (SUCCESS! Bytes: {len(r.content)})")
                        working_pwd = pwd
                        working_proto = proto
                        break
                    elif r.status_code == 401:
                        print(" (Wrong Password / Unauthorized)")
                    elif r.status_code == 404:
                        print(" (Path Not Found)")
                    else:
                        print(f" ({r.reason})")
                except Exception as e:
                    print(f"    [{proto.upper()}:{p}] Error: {e}")
            if working_pwd:
                break
        if working_pwd:
            break
    if working_pwd:
        break

# 3. RTSP Probing with Verified / Candidate Passwords
print(f"\n[3/3] Probing RTSP Stream with OpenCV...")
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

pwds_for_rtsp = [working_pwd] if working_pwd else passwords_to_test

working_rtsp = None
for pwd in pwds_for_rtsp:
    for sub in [1, 0]:
        stream_name = "Sub-stream (720p)" if sub == 1 else "Main-stream (High Res)"
        url = f"rtsp://{USER}:{pwd}@{IP}:{PORT}/cam/realmonitor?channel=1&subtype={sub}"
        print(f"  Testing {stream_name} with pwd '{pwd}'...")
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                print(f"  >>> SUCCESS! RTSP Connected! Resolution: {w}x{h}")
                working_rtsp = url
                break
            else:
                print("  >>> RTSP Opened but returned empty frame (Possible H.265 Smart Codec).")
        else:
            print("  >>> Connection failed.")
    if working_rtsp:
        break

print("\n" + "=" * 65)
if working_pwd:
    print(f"VERIFIED PASSWORD IS: {working_pwd}")
    print(f"Working Protocol: {working_proto}")

if working_rtsp:
    print(f"WORKING RTSP URL: {working_rtsp}")
    # Update .env
    env_path = Path(__file__).resolve().parent / ".env"
    env_text = env_path.read_text()
    import re
    env_text = re.sub(r"CAMERA_PASSWORD=.*", f"CAMERA_PASSWORD={working_pwd}", env_text)
    env_text = re.sub(r"CAMERA_SOURCE=.*", f"CAMERA_SOURCE={working_rtsp}", env_text)
    env_path.write_text(env_text)
    print("Updated backend/.env automatically!")
elif working_pwd:
    print("NOTE: HTTP authentication is WORKING, but RTSP is blocked.")
    print("Solution in camera browser (https://192.168.0.100):")
    print("1. Go to: Setting -> Camera -> Video -> Change Compression from H.265 to H.264")
    print("2. Go to: Setting -> Network -> Access Platform -> ONVIF -> Add User 'admin'")
else:
    print("COULD NOT AUTHENTICATE WITH ANY OF THE TESTED PASSWORDS.")
    print("Please verify your camera password by logging in at https://192.168.0.100")
print("=" * 65)
