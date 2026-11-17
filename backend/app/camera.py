import cv2
import time
import threading
import logging
import math
import socket
import re
import numpy as np
import requests
import urllib3
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from typing import Optional, Tuple
from pathlib import Path
from app.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# All known RTSP paths across CP PLUS Vedaan, RaySharp, Uniview, Tiandy & Dahua
RTSP_PATHS = [
    "/live/ch0",
    "/live/ch1",
    "/ch01/0",
    "/ch01/1",
    "/stream1",
    "/stream2",
    "/11",
    "/12",
    "/h264/ch1/main/av_stream",
    "/h264/ch1/sub/av_stream",
    "/unicast/c1/s0/live",
    "/unicast/c1/s1/live",
    "/cam/realmonitor?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
    "/live",
    "/onvif1",
    "/onvif2",
    "/Streaming/Channels/101",
    "/Streaming/Channels/102",
    "/video1",
    "/video2",
    "/ch0",
    "/ch1"
]

HTTP_SNAPSHOT_PATHS = [
    "/snapshot/ch0.jpg",
    "/snapshot/ch1.jpg",
    "/tmpfs/auto.jpg",
    "/auto.jpg",
    "/image.jpg",
    "/cgi-bin/snapshot.cgi?channel=1",
    "/cgi-bin/snapshot.cgi",
    "/onvif-http/snapshot?channel=1"
]

