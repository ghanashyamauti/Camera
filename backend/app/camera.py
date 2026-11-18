import cv2
import os
import time
import threading
import logging
import numpy as np
from typing import Optional, Tuple, Dict, List, Any, Callable
from app.config import settings
from app.database import SessionLocal, CameraRecord, ZoneRecord
from app.crypto import encrypt_secret, decrypt_secret
from app.discovery import auto_detect_camera, is_port_open

logger = logging.getLogger(__name__)


class CameraWorker:
    """
    Scalable per-camera engine:
    - Thread 1 (_capture_loop): Reads RTSPS/RTSP frames continuously at native FPS.
    - Thread 2 (_ai_loop): Evaluates YOLOv8 + zones at AI_DETECTION_INTERVAL and caches
      both the evaluated zone state and pre-encoded annotated JPEG bytes.
    - Any number of browser viewers simply stream the cached JPEG bytes with ZERO extra CPU!
    """

    def __init__(
        self,
        cam_id: str,
        name: str,
        ip: str,
        port: int,
        username: str,
        password: str,
        protocol: str = "rtsps",
        subtype: str = "1",
        stream_path: Optional[str] = None,
        manufacturer: Optional[str] = None,
        model: Optional[str] = None,
        enabled: bool = True,
        on_zone_eval: Optional[Callable[[str, str, List[Dict[str, Any]], np.ndarray], None]] = None,
        get_zones_cb: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    ):
        self.id = cam_id
        self.name = name
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol or "rtsps"
        self.subtype = subtype or "1"
        self.stream_path = stream_path or f"/video/live?channel=1&subtype={self.subtype}&unicast=true&proto=Onvif&tls=true"
        self.manufacturer = manufacturer
        self.model = model
        self.enabled = enabled

        self._on_zone_eval = on_zone_eval
        self._get_zones_cb = get_zones_cb

        self.cap: Optional[cv2.VideoCapture] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.latest_jpeg: Optional[bytes] = None
        self.latest_zone_states: List[Dict[str, Any]] = []
        self.latest_detected_objects: List[Dict[str, Any]] = []

        self.is_running = False
        self.is_connected = False
        self.fps = 0.0
        self.status_message = "Initializing..."

        self.lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        self.ai_thread: Optional[threading.Thread] = None
        self.last_reconnect_attempt = 0.0

    @property
    def full_url(self) -> str:
        path = self.stream_path if self.stream_path.startswith("/") else f"/{self.stream_path}"
        return f"{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}{path}"

    def to_public_dict(self) -> Dict[str, Any]:
        """Never exposes plaintext password to frontend."""
        with self.lock:
            zones_snapshot = list(self.latest_zone_states)
        return {
            "id": self.id,
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "username": self.username,
            "protocol": self.protocol,
            "subtype": self.subtype,
            "stream_path": self.stream_path,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "enabled": self.enabled,
            "connected": self.is_connected,
            "fps": round(self.fps, 1),
            "status_message": self.status_message,
            "zones": zones_snapshot,
        }

    def start(self):
        if self.is_running or not self.enabled:
            return
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name=f"cap-{self.id}")
        self.ai_thread = threading.Thread(target=self._ai_loop, daemon=True, name=f"ai-{self.id}")
        self.capture_thread.start()
        self.ai_thread.start()
        logger.info(f"[{self.id}] Started capture & AI workers for {self.name} ({self.ip})")

    def stop(self):
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.5)
        if self.ai_thread:
            self.ai_thread.join(timeout=1.5)
        self._release_cap()
        self.is_connected = False
        self.fps = 0.0
        logger.info(f"[{self.id}] Stopped workers")

    def _release_cap(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _open_stream(self) -> bool:
        if not is_port_open(self.ip, self.port, timeout=1.8):
            self.status_message = f"Unreachable ({self.ip}:{self.port})"
            self.is_connected = False
            return False

        self.status_message = f"Connecting to {self.ip}..."
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|"
            "fflags;nobuffer|"
            "flags;low_delay|"
            "max_delay;0|"
            "framedrop;1|"
            "reorder_queue_size;0|"
            "stimeout;5000000"
        )

        # 1. Try stored URL directly (primary path)
        for attempt in range(2):
            try:
                cap = cv2.VideoCapture(self.full_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        self.cap = cap
                        self.is_connected = True
                        self.status_message = "Live Stream Active"
                        with self.lock:
                            self.latest_raw_frame = frame
                        logger.info(f"[{self.id}] Connected via {self.protocol.upper()}://{self.ip}:{self.port}")
                        return True
                cap.release()
            except Exception as e:
                logger.debug(f"[{self.id}] Direct open attempt {attempt+1} failed: {e}")
            time.sleep(0.5)

        self.status_message = f"Waiting for stream on {self.ip}..."
        self.is_connected = False
        return False

    def _sync_discovered_to_db(self):
        db = SessionLocal()
        try:
            rec = db.query(CameraRecord).filter(CameraRecord.id == self.id).first()
            if rec:
                rec.protocol = self.protocol
                rec.port = self.port
                rec.stream_path = self.stream_path
                rec.manufacturer = self.manufacturer
                rec.model = self.model
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _make_placeholder_jpeg(self) -> bytes:
        frame = np.full((540, 960, 3), (15, 23, 42), dtype=np.uint8)
        cv2.putText(frame, f"{self.name} ({self.ip})", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (226, 232, 240), 2, cv2.LINE_AA)
        cv2.putText(frame, self.status_message, (40, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (148, 163, 184), 1, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return buf.tobytes() if ok else b""

    def _capture_loop(self):
        fps_counter = 0
        fps_timer = time.time()
        consecutive_fails = 0

        while self.is_running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    consecutive_fails = 0
                    with self.lock:
                        self.latest_raw_frame = frame
                        self.is_connected = True
                    fps_counter += 1
                    elapsed = time.time() - fps_timer
                    if elapsed >= 1.0:
                        self.fps = fps_counter / elapsed
                        fps_counter = 0
                        fps_timer = time.time()
                    continue
                else:
                    consecutive_fails += 1
                    if consecutive_fails < 5:
                        time.sleep(0.04)
                        continue
                    # 5 consecutive failed frame reads -> connection genuinely broken
                    self._release_cap()
                    self.is_connected = False
                    self.fps = 0.0
                    self.status_message = "Stream interrupted, reconnecting..."
                    consecutive_fails = 0

            now = time.time()
            if now - self.last_reconnect_attempt > 3.0:
                self.last_reconnect_attempt = now
                self._open_stream()

            if not self.is_connected:
                placeholder = self._make_placeholder_jpeg()
                with self.lock:
                    self.latest_jpeg = placeholder
                time.sleep(0.35)

    def _ai_loop(self):
        """
        Decoupled rendering + AI inference loop:
        - Runs YOLOv8 detection at AI_DETECTION_INTERVAL (e.g. 4x/sec) for low CPU scaling.
        - Re-renders smooth annotated JPEG frames at ~20 FPS using the latest cached detections.
        """
        from app.detector import detector

        last_ai_time = 0.0
        cached_detections: List[Dict[str, Any]] = []

        while self.is_running:
            if not self.is_connected:
                time.sleep(0.15)
                continue

            with self.lock:
                frame = self.latest_raw_frame.copy() if self.latest_raw_frame is not None else None

            if frame is None:
                time.sleep(0.05)
                continue

            try:
                now = time.time()
                zones = self._get_zones_cb(self.id) if self._get_zones_cb else []

                if now - last_ai_time >= settings.AI_DETECTION_INTERVAL:
                    cached_detections = detector.detect(frame)
                    last_ai_time = now

                eval_results, annotated = detector.evaluate_zones_with_detections(
                    frame,
                    zones,
                    cached_detections,
                    camera_id=self.id,
                )

                ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                jpeg_bytes = buf.tobytes() if ok else None

                with self.lock:
                    self.latest_zone_states = eval_results
                    self.latest_detected_objects = cached_detections
                    if jpeg_bytes:
                        self.latest_jpeg = jpeg_bytes

                if self._on_zone_eval and zones:
                    self._on_zone_eval(self.id, self.name, eval_results, annotated)
            except Exception as e:
                logger.error(f"[{self.id}] AI loop error: {e}")

            time.sleep(0.045)  # ~20 FPS smooth output per camera

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_jpeg

    def get_latest_raw_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self.lock:
            if self.latest_raw_frame is not None:
                return True, self.latest_raw_frame.copy()
            return False, None


class DynamicCameraManager:
    """
    PostgreSQL-backed Multi-Camera Manager.
    Zero hardcoded cameras in code or .env — all cameras are stored in PostgreSQL
    with encrypted credentials and started/stopped dynamically.
    """

    def __init__(self):
        self.workers: Dict[str, CameraWorker] = {}
        self.lock = threading.Lock()
        self._on_zone_eval: Optional[Callable] = None
        self._get_zones_cb: Optional[Callable] = None

    def configure_callbacks(self, on_zone_eval: Callable, get_zones_cb: Callable):
        self._on_zone_eval = on_zone_eval
        self._get_zones_cb = get_zones_cb

    def load_from_db_and_start(self):
        db = SessionLocal()
        try:
            records = db.query(CameraRecord).order_by(CameraRecord.created_at.asc()).all()
            with self.lock:
                for rec in records:
                    worker = self._build_worker(rec)
                    self.workers[rec.id] = worker
                    if rec.enabled:
                        worker.start()
            logger.info(f"Loaded {len(records)} dynamic camera(s) from PostgreSQL.")
        finally:
            db.close()

    def stop_all(self):
        with self.lock:
            for w in self.workers.values():
                w.stop()
            self.workers.clear()

    def _build_worker(self, rec: CameraRecord) -> CameraWorker:
        return CameraWorker(
            cam_id=rec.id,
            name=rec.name,
            ip=rec.ip,
            port=rec.port,
            username=rec.username,
            password=decrypt_secret(rec.password_enc),
            protocol=rec.protocol,
            subtype=rec.subtype,
            stream_path=rec.stream_path,
            manufacturer=rec.manufacturer,
            model=rec.model,
            enabled=rec.enabled,
            on_zone_eval=self._on_zone_eval,
            get_zones_cb=self._get_zones_cb,
        )

    def list_cameras(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [w.to_public_dict() for w in self.workers.values()]

    def get_worker(self, cam_id: Optional[str] = None) -> Optional[CameraWorker]:
        with self.lock:
            if cam_id and cam_id in self.workers:
                return self.workers[cam_id]
            if self.workers:
                return next(iter(self.workers.values()))
            return None

    def add_camera(
        self,
        name: str,
        ip: str,
        username: str,
        password: str,
        subtype: str = "1",
        auto_detect: bool = True,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        stream_path: Optional[str] = None,
    ) -> Tuple[CameraWorker, Dict[str, Any]]:
        """
        Auto-detects port, protocol (RTSPS/RTSP), model, and stream path if requested,
        encrypts the password, saves to PostgreSQL, and launches the worker immediately.
        """
        detection_info: Dict[str, Any] = {}
        if auto_detect or not stream_path:
            detection_info = auto_detect_camera(ip, username, password, preferred_subtype=subtype)
            port = port or detection_info["port"]
            protocol = protocol or detection_info["protocol"]
            stream_path = stream_path or detection_info["stream_path"]
        else:
            port = port or 554
            protocol = protocol or "rtsps"

        cam_id = f"cam-{int(time.time() * 1000) % 1000000}"

        db = SessionLocal()
        try:
            while db.query(CameraRecord).filter(CameraRecord.id == cam_id).first():
                cam_id = f"cam-{int(time.time() * 1000) % 1000000 + 1}"

            rec = CameraRecord(
                id=cam_id,
                name=name.strip(),
                ip=ip.strip(),
                port=int(port),
                username=username.strip(),
                password_enc=encrypt_secret(password),
                protocol=protocol,
                subtype=str(subtype),
                stream_path=stream_path,
                manufacturer=detection_info.get("manufacturer"),
                model=detection_info.get("model"),
                enabled=True,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)

            worker = self._build_worker(rec)
            with self.lock:
                self.workers[rec.id] = worker
            worker.start()
            return worker, detection_info
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_camera(
        self,
        cam_id: str,
        name: Optional[str] = None,
        ip: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        subtype: Optional[str] = None,
        enabled: Optional[bool] = None,
        re_detect: bool = False,
    ) -> Optional[CameraWorker]:
        db = SessionLocal()
        try:
            rec = db.query(CameraRecord).filter(CameraRecord.id == cam_id).first()
            if not rec:
                return None

            creds_changed = False
            if name is not None:
                rec.name = name.strip()
            if ip is not None and ip.strip() != rec.ip:
                rec.ip = ip.strip()
                creds_changed = True
            if username is not None and username.strip() != rec.username:
                rec.username = username.strip()
                creds_changed = True
            if password is not None and password != "":
                rec.password_enc = encrypt_secret(password)
                creds_changed = True
            if subtype is not None and str(subtype) != rec.subtype:
                rec.subtype = str(subtype)
                creds_changed = True
            if enabled is not None:
                rec.enabled = enabled

            if re_detect or creds_changed:
                plain_pwd = decrypt_secret(rec.password_enc)
                probe = auto_detect_camera(rec.ip, rec.username, plain_pwd, preferred_subtype=rec.subtype)
                rec.port = probe["port"]
                rec.protocol = probe["protocol"]
                rec.stream_path = probe["stream_path"]
                if probe.get("manufacturer"):
                    rec.manufacturer = probe["manufacturer"]
                if probe.get("model"):
                    rec.model = probe["model"]

            db.commit()
            db.refresh(rec)

            with self.lock:
                old = self.workers.pop(cam_id, None)
                if old:
                    old.stop()
                worker = self._build_worker(rec)
                self.workers[rec.id] = worker
                if rec.enabled:
                    worker.start()
            return worker
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def remove_camera(self, cam_id: str) -> bool:
        db = SessionLocal()
        try:
            rec = db.query(CameraRecord).filter(CameraRecord.id == cam_id).first()
            if not rec:
                return False
            db.delete(rec)
            db.commit()

            with self.lock:
                old = self.workers.pop(cam_id, None)
            if old:
                old.stop()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


camera_manager = DynamicCameraManager()
