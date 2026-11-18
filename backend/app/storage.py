import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
from app.config import settings
from app.database import SessionLocal, EventRecord


class StorageManager:
    def __init__(self):
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        zone_id: str,
        zone_name: str,
        status: str,
        detected_objects: list,
        snapshot_filename: Optional[str] = None,
        camera_id: Optional[str] = None,
    ):
        db = SessionLocal()
        try:
            ev = EventRecord(
                camera_id=camera_id,
                zone_id=zone_id,
                zone_name=zone_name,
                status=status,
                detected_objects=detected_objects or [],
                snapshot=snapshot_filename,
                timestamp=datetime.utcnow(),
            )
            db.add(ev)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def save_snapshot(
        self,
        frame: np.ndarray,
        zone_name: str = "zone",
        status: str = "occupied",
        detected_labels: Optional[List[str]] = None,
    ) -> str:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:18]
        labels_tag = "_".join(detected_labels[:2]) if detected_labels else status
        clean_tag = "".join(c for c in labels_tag if c.isalnum() or c == "_")
        filename = f"capture_{timestamp_str}_{clean_tag}.jpg"
        filepath = settings.SNAPSHOTS_DIR / filename
        cv2.imwrite(str(filepath), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return filename

    def get_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        items = []
        files = sorted(
            [f for f in settings.SNAPSHOTS_DIR.glob("*.jpg")],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )[:limit]

        for f in files:
            stat = f.stat()
            dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            items.append({
                "filename": f.name,
                "url": f"/api/snapshots/{f.name}",
                "timestamp": dt,
                "size_kb": round(stat.st_size / 1024, 1),
            })
        return items

    def delete_snapshot(self, filename: str) -> bool:
        safe_name = os.path.basename(filename)
        filepath = settings.SNAPSHOTS_DIR / safe_name
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_recent_events(self, limit: int = 50, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            q = db.query(EventRecord)
            if camera_id:
                q = q.filter(EventRecord.camera_id == camera_id)
            rows = q.order_by(EventRecord.id.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "camera_id": r.camera_id,
                    "zone_id": r.zone_id,
                    "zone_name": r.zone_name,
                    "status": r.status,
                    "detected_objects": r.detected_objects or [],
                    "snapshot": r.snapshot,
                    "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for r in rows
            ]
        finally:
            db.close()


storage_manager = StorageManager()
