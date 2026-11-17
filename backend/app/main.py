import os
import time
import socket
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.models import ZoneModel, CameraConfigRequest, ManualSnapshotRequest
from app.camera import camera_manager
from app.detector import detector
from app.storage import storage_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Active zones in memory
active_zones: List[Dict[str, Any]] = [
    {
        "id": "zone-main",
        "name": "Detection Zone",
        "x": 0.25,
        "y": 0.25,
        "width": 0.50,
        "height": 0.50,
        "active": True
    }
]

# Track previous state for auto-snapshotting on state change
zone_states: Dict[str, Dict[str, Any]] = {}
last_snapshot_time = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up camera service...")
    camera_manager.start()
    yield
    logger.info("Shutting down camera service...")
    camera_manager.stop()

app = FastAPI(title="Camera Thing Detector API", lifespan=lifespan)

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_video_stream():
    """Generates continuous MJPEG stream with live detection and zone overlays"""
    global zone_states, last_snapshot_time
    import cv2

    while True:
        try:
            ret, frame = camera_manager.get_latest_frame()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            # Evaluate zones and get annotated frame
            current_zones = [z for z in active_zones if z.get("active", True)]
            eval_results, annotated_frame = detector.evaluate_zones(frame, current_zones)

            # Check for auto-snapshot events (when zone becomes occupied)
            now = time.time()
            for res in eval_results:
                zid = res["id"]
                prev_status = zone_states.get(zid, {}).get("status", "empty")
                curr_status = res["status"]

                is_new_detection = (prev_status == "empty" and curr_status == "occupied")
                cooldown_passed = (now - last_snapshot_time > settings.AUTO_SNAPSHOT_COOLDOWN)

                if curr_status == "occupied" and (is_new_detection or cooldown_passed):
                    labels = [o["label"] for o in res["detected_objects"]]
                    snapshot_file = storage_manager.save_snapshot(
                        annotated_frame,
                        zone_name=res["name"],
                        status=curr_status,
                        detected_labels=labels
                    )
                    storage_manager.log_event(
                        zone_id=zid,
                        zone_name=res["name"],
                        status=curr_status,
                        detected_objects=res["detected_objects"],
                        snapshot_filename=snapshot_file
                    )
                    last_snapshot_time = now

                zone_states[zid] = res

            # Encode to JPEG
            success, jpeg_buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not success:
                time.sleep(0.02)
                continue

            frame_bytes = jpeg_buffer.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.03) # ~30 FPS
        except Exception as e:
            time.sleep(0.05)

@app.get("/api/stream")
def video_stream():
    """Stream live annotated video feed as MJPEG"""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/status")
def get_status():
    """Get current camera connection, FPS, and real-time status of all zones"""
    return {
        "connected": camera_manager.is_connected,
        "source": camera_manager.source,
        "fps": round(camera_manager.fps, 1),
        "zones": list(zone_states.values())
    }

@app.get("/api/zones")
def get_zones():
    """Get list of active zones"""
    return active_zones

@app.post("/api/zones")
def update_zones(zones: List[ZoneModel]):
    """Update active zones from React UI"""
    global active_zones
    active_zones = [z.model_dump() for z in zones]
    return {"message": "Zones updated successfully", "count": len(active_zones), "zones": active_zones}

@app.get("/api/camera/config")
def get_camera_config():
    return {
        "source": camera_manager.source,
        "is_connected": camera_manager.is_connected,
        "confidence": detector.confidence_thresh,
        "default_rtsp": settings.CAMERA_SOURCE,
        "camera_ip": settings.CAMERA_IP,
        "camera_user": settings.CAMERA_USER,
        "camera_password": settings.CAMERA_PASSWORD
    }

@app.post("/api/camera/config")
def set_camera_config(req: CameraConfigRequest):
    camera_manager.set_source(req.source)
    if req.confidence is not None:
        detector.confidence_thresh = req.confidence
    return {
        "message": f"Camera source updated to {req.source}",
        "confidence": detector.confidence_thresh
    }

@app.get("/api/snapshots")
def list_snapshots(limit: int = 50):
    return storage_manager.get_snapshots(limit=limit)

@app.get("/api/snapshots/{filename}")
def serve_snapshot(filename: str):
    file_path = settings.SNAPSHOTS_DIR / os.path.basename(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(file_path, media_type="image/jpeg")

@app.delete("/api/snapshots/{filename}")
def delete_snapshot(filename: str):
    success = storage_manager.delete_snapshot(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"message": "Snapshot deleted"}

@app.post("/api/snapshot/manual")
def trigger_manual_snapshot(req: ManualSnapshotRequest = None):
    ret, frame = camera_manager.get_latest_frame()
    if not ret or frame is None:
        raise HTTPException(status_code=400, detail="No active frame available to snapshot")

    # Evaluate zones to annotate frame
    current_zones = [z for z in active_zones if z.get("active", True)]
    eval_results, annotated = detector.evaluate_zones(frame, current_zones)
    
    occupied_count = sum(1 for r in eval_results if r["occupied"])
    status = "occupied" if occupied_count > 0 else "empty"

    all_labels = []
    for r in eval_results:
        all_labels.extend([o["label"] for o in r.get("detected_objects", [])])

    filename = storage_manager.save_snapshot(
        annotated,
        zone_name="manual",
        status=status,
        detected_labels=all_labels
    )
    storage_manager.log_event(
        zone_id="manual",
        zone_name="Manual Snapshot",
        status=status,
        detected_objects=[],
        snapshot_filename=filename
    )
    return {"message": "Snapshot saved successfully", "filename": filename, "url": f"/api/snapshots/{filename}"}

@app.get("/api/events")
def list_events(limit: int = 50):
    return storage_manager.get_recent_events(limit=limit)

@app.post("/api/network/scan")
def scan_network_for_camera():
    """
    Scans common IP addresses and ports to find CP PLUS or ONVIF camera
    """
    candidates = [
        "192.168.1.250", # CP PLUS default static IP
        "192.168.0.250",
        "192.168.1.100",
        "192.168.0.100",
        "192.168.1.101",
        "192.168.0.101",
        "192.168.1.1",
        "192.168.0.1"
    ]
    found = []
    ports = [554, 80, 8899, 37777] # RTSP, HTTP, ONVIF, Dahua/CP PLUS media port

    for ip in candidates:
        for p in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)
                res = s.connect_ex((ip, p))
                s.close()
                if res == 0:
                    found.append({"ip": ip, "port": p})
            except Exception:
                pass

    return {
        "status": "scan complete",
        "found_devices": found,
        "recommended_rtsp": [
            f"rtsp://{settings.CAMERA_USER}:{settings.CAMERA_PASSWORD}@{d['ip']}:554/cam/realmonitor?channel=1&subtype=1"
            for d in found if d["port"] in [554, 80]
        ]
    }
