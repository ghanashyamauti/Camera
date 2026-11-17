import cv2
import time
import threading
import logging
import math
import socket
import re
import numpy as np
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

def is_host_reachable(host: str, port: int, timeout: float = 0.8) -> bool:
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
        self.status_message = "Initializing..."

        # HTTP stream mode (Dahua / CP PLUS HTTP snapshot API)
        self.use_http_mode = False
        self.http_auth = None
        self.camera_ip = settings.CAMERA_IP
        self.camera_user = settings.CAMERA_USER
        self.camera_pass = settings.CAMERA_PASSWORD

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Camera manager started with source: {self.source}")

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
            self.use_http_mode = False
            self.is_connected = False
            self.last_reconnect_attempt = 0.0

            # Extract IP and credentials if present
            m = re.search(r"://([^:]+):([^@]+)@([^:/]+)", self.source)
            if m:
                self.camera_user = m.group(1)
                self.camera_pass = m.group(2).replace("%40", "@")
                self.camera_ip = m.group(3)

        logger.info(f"Switched camera source to: {self.source}")

    def _release_cap(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _try_http_snapshot(self) -> bool:
        """
        CP PLUS / Dahua cameras support high-res JPEG snapshot API over HTTP port 80.
        This provides a 100% reliable bypass if RTSP port 554 is blocked or H.265 encoded.
        """
        endpoints = [
            f"http://{self.camera_ip}/cgi-bin/snapshot.cgi?channel=1",
            f"http://{self.camera_ip}/cgi-bin/snapshot.cgi",
            f"http://{self.camera_ip}/onvif/snapshot",
            f"https://{self.camera_ip}/cgi-bin/snapshot.cgi?channel=1"
        ]
        auth_candidates = [
            HTTPDigestAuth(self.camera_user, self.camera_pass),
            HTTPBasicAuth(self.camera_user, self.camera_pass)
        ]

        logger.info(f"Checking CP PLUS HTTP snapshot API on {self.camera_ip}...")
        for url in endpoints:
            for auth in auth_candidates:
                try:
                    r = requests.get(url, auth=auth, timeout=1.2, verify=False)
                    if r.status_code == 200 and len(r.content) > 2000:
                        img_arr = np.frombuffer(r.content, np.uint8)
                        frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            logger.info(f"SUCCESS: Connected via CP PLUS HTTP Snapshot API: {url}")
                            self.use_http_mode = True
                            self.http_auth = auth
                            self.http_url = url
                            self.is_connected = True
                            self.status_message = "CP PLUS Connected (HTTP High-Res Stream)"
                            with self.lock:
                                self.latest_raw_frame = frame
                            return True
                except Exception:
                    pass
        return False

    def _connect_capture(self) -> bool:
        self._release_cap()
        self.use_http_mode = False
        src = self.source.strip()

        # Demo mode
        if src.lower() in ["demo", "synthetic", "test"]:
            self.is_connected = True
            self.status_message = "Demo Simulation Active"
            return True

        # Webcam
        if src.isdigit() or src.lower() == "webcam":
            dev_idx = 0 if src.lower() == "webcam" else int(src)
            logger.info(f"Opening webcam device {dev_idx}...")
            self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
            if self.cap and self.cap.isOpened():
                self.is_connected = True
                self.status_message = f"Webcam Device {dev_idx} Connected"
                return True
            else:
                self.status_message = f"Webcam Device {dev_idx} Failed"
                return False

        # Extract IP and port
        m = re.search(r"://(?:[^@]+@)?([^:/]+)(?::(\d+))?", src)
        host = m.group(1) if m else self.camera_ip
        port = int(m.group(2)) if m and m.group(2) else 554

        # Fast socket check
        if not is_host_reachable(host, port, timeout=0.8):
            logger.warning(f"RTSP host {host}:{port} unreachable.")
            # If RTSP 554 is unreachable, try HTTP port 80 directly!
            if is_host_reachable(host, 80, timeout=0.8):
                if self._try_http_snapshot():
                    return True
            self.status_message = f"Camera unreachable at {host}. Connect to router Wi-Fi."
            self.is_connected = False
            return False

        # Try RTSP candidates with OpenCV
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

        root_url = f"rtsp://{self.camera_user}:{self.camera_pass}@{host}:{port}"
        candidates = [
            src,
            f"{root_url}/cam/realmonitor?channel=1&subtype=1",
            f"{root_url}/cam/realmonitor?channel=1&subtype=0",
            f"{root_url}/live",
            f"{root_url}/onvif1",
            f"{root_url}/Streaming/Channels/101"
        ]

        for candidate in candidates:
            try:
                cap = cv2.VideoCapture(candidate, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        self.cap = cap
                        self.is_connected = True
                        self.status_message = "CP PLUS Camera Connected (RTSP)"
                        logger.info(f"RTSP stream opened successfully: {candidate}")
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

        # RTSP rejected. Try HTTP Snapshot API fallback!
        logger.info("RTSP candidates rejected. Falling back to CP PLUS HTTP API...")
        if self._try_http_snapshot():
            return True

        self.status_message = "RTSP/HTTP Authentication Failed"
        self.is_connected = False
        return False

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
        banner_text = f"STANDBY: {self.status_message}"
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (235, 240, 245), -1)
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (200, 210, 220), 1)
        cv2.putText(frame, banner_text, (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (50, 50, 220), 1, cv2.LINE_AA)

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

            # Mode B: HTTP Snapshot Stream Mode (100% Reliable for CP PLUS)
            if self.use_http_mode:
                try:
                    r = requests.get(self.http_url, auth=self.http_auth, timeout=1.0, verify=False)
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
                            time.sleep(0.03) # ~25-30 FPS
                            continue
                except Exception:
                    self.use_http_mode = False
                    self.is_connected = False

            # Mode C: Hardware / RTSP / Webcam
            if self.cap is None or not self.cap.isOpened():
                now = time.time()
                if now - self.last_reconnect_attempt > 2.5:
                    self.last_reconnect_attempt = now
                    self._connect_capture()

                frame = self._generate_synthetic_frame()
                with self.lock:
                    self.latest_raw_frame = frame
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    self.fps = fps_counter / (time.time() - fps_timer)
                    fps_counter = 0
                    fps_timer = time.time()
                continue

            # Read from OpenCV Capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self._release_cap()
                self.is_connected = False
                continue

            with self.lock:
                self.latest_raw_frame = frame
                self.is_connected = True

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
