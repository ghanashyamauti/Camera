import os
import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
from app.config import settings

class StorageManager:
    def __init__(self):
        self.db_path = settings.STORAGE_DIR / "detector.db"
        self._init_db()

    def _init_db(self):
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    zone_name TEXT,
                    status TEXT NOT NULL,
                    detected_objects TEXT,
                    snapshot_filename TEXT
                )
            """)
            conn.commit()

    def log_event(self, zone_id: str, zone_name: str, status: str, detected_objects: list, snapshot_filename: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detection_events (timestamp, zone_id, zone_name, status, detected_objects, snapshot_filename)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                zone_id,
                zone_name,
                status,
                json.dumps(detected_objects),
                snapshot_filename
            ))
            conn.commit()

    def save_snapshot(self, frame: np.ndarray, zone_name: str = "zone", status: str = "occupied", detected_labels: Optional[List[str]] = None) -> str:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
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
            reverse=True
        )[:limit]

        for f in files:
            stat = f.stat()
            dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            items.append({
                "filename": f.name,
                "url": f"/api/snapshots/{f.name}",
                "timestamp": dt,
                "size_kb": round(stat.st_size / 1024, 1)
            })
        return items

    def delete_snapshot(self, filename: str) -> bool:
        # Sanitize filename
        safe_name = os.path.basename(filename)
        filepath = settings.SNAPSHOTS_DIR / safe_name
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM detection_events ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

storage_manager = StorageManager()
