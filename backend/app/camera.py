import cv2
import time
import threading
import logging
import math
import socket
import re
import urllib.request
import urllib.error
import numpy as np
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

class CpPlusHttpGrabber:
    """
    Direct HTTP Digest grabber for CP PLUS / Dahua cameras.
    Works natively over HTTP (Port 80) even when RTSP / Port 554 is blocked.
    """
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self.base_url = f"http://{host}"
        self.snapshot_url = f"http://{host}/cgi-bin/snapshot.cgi?channel=1"
        self.opener = self._build_opener()

    def _build_opener(self):
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, self.base_url, self.user, self.password)
        auth_handler = urllib.request.HTTPDigestAuthHandler(password_mgr)
        basic_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        return urllib.request.build_opener(auth_handler, basic_handler)

    def grab_frame(self, timeout: float = 1.5) -> Optional[np.ndarray]:
        try:
            req = urllib.request.Request(self.snapshot_url)
            with self.opener.open(req, timeout=timeout) as response:
                img_bytes = response.read()
                if img_bytes and len(img_bytes) > 100:
                    arr = np.frombuffer(img_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    return frame
        except Exception as e:
            pass
        return None

class CameraManager:
    def __init__(self):
        self.source = settings.CAMERA_SOURCE
        self.fallback = settings.FALLBACK_SOURCE
        self.cap: Optional[cv2.VideoCapture] = None
        self.http_grabber: Optional[CpPlusHttpGrabber] = None
        self.use_http_mode = False
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.is_running = False
        self.is_connected = False
        self.fps = 0.0
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.last_reconnect_attempt = 0.0
        self.demo_tick = 0
        self.status_message = "Initializing..."

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
            self.http_grabber = None
            self.use_http_mode = False
            self.is_connected = False
            self.last_reconnect_attempt = 0.0
        logger.info(f"Switched camera source to: {self.source}")

    def _release_cap(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _extract_credentials(self, url: str) -> Tuple[str, str, str, int]:
        """Extracts user, password, host, port from RTSP/HTTP URL"""
        user = settings.CAMERA_USER
        password = settings.CAMERA_PASSWORD
        host = settings.CAMERA_IP
        port = settings.CAMERA_PORT

        match = re.search(r"://(?:([^:]+):([^@]+)@)?([^:/]+)(?::(\d+))?", url)
        if match:
            if match.group(1): user = match.group(1)
            if match.group(2): password = match.group(2)
            if match.group(3): host = match.group(3)
            if match.group(4): port = int(match.group(4))
        return user, password, host, port

    def _connect_capture(self) -> bool:
        self._release_cap()
        src = self.source.strip()

        # Demo mode
        if src.lower() in ["demo", "synthetic", "test"]:
            self.is_connected = True
            self.use_http_mode = False
            self.status_message = "Demo Simulation Active"
            return True

        # Webcam
        if src.isdigit() or src.lower() == "webcam":
            dev_idx = 0 if src.lower() == "webcam" else int(src)
            logger.info(f"Opening webcam device {dev_idx}...")
            self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
            if self.cap and self.cap.isOpened():
                self.is_connected = True
                self.use_http_mode = False
                self.status_message = f"Webcam Device {dev_idx} Connected"
                return True
            else:
                self.status_message = f"Webcam Device {dev_idx} Failed"
                return False

        user, password, host, port = self._extract_credentials(src)

        # 1. First attempt: OpenCV RTSP stream variants
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        candidates = [
            f"rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel=1&subtype=1",
            f"rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel=1&subtype=0",
            f"rtsp://{user}:{password}@{host}:{port}/live",
            f"rtsp://{user}:{password}@{host}:{port}/onvif1"
        ]

        for candidate in candidates:
            logger.info(f"Trying RTSP stream: {candidate}")
            cap = cv2.VideoCapture(candidate, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    self.cap = cap
                    self.is_connected = True
                    self.use_http_mode = False
                    self.status_message = "CP PLUS Camera Connected (RTSP)"
                    logger.info(f"Stream opened successfully via RTSP: {candidate}")
                    return True
            try:
                cap.release()
            except Exception:
                pass

        # 2. Second attempt: Native CP PLUS HTTP Digest Snapshot (Port 80)
        # If the user can see the camera web page, this ALWAYS works!
        logger.info(f"RTSP failed. Trying native CP PLUS HTTP Digest grabber on {host}:80...")
        grabber = CpPlusHttpGrabber(host, user, password)
        test_frame = grabber.grab_frame(timeout=1.5)
        if test_frame is not None:
            self.http_grabber = grabber
            self.use_http_mode = True
            self.is_connected = True
            self.latest_raw_frame = test_frame
            self.status_message = "CP PLUS Connected (HTTP Native Stream)"
            logger.info("CP PLUS camera connected successfully via native HTTP stream!")
            return True

        self.status_message = f"Connecting to camera at {host}... Check Wi-Fi"
        self.is_connected = False
        return False

    def _generate_synthetic_frame(self) -> np.ndarray:
        self.demo_tick += 1
        w, h = 960, 540
        frame = np.full((h, w, 3), (248, 250, 252), dtype=np.uint8)

        # Draw grid floor
        for y in range(320, h, 25):
            cv2.line(frame, (0, y), (w, y), (226, 232, 240), 1)

        # Window outside (driveway with moving car)
        cv2.rectangle(frame, (40, 40), (280, 220), (220, 235, 250), -1)
        cv2.rectangle(frame, (40, 40), (280, 220), (180, 200, 225), 2)
        cv2.putText(frame, "Driveway Window", (50, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 120, 140), 1)

        # Moving car
        car_x = int(50 + (math.sin(self.demo_tick * 0.03) + 1) * 70)
        cv2.rectangle(frame, (car_x, 120), (car_x + 95, 175), (55, 65, 210), -1)
        cv2.putText(frame, "car", (car_x + 10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Stationary Chair
        cv2.rectangle(frame, (680, 260), (800, 430), (130, 90, 70), -1)
        cv2.rectangle(frame, (680, 260), (800, 430), (100, 70, 50), 2)
        cv2.putText(frame, "chair", (710, 345), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Moving Person
        obj_x = int(340 + math.sin(self.demo_tick * 0.04) * 200)
        obj_y = int(270 + math.cos(self.demo_tick * 0.02) * 45)
        cv2.circle(frame, (obj_x + 40, obj_y - 30), 20, (190, 140, 80), -1)
        cv2.rectangle(frame, (obj_x + 15, obj_y - 10), (obj_x + 65, obj_y + 80), (60, 130, 200), -1)
        cv2.putText(frame, "person", (obj_x + 18, obj_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Status Banner at bottom
        banner_text = f"STANDBY: {self.status_message}"
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (235, 240, 245), -1)
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (200, 210, 220), 1)
        cv2.putText(frame, banner_text, (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 210), 1, cv2.LINE_AA)

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

            # Mode B: Native HTTP Digest Grabber (Port 80)
            if self.use_http_mode and self.http_grabber:
                frame = self.http_grabber.grab_frame(timeout=1.0)
                if frame is not None:
                    with self.lock:
                        self.latest_raw_frame = frame
                        self.is_connected = True
                    fps_counter += 1
                    if time.time() - fps_timer >= 1.0:
                        self.fps = fps_counter / (time.time() - fps_timer)
                        fps_counter = 0
                        fps_timer = time.time()
                    time.sleep(0.04) # ~25 FPS
                    continue
                else:
                    self.is_connected = False
                    self.use_http_mode = False

            # Mode C: Hardware RTSP / Webcam
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

            # Mode D: Reconnecting / Standby Feed
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

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self.lock:
            if self.latest_raw_frame is not None:
                return True, self.latest_raw_frame.copy()
            return False, None

camera_manager = CameraManager()