def check_port(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

class CameraManager:
    def __init__(self):
        self.source = settings.CAMERA_SOURCE
        self.fallback = settings.FALLBACK_SOURCE
        self.cap: Optional[cv2.VideoCapture] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.is_running = False
        self.is_connected = False
        self.fps = 0.0
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.last_reconnect_attempt = 0.0
        self.demo_tick = 0
        self.status_message = "Auto-discovering camera stream..."

        # Credentials
        self.camera_ip = settings.CAMERA_IP
        self.camera_user = settings.CAMERA_USER
        self.passwords = [settings.CAMERA_PASSWORD, "Admin123!", "Admin@123", "admin123", "admin"]
        # Remove duplicates
        self.passwords = list(dict.fromkeys([p for p in self.passwords if p]))

        # Auto-discovered working URL
        self.working_rtsp_url: Optional[str] = None
        self.working_http_url: Optional[str] = None
        self.working_http_auth = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Camera manager started.")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self._release_cap()
        logger.info("Camera manager stopped.")

    def set_source(self, new_source: str):
        with self.lock:
            self.source = new_source.strip()
            self._release_cap()
            self.working_rtsp_url = None
            self.working_http_url = None
            self.is_connected = False
            self.last_reconnect_attempt = 0.0

            # Parse user/pass/ip if provided
            m = re.search(r"://([^:]+):([^@]+)@([^:/]+)", self.source)
            if m:
                self.camera_user = m.group(1)
                p = m.group(2).replace("%40", "@")
                if p not in self.passwords:
                    self.passwords.insert(0, p)
                self.camera_ip = m.group(3)

        logger.info(f"Switched camera source to: {self.source}")

    def _release_cap(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _auto_discover_stream(self) -> bool:
        """
        Silently probes all RTSP and HTTP stream endpoints in the background
        until it finds the exact working stream. No user interaction needed!
        """
        host = self.camera_ip
        port = 554

        # 1. Quick check: Is camera IP online?
        rtsp_port_open = check_port(host, port, timeout=0.6)
        http_port_open = check_port(host, 80, timeout=0.6) or check_port(host, 443, timeout=0.6)

        if not rtsp_port_open and not http_port_open:
            self.status_message = f"Camera {host} offline. Connect PC to router Wi-Fi (Shakham_5G)."
            self.is_connected = False
            return False

        self.status_message = f"Scanning stream paths on {host}..."
        logger.info(f"Auto-probing streams on {host} (RTSP 554={rtsp_port_open}, HTTP 80/443={http_port_open})...")

        # 2. Probe RTSP Paths with TCP & UDP
        if rtsp_port_open:
            import os
            for transport in ["tcp", "udp"]:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}|stimeout;800000"
                for pwd in self.passwords:
                    for path in RTSP_PATHS:
                        test_url = f"rtsp://{self.camera_user}:{pwd}@{host}:{port}{path}"
                        try:
                            cap = cv2.VideoCapture(test_url, cv2.CAP_FFMPEG)
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            if cap.isOpened():
                                ret, frame = cap.read()
                                if ret and frame is not None and frame.size > 0:
                                    logger.info(f"SUCCESS: Auto-locked RTSP stream: {test_url} ({transport})")
                                    self.cap = cap
                                    self.working_rtsp_url = test_url
                                    self.is_connected = True
                                    self.status_message = "CP PLUS Live Stream Active"
                                    with self.lock:
                                        self.latest_raw_frame = frame
                                    self._save_working_url(test_url)
                                    return True
                                else:
                                    cap.release()
                            else:
                                try:
                                    cap.release()
                                except Exception:
                                    pass
                        except Exception:
                            pass

        # 3. Probe HTTP / HTTPS Snapshot Endpoints
        for proto, p in [("http", 80), ("https", 443)]:
            if not check_port(host, p, timeout=0.5):
                continue
            for pwd in self.passwords:
                auth_list = [
                    HTTPDigestAuth(self.camera_user, pwd),
                    HTTPBasicAuth(self.camera_user, pwd)
                ]
                for path in HTTP_SNAPSHOT_PATHS:
                    url = f"{proto}://{host}:{p}{path}"
                    for auth in auth_list:
                        try:
                            r = requests.get(url, auth=auth, timeout=0.8, verify=False)
                            if r.status_code == 200 and len(r.content) > 1000:
                                img_arr = np.frombuffer(r.content, np.uint8)
                                frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                                if frame is not None:
                                    logger.info(f"SUCCESS: Auto-locked HTTP stream: {url}")
                                    self.working_http_url = url
                                    self.working_http_auth = auth
                                    self.is_connected = True
                                    self.status_message = "CP PLUS Live Feed Active (HTTP Engine)"
                                    with self.lock:
                                        self.latest_raw_frame = frame
                                    return True
                        except Exception:
                            pass

        self.status_message = "Camera stream paths locked by firmware. Connect PC to router Wi-Fi."
        self.is_connected = False
        return False

    def _save_working_url(self, url: str):
        try:
            env_file = Path(settings.BASE_DIR) / ".env"
            if env_file.exists():
                lines = env_file.read_text().splitlines()
                updated = False
                new_lines = []
                for line in lines:
                    if line.startswith("CAMERA_SOURCE="):
                        new_lines.append(f"CAMERA_SOURCE={url}")
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append(f"CAMERA_SOURCE={url}")
                env_file.write_text("\n".join(new_lines))
        except Exception:
            pass

    def _generate_synthetic_frame(self) -> np.ndarray:
        self.demo_tick += 1
        w, h = 960, 540
        frame = np.full((h, w, 3), (248, 250, 252), dtype=np.uint8)

        for y in range(320, h, 25):
            cv2.line(frame, (0, y), (w, y), (226, 232, 240), 1)

        cv2.rectangle(frame, (40, 40), (280, 220), (220, 235, 250), -1)
        cv2.rectangle(frame, (40, 40), (280, 220), (180, 200, 225), 2)
        cv2.putText(frame, "Driveway Window", (50, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 120, 140), 1)

        car_x = int(50 + (math.sin(self.demo_tick * 0.03) + 1) * 70)
        cv2.rectangle(frame, (car_x, 120), (car_x + 95, 175), (55, 65, 210), -1)
        cv2.putText(frame, "car", (car_x + 10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.rectangle(frame, (680, 260), (800, 430), (130, 90, 70), -1)
        cv2.rectangle(frame, (680, 260), (800, 430), (100, 70, 50), 2)
        cv2.putText(frame, "chair", (710, 345), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        obj_x = int(340 + math.sin(self.demo_tick * 0.04) * 200)
        obj_y = int(270 + math.cos(self.demo_tick * 0.02) * 45)
        cv2.circle(frame, (obj_x + 40, obj_y - 30), 20, (190, 140, 80), -1)
        cv2.rectangle(frame, (obj_x + 15, obj_y - 10), (obj_x + 65, obj_y + 80), (60, 130, 200), -1)
        cv2.putText(frame, "person", (obj_x + 18, obj_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Standby status
        banner_text = f"AUTO-CONNECTING: {self.status_message}"
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (235, 240, 245), -1)
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (200, 210, 220), 1)
        cv2.putText(frame, banner_text, (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 50, 220), 1, cv2.LINE_AA)

        time.sleep(0.033)
        return frame

    def _capture_loop(self):
        fps_counter = 0
        fps_timer = time.time()

        while self.is_running:
            # Mode A: Explicit Demo Source
            if self.source.lower() in ["demo", "synthetic", "test"]:
                frame = self._generate_synthetic_frame()
                with self.lock:
                    self.latest_raw_frame = frame
                    self.is_connected = True
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    self.fps = fps_counter / (time.time() - fps_timer)
                    fps_counter = 0
                    fps_timer = time.time()
                continue

            # Mode B: Explicit Webcam Source
            if self.source.isdigit() or self.source.lower() == "webcam":
                if self.cap is None or not self.cap.isOpened():
                    dev_idx = 0 if self.source.lower() == "webcam" else int(self.source)
                    self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        with self.lock:
                            self.latest_raw_frame = frame
                            self.is_connected = True
                        fps_counter += 1
                        if time.time() - fps_timer >= 1.0:
                            self.fps = fps_counter / (time.time() - fps_timer)
                            fps_counter = 0
                            fps_timer = time.time()
                        continue
                time.sleep(0.1)
                continue

            # Mode C: Locked HTTP Stream
            if self.working_http_url and self.working_http_auth:
                try:
                    r = requests.get(self.working_http_url, auth=self.working_http_auth, timeout=0.8, verify=False)
                    if r.status_code == 200 and len(r.content) > 1000:
                        img_arr = np.frombuffer(r.content, np.uint8)
                        frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.latest_raw_frame = frame
                                self.is_connected = True
                            fps_counter += 1
                            if time.time() - fps_timer >= 1.0:
                                self.fps = fps_counter / (time.time() - fps_timer)
                                fps_counter = 0
                                fps_timer = time.time()
                            time.sleep(0.03)
                            continue
                except Exception:
                    self.working_http_url = None
                    self.is_connected = False

            # Mode D: Locked RTSP Stream
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.latest_raw_frame = frame
                        self.is_connected = True
                    fps_counter += 1
                    if time.time() - fps_timer >= 1.0:
                        self.fps = fps_counter / (time.time() - fps_timer)
                        fps_counter = 0
                        fps_timer = time.time()
                    continue
                else:
                    self._release_cap()
                    self.is_connected = False

            # Mode E: Auto-Discover / Reconnect in background
            now = time.time()
            if now - self.last_reconnect_attempt > 3.0:
                self.last_reconnect_attempt = now
                self._auto_discover_stream()

            frame = self._generate_synthetic_frame()
            with self.lock:
                self.latest_raw_frame = frame
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                self.fps = fps_counter / (time.time() - fps_timer)
                fps_counter = 0
                fps_timer = time.time()

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self.lock:
            if self.latest_raw_frame is not None:
                return True, self.latest_raw_frame.copy()
            return False, None

camera_manager = CameraManager()
