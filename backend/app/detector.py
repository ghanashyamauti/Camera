import cv2
import time
import threading
import numpy as np
from typing import List, Dict, Any, Tuple
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{mins}m {secs}s"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins}m"

class ObjectDetector:
    def __init__(self):
        self.model = None
        self.confidence_thresh = settings.DETECTION_CONFIDENCE
        self._zone_timers: Dict[str, Dict[str, Any]] = {}
        self._infer_lock = threading.Lock()
        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            model_path = str(settings.BASE_DIR / "yolov8n.pt")
            logger.info(f"Loading YOLOv8n model from {model_path}...")
            self.model = YOLO(model_path)
            logger.info("YOLOv8n model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}. Will use presence fallback.")
            self.model = None

    def get_available_classes(self) -> List[str]:
        if self.model is not None and hasattr(self.model, "names"):
            return list(self.model.names.values())
        return [
            "person", "bicycle", "car", "motorcycle", "bus", "truck",
            "backpack", "handbag", "suitcase", "bottle", "cup",
            "chair", "couch", "bed", "dining table", "laptop", "cell phone", "book"
        ]

    def reset_timers(self, prefix: str, active_ids: List[str]):
        active_keys = {f"{prefix}:{zid}" for zid in active_ids}
        stale = [k for k in list(self._zone_timers.keys()) if k.startswith(f"{prefix}:") and k not in active_keys]
        for k in stale:
            del self._zone_timers[k]

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if frame is None:
            return []

        h, w = frame.shape[:2]
        detected = []

        if self.model is not None:
            try:
                with self._infer_lock:
                    results = self.model(frame, verbose=False, conf=self.confidence_thresh, imgsz=640)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = r.names[cls_id]
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].tolist()

                        detected.append({
                            "label": cls_name,
                            "confidence": round(conf, 2),
                            "bbox": [
                                max(0.0, xyxy[0] / w),
                                max(0.0, xyxy[1] / h),
                                min(1.0, xyxy[2] / w),
                                min(1.0, xyxy[3] / h)
                            ],
                            "pixel_bbox": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
                        })
                return detected
            except Exception as e:
                logger.error(f"YOLO inference error: {e}")

        # Fallback: motion/presence detection if model fails
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (21, 21), 0)
            if not hasattr(self, '_prev_gray') or self._prev_gray is None:
                self._prev_gray = blurred
                return detected

            frame_diff = cv2.absdiff(self._prev_gray, blurred)
            thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                if cv2.contourArea(c) < 1200:
                    continue
                (x, y, cw, ch) = cv2.boundingRect(c)
                detected.append({
                    "label": "object",
                    "confidence": 0.85,
                    "bbox": [x / w, y / h, (x + cw) / w, (y + ch) / h],
                    "pixel_bbox": [x, y, x + cw, y + ch]
                })
            self._prev_gray = blurred
        except Exception:
            pass

        return detected

    def _object_in_polygon(self, obj_bbox: List[int], poly_pts: np.ndarray) -> bool:
        ox1, oy1, ox2, oy2 = obj_bbox
        cx = (ox1 + ox2) / 2.0
        cy = (oy1 + oy2) / 2.0
        # Check center point + bottom-center (feet/base of standing objects) + corners
        test_points = [
            (cx, cy),
            (cx, float(oy2) - (oy2 - oy1) * 0.15),
            (cx, float(oy1) + (oy2 - oy1) * 0.25),
        ]
        for pt in test_points:
            if cv2.pointPolygonTest(poly_pts, pt, False) >= 0:
                return True
        return False

    def _object_in_rect(self, obj_bbox: List[int], rect_box: Tuple[int, int, int, int]) -> bool:
        zx1, zy1, zx2, zy2 = rect_box
        ox1, oy1, ox2, oy2 = obj_bbox
        zone_area = max(1, (zx2 - zx1) * (zy2 - zy1))

        obj_cx = (ox1 + ox2) / 2.0
        obj_cy = (oy1 + oy2) / 2.0
        center_inside = (zx1 <= obj_cx <= zx2) and (zy1 <= obj_cy <= zy2)

        ix1 = max(zx1, ox1)
        iy1 = max(zy1, oy1)
        ix2 = min(zx2, ox2)
        iy2 = min(zy2, oy2)

        overlap_ratio = 0.0
        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            obj_area = max(1, (ox2 - ox1) * (oy2 - oy1))
            overlap_ratio = inter_area / min(zone_area, obj_area)

        return center_inside or overlap_ratio > 0.15

    def evaluate_zones(self, frame: np.ndarray, zones: List[Dict[str, Any]], camera_id: str = "cam-1") -> Tuple[List[Dict[str, Any]], np.ndarray]:
        detected_objects = self.detect(frame)
        return self.evaluate_zones_with_detections(frame, zones, detected_objects, camera_id=camera_id)

    def evaluate_zones_with_detections(
        self,
        frame: np.ndarray,
        zones: List[Dict[str, Any]],
        detected_objects: List[Dict[str, Any]],
        camera_id: str = "cam-1",
    ) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """
        Evaluates all zones (rectangles & custom polygons) simultaneously against pre-computed detections,
        applies per-zone object class filters, tracks state durations per camera, and annotates the frame.
        """
        h, w = frame.shape[:2]
        annotated = frame.copy()
        overlay = annotated.copy()
        now = time.time()

        active_ids = [z["id"] for z in zones]
        self.reset_timers(camera_id, active_ids)

        zone_results = []

        for z in zones:
            zid = z["id"]
            shape = z.get("shape", "rect")
            pts_norm = z.get("points")
            allowed_classes = [c.lower() for c in z.get("allowed_classes", []) if c]

            is_poly = (shape == "polygon" and pts_norm and len(pts_norm) >= 3)

            if is_poly:
                poly_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts_norm], dtype=np.int32)
                xs = poly_pts[:, 0]
                ys = poly_pts[:, 1]
                badge_anchor_x = int(np.min(xs))
                badge_anchor_y = int(np.min(ys))
            else:
                zx1 = int(z.get("x", 0) * w)
                zy1 = int(z.get("y", 0) * h)
                zw = int(z.get("width", 0) * w)
                zh = int(z.get("height", 0) * h)
                zx2 = min(w, zx1 + zw)
                zy2 = min(h, zy1 + zh)
                rect_box = (zx1, zy1, zx2, zy2)
                badge_anchor_x = zx1
                badge_anchor_y = zy1

            zone_objects = []
            for obj in detected_objects:
                # Apply per-zone object class filter if configured
                if allowed_classes and obj["label"].lower() not in allowed_classes:
                    continue

                if is_poly:
                    matched = self._object_in_polygon(obj["pixel_bbox"], poly_pts)
                else:
                    matched = self._object_in_rect(obj["pixel_bbox"], rect_box)

                if matched:
                    zone_objects.append(obj)

            is_occupied = len(zone_objects) > 0
            status = "occupied" if is_occupied else "empty"

            # Duration & Absence Tracking (namespaced by camera_id)
            timer_key = f"{camera_id}:{zid}"
            timer = self._zone_timers.get(timer_key)
            if timer is None or timer["status"] != status:
                self._zone_timers[timer_key] = {"status": status, "since": now}
                duration_sec = 0
                since_ts = now
            else:
                since_ts = timer["since"]
                duration_sec = int(now - since_ts)

            dur_str = format_duration(duration_sec)

            # Vibrant Green (Occupied) / Vibrant Red (Empty)
            color = (34, 197, 94) if is_occupied else (68, 68, 239)

            if is_poly:
                cv2.fillPoly(overlay, [poly_pts], color)
                cv2.polylines(annotated, [poly_pts], isClosed=True, color=color, thickness=3)
            else:
                cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), color, -1)
                cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), color, 3)

            zname = z.get("name", "Zone")
            if is_occupied:
                top_obj = max(zone_objects, key=lambda o: o["confidence"])
                badge_text = f"{zname}: {top_obj['label'].upper()} ({int(top_obj['confidence']*100)}%) | {dur_str}"
            else:
                badge_text = f"{zname}: EMPTY | {dur_str}"

            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            bx1 = max(0, min(w - tw - 16, badge_anchor_x))
            by2 = max(th + 12, badge_anchor_y)
            by1 = max(0, by2 - th - 12)
            cv2.rectangle(annotated, (bx1, by1), (bx1 + tw + 14, by2), color, -1)
            cv2.putText(
                annotated,
                badge_text,
                (bx1 + 7, by2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

            zone_results.append({
                "id": zid,
                "name": zname,
                "shape": shape,
                "occupied": is_occupied,
                "status": status,
                "duration_seconds": duration_sec,
                "since_timestamp": since_ts,
                "allowed_classes": z.get("allowed_classes", []),
                "detected_objects": [
                    {
                        "label": o["label"],
                        "confidence": o["confidence"],
                        "bbox": o["bbox"]
                    } for o in zone_objects
                ],
                "x": z.get("x", 0.0),
                "y": z.get("y", 0.0),
                "width": z.get("width", 0.0),
                "height": z.get("height", 0.0),
                "points": pts_norm
            })

        # Blend overlay (30% opacity)
        if len(zones) > 0:
            cv2.addWeighted(overlay, 0.30, annotated, 0.70, 0, annotated)

        # Draw subtle boxes around detected objects
        for obj in detected_objects:
            ox1, oy1, ox2, oy2 = obj["pixel_bbox"]
            cv2.rectangle(annotated, (ox1, oy1), (ox2, oy2), (220, 220, 220), 1)
            label_tag = f"{obj['label']} {int(obj['confidence']*100)}%"
            cv2.putText(annotated, label_tag, (ox1, max(14, oy1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)

        return zone_results, annotated

detector = ObjectDetector()
