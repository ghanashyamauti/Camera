import cv2
import time
import threading
import logging
import math
import socket
import re
import numpy as np
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

def is_host_reachable(url: str, timeout: float = 0.8) -> Tuple[bool, str, int]:
    """
    Fast pre-flight check to see if RTSP host & port are reachable.
    Avoids OpenCV cv2.VideoCapture 30-second blocking freeze!
    """
    try:
        # Match rtsp://[user:pass@]host[:port][/path]
        match = re.search(r"rtsp://(?:[^@]+@)?([^:/]+)(?::(\d+))?", url)
        if not match:
            return False, "", 0
        host = match.group(1)
        port = int(match.group(2)) if match.group(2) else 554

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True, host, port
    except Exception:
        return False, "", 0

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

    def _connect_capture(self) -> bool:
        self._release_cap()
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

        # RTSP stream: First do fast socket pre-flight check!
        reachable, host, port = is_host_reachable(src, timeout=0.8)
        if not reachable:
            logger.warning(f"RTSP target host {host}:{port} is unreachable over current network.")
            self.status_message = f"Camera unreachable at {host}:{port}. Connect to router Wi-Fi."
            self.is_connected = False
            return False

        # Host is reachable, now connect OpenCV safely
        logger.info(f"Host {host}:{port} reachable. Opening RTSP stream...")
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        candidates = [src]
        if "rtsp://" in src and src.count("@") > 1:
            proto, rest = src.split("://", 1)
            last_at_idx = rest.rfind("@")
            if last_at_idx != -1:
                user_pass = rest[:last_at_idx]
                host_path = rest[last_at_idx + 1:]
                if ":" in user_pass:
                    u, p = user_pass.split(":", 1)
                    encoded_p = p.replace("@", "%40")
                    candidates.insert(0, f"{proto}://{u}:{encoded_p}@{host_path}")

        # Add alternative stream path candidates if standard one fails
        if "rtsp://" in src:
            base_url = src.split("?")[0]
            if "/" in base_url.replace("://", ""):
                # Extract root url up to host:port
                m = re.match(r"(rtsp://[^/]+)", src)
                if m:
                    root = m.group(1)
                    alt_paths = [
                        f"{root}/cam/realmonitor?channel=1&subtype=0",
                        f"{root}/cam/realmonitor?channel=1&subtype=1",
                        f"{root}/live",
                        f"{root}/onvif1",
                        f"{root}/Streaming/Channels/101"
                    ]
                    for ap in alt_paths:
                        if ap not in candidates:
                            candidates.append(ap)

        for candidate in candidates:
            cap = cv2.VideoCapture(candidate, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                self.cap = cap
                self.is_connected = True
                self.status_message = "CP PLUS Camera Connected"
                logger.info(f"Stream opened successfully with: {candidate}")
                return True
            else:
                try:
                    cap.release()
                except Exception:
                    pass

        self.status_message = "RTSP Authentication Failed (Check password)"
        self.is_connected = False
        return False

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        Generates continuous test room scene with moving objects so the user
        ALWAYS gets a live, interactive video feed without freezing.
        """
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

        # Moving Person / Package
        obj_x = int(340 + math.sin(self.demo_tick * 0.04) * 200)
        obj_y = int(270 + math.cos(self.demo_tick * 0.02) * 45)
        cv2.circle(frame, (obj_x + 40, obj_y - 30), 20, (190, 140, 80), -1)
        cv2.rectangle(frame, (obj_x + 15, obj_y - 10), (obj_x + 65, obj_y + 80), (60, 130, 200), -1)
        cv2.putText(frame, "person", (obj_x + 18, obj_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Status Banner at bottom
        is_rtsp = self.source.startswith("rtsp://")
        if is_rtsp and not self.is_connected:
            banner_text = f"STANDBY: {self.status_message}"
            color = (50, 50, 220)
        else:
            banner_text = "SIMULATION DEMO MODE - Draw boxes over the chair or car to test!"
            color = (40, 150, 40)

        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (235, 240, 245), -1)
        cv2.rectangle(frame, (10, h - 35), (w - 10, h - 10), (200, 210, 220), 1)
        cv2.putText(frame, banner_text, (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        time.sleep(0.033) # 30 FPS
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

            # Mode B: Hardware / RTSP / Webcam
            if self.cap is None or not self.cap.isOpened():
                now = time.time()
                if now - self.last_reconnect_attempt > 3.0:
                    self.last_reconnect_attempt = now
                    self._connect_capture()

                # Always generate smooth standby frame while connecting so stream never drops!
                frame = self._generate_synthetic_frame()
                with self.lock:
                    self.latest_raw_frame = frame
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    self.fps = fps_counter / (time.time() - fps_timer)
                    fps_counter = 0
                    fps_timer = time.time()
                continue

            # Mode C: Reading active camera hardware frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.warning("Frame read failed from camera. Reconnecting...")
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
