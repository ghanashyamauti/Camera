import cv2
import time
import threading
import logging
import math
import numpy as np
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

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
            self.source = new_source
            self._release_cap()
            self.is_connected = False
        logger.info(f"Switched camera source to: {new_source}")

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

        # Demo mode check
        if src.lower() in ["demo", "synthetic", "test"]:
            self.is_connected = True
            return True

        # Webcam check
        if src.isdigit() or src.lower() == "webcam":
            dev_idx = 0 if src.lower() == "webcam" else int(src)
            logger.info(f"Opening webcam device {dev_idx}...")
            self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
        else:
            # RTSP or video file/stream
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

            # Generate candidate URLs (handling @ in password like Admin@123)
            candidates = [src]
            if "rtsp://" in src and src.count("@") > 1:
                # Password has '@' in it. Encode internal '@' as '%40'
                # Format: rtsp://user:pass@host:port/path
                proto, rest = src.split("://", 1)
                last_at_idx = rest.rfind("@")
                if last_at_idx != -1:
                    user_pass = rest[:last_at_idx]
                    host_path = rest[last_at_idx + 1:]
                    if ":" in user_pass:
                        u, p = user_pass.split(":", 1)
                        encoded_p = p.replace("@", "%40")
                        encoded_url = f"{proto}://{u}:{encoded_p}@{host_path}"
                        candidates.insert(0, encoded_url)

            # Try candidate RTSP URLs
            for candidate in candidates:
                logger.info(f"Trying RTSP stream: {candidate}")
                cap = cv2.VideoCapture(candidate, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    self.cap = cap
                    self.is_connected = True
                    logger.info(f"Stream opened successfully with: {candidate}")
                    return True
                else:
                    try:
                        cap.release()
                    except Exception:
                        pass

        if self.cap and self.cap.isOpened():
            self.is_connected = True
            logger.info(f"Stream opened successfully: {src}")
            return True
        else:
            logger.warning(f"Could not open stream: {src}. Will retry.")
            self.is_connected = False
            return False

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        Generates a clean, simulated test room scene with objects (chair, car, person, box)
        moving smoothly to test the Red/Green detection zone without needing hardware.
        """
        self.demo_tick += 1
        w, h = 960, 540
        # Light minimalist clean room background
        frame = np.full((h, w, 3), (245, 247, 250), dtype=np.uint8)

        # Draw grid floor
        for y in range(320, h, 25):
            cv2.line(frame, (0, y), (w, y), (225, 230, 235), 1)

        # Draw simulated window outside (showing a car)
        cv2.rectangle(frame, (40, 40), (280, 220), (210, 225, 240), -1)
        cv2.rectangle(frame, (40, 40), (280, 220), (180, 195, 210), 2)
        cv2.putText(frame, "Window (Driveway)", (50, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 115, 130), 1)

        # Moving car outside window
        car_x = int(50 + (math.sin(self.demo_tick * 0.03) + 1) * 70)
        cv2.rectangle(frame, (car_x, 120), (car_x + 90, 175), (50, 60, 200), -1)
        cv2.putText(frame, "car", (car_x + 10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Stationary Chair in Room
        cv2.rectangle(frame, (680, 260), (790, 420), (120, 80, 60), -1)
        cv2.rectangle(frame, (680, 260), (790, 420), (90, 60, 40), 2)
        cv2.putText(frame, "chair", (710, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Moving Object (e.g. Person / Package moving across the center)
        obj_x = int(320 + math.sin(self.demo_tick * 0.04) * 220)
        obj_y = int(270 + math.cos(self.demo_tick * 0.02) * 50)
        cv2.circle(frame, (obj_x + 40, obj_y - 30), 20, (180, 130, 70), -1) # Head
        cv2.rectangle(frame, (obj_x + 15, obj_y - 10), (obj_x + 65, obj_y + 80), (60, 120, 190), -1) # Body
        cv2.putText(frame, "person", (obj_x + 18, obj_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Status text watermark on demo feed
        cv2.putText(
            frame,
            "[DEMO SIMULATION MODE - Select CP PLUS Camera in Settings once connected]",
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (120, 120, 130),
            1,
            cv2.LINE_AA
        )
        time.sleep(0.033) # ~30 FPS
        return frame

    def _capture_loop(self):
        fps_counter = 0
        fps_timer = time.time()

        while self.is_running:
            # Handle Demo / Synthetic Feed
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

            # Handle Hardware / RTSP / Webcam
            if self.cap is None or not self.cap.isOpened():
                now = time.time()
                if now - self.last_reconnect_attempt > 4.0:
                    self.last_reconnect_attempt = now
                    connected = self._connect_capture()
                    if not connected and self.fallback == "demo":
                        logger.info("RTSP camera offline, using synthetic demo frame temporarily.")
                        frame = self._generate_synthetic_frame()
                        with self.lock:
                            self.latest_raw_frame = frame
                else:
                    time.sleep(0.1)
                continue

            # Read frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.warning("Frame read failed. Retrying connection...")
                self._release_cap()
                self.is_connected = False
                time.sleep(0.5)
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
