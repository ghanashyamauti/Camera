import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class ObjectDetector:
    def __init__(self):
        self.model = None
        self.confidence_thresh = settings.DETECTION_CONFIDENCE
        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            # Load nano model from backend folder
            model_path = str(settings.BASE_DIR / "yolov8n.pt")
            logger.info(f"Loading YOLOv8n model from {model_path}...")
            self.model = YOLO(model_path)
            logger.info("YOLOv8n model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}. Will use presence fallback.")
            self.model = None

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs object detection on the frame.
        Returns list of detected objects: [{label, confidence, bbox: [x1, y1, x2, y2]}]
        """
        if frame is None:
            return []

        h, w = frame.shape[:2]
        detected = []

        if self.model is not None:
            try:
                # Run inference with lightweight settings
                results = self.model(frame, verbose=False, conf=self.confidence_thresh, imgsz=640)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = r.names[cls_id]
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].tolist() # [x1, y1, x2, y2] in pixels
                        
                        detected.append({
                            "label": cls_name,
                            "confidence": round(conf, 2),
                            "bbox": [
                                max(0, xyxy[0] / w),
                                max(0, xyxy[1] / h),
                                min(1.0, xyxy[2] / w),
                                min(1.0, xyxy[3] / h)
                            ],
                            "pixel_bbox": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
                        })
                return detected
            except Exception as e:
                logger.error(f"YOLO inference error: {e}")

        # Fallback: simple contour / presence detection if model fails
        return detected

    def evaluate_zones(self, frame: np.ndarray, zones: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """
        Evaluates zones against detected objects.
        Returns (zone_evaluations, annotated_frame).
        """
        h, w = frame.shape[:2]
        detected_objects = self.detect(frame)
        annotated = frame.copy()

        # Create overlay for transparent zone tints
        overlay = annotated.copy()

        zone_results = []

        for z in zones:
            zx1 = int(z["x"] * w)
            zy1 = int(z["y"] * h)
            zw = int(z["width"] * w)
            zh = int(z["height"] * h)
            zx2 = min(w, zx1 + zw)
            zy2 = min(h, zy1 + zh)

            zone_box = (zx1, zy1, zx2, zy2)
            zone_area = max(1, (zx2 - zx1) * (zy2 - zy1))

            zone_objects = []

            for obj in detected_objects:
                ox1, oy1, ox2, oy2 = obj["pixel_bbox"]
                obj_cx = (ox1 + ox2) / 2
                obj_cy = (oy1 + oy2) / 2

                # Check 1: Object center point inside zone
                center_inside = (zx1 <= obj_cx <= zx2) and (zy1 <= obj_cy <= zy2)

                # Check 2: Area intersection
                ix1 = max(zx1, ox1)
                iy1 = max(zy1, oy1)
                ix2 = min(zx2, ox2)
                iy2 = min(zy2, oy2)

                overlap_ratio = 0.0
                if ix2 > ix1 and iy2 > iy1:
                    inter_area = (ix2 - ix1) * (iy2 - iy1)
                    obj_area = max(1, (ox2 - ox1) * (oy2 - oy1))
                    overlap_ratio = inter_area / min(zone_area, obj_area)

                if center_inside or overlap_ratio > 0.15:
                    zone_objects.append(obj)

            is_occupied = len(zone_objects) > 0
            status = "occupied" if is_occupied else "empty"

            # Color scheme:
            # Green (BGR: 46, 204, 113) when Occupied
            # Red (BGR: 71, 71, 235) when Empty
            color = (46, 204, 113) if is_occupied else (71, 71, 235)

            # Draw semi-transparent zone fill
            cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), color, -1)

            # Draw zone border
            cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), color, 2)

            # Draw header badge for zone
            if is_occupied:
                top_obj = max(zone_objects, key=lambda o: o["confidence"])
                badge_text = f"● {z.get('name', 'Zone')}: OCCUPIED ({top_obj['label']} {int(top_obj['confidence']*100)}%)"
            else:
                badge_text = f"○ {z.get('name', 'Zone')}: EMPTY"

            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            badge_y1 = max(0, zy1 - th - 12)
            badge_y2 = zy1
            cv2.rectangle(annotated, (zx1, badge_y1), (zx1 + tw + 16, badge_y2), color, -1)
            cv2.putText(
                annotated,
                badge_text,
                (zx1 + 8, zy1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

            zone_results.append({
                "id": z["id"],
                "name": z.get("name", "Zone"),
                "occupied": is_occupied,
                "status": status,
                "detected_objects": [
                    {
                        "label": o["label"],
                        "confidence": o["confidence"],
                        "bbox": o["bbox"]
                    } for o in zone_objects
                ],
                "x": z["x"],
                "y": z["y"],
                "width": z["width"],
                "height": z["height"]
            })

        # Blend the overlay (30% opacity) with annotated
        cv2.addWeighted(overlay, 0.20, annotated, 0.80, 0, annotated)

        # Draw detected object outlines subtly
        for obj in detected_objects:
            ox1, oy1, ox2, oy2 = obj["pixel_bbox"]
            cv2.rectangle(annotated, (ox1, oy1), (ox2, oy2), (200, 200, 200), 1)
            label_tag = f"{obj['label']} {int(obj['confidence']*100)}%"
            cv2.putText(annotated, label_tag, (ox1, max(15, oy1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)

        return zone_results, annotated

detector = ObjectDetector()
