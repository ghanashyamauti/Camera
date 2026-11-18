import os
import time
import threading
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db, SessionLocal, ZoneRecord
from app.models import (
    ZoneModel,
    ManualSnapshotRequest,
    CameraProbeRequest,
    CameraCreateRequest,
    CameraUpdateRequest,
)
from app.camera import camera_manager
from app.detector import detector
from app.discovery import auto_detect_camera, discover_lan_cameras
from app.storage import storage_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# In-memory zone cache synced with PostgreSQL so AI threads never hit DB every frame
_zones_cache_lock = threading.Lock()
_zones_cache: Dict[str, List[Dict[str, Any]]] = {}

# Track last status & snapshot time per camera+zone for event logging
_prev_zone_status: Dict[str, str] = {}
_last_snapshot_by_cam: Dict[str, float] = {}


def _load_zones_cache_from_db():
    db = SessionLocal()
    try:
        rows = db.query(ZoneRecord).order_by(ZoneRecord.created_at.asc()).all()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            grouped.setdefault(r.camera_id, []).append({
                "id": r.id,
                "name": r.name,
                "shape": r.shape,
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "points": r.points,
                "allowed_classes": r.allowed_classes or [],
                "active": r.active,
            })
        with _zones_cache_lock:
            _zones_cache.clear()
            _zones_cache.update(grouped)
    finally:
        db.close()


def _get_zones_for_camera(camera_id: str) -> List[Dict[str, Any]]:
    with _zones_cache_lock:
        return [z for z in _zones_cache.get(camera_id, []) if z.get("active", True)]


def _handle_zone_evaluation(camera_id: str, camera_name: str, eval_results: List[Dict[str, Any]], annotated_frame):
    now = time.time()
    last_snap = _last_snapshot_by_cam.get(camera_id, 0.0)

    for res in eval_results:
        zid = res["id"]
        key = f"{camera_id}:{zid}"
        prev_status = _prev_zone_status.get(key, "empty")
        curr_status = res["status"]

        is_new_detection = (prev_status == "empty" and curr_status == "occupied")
        is_cleared = (prev_status == "occupied" and curr_status == "empty")
        cooldown_passed = (now - last_snap > settings.AUTO_SNAPSHOT_COOLDOWN)

        if curr_status == "occupied" and (is_new_detection or cooldown_passed):
            labels = [o["label"] for o in res["detected_objects"]]
            zone_label = f"{camera_name} - {res['name']}"
            snap_file = storage_manager.save_snapshot(
                annotated_frame,
                zone_name=zone_label,
                status=curr_status,
                detected_labels=labels,
            )
            storage_manager.log_event(
                camera_id=camera_id,
                zone_id=key,
                zone_name=zone_label,
                status=curr_status,
                detected_objects=res["detected_objects"],
                snapshot_filename=snap_file,
            )
            _last_snapshot_by_cam[camera_id] = now
            last_snap = now
        elif is_cleared:
            storage_manager.log_event(
                camera_id=camera_id,
                zone_id=key,
                zone_name=f"{camera_name} - {res['name']}",
                status="empty",
                detected_objects=[],
                snapshot_filename=None,
            )

        _prev_zone_status[key] = curr_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing PostgreSQL tables and dynamic multi-camera engine...")
    init_db()
    _load_zones_cache_from_db()
    camera_manager.configure_callbacks(
        on_zone_eval=_handle_zone_evaluation,
        get_zones_cb=_get_zones_for_camera,
    )
    camera_manager.load_from_db_and_start()
    yield
    logger.info("Shutting down camera workers...")
    camera_manager.stop_all()


app = FastAPI(title="Dynamic Multi-Camera AI Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _stream_cached_jpegs(camera_id: str):
    """Zero-latency MJPEG generator: streams fresh pre-rendered frames instantly."""
    last_sent = None
    while True:
        worker = camera_manager.get_worker(camera_id)
        if worker is None:
            break
        jpeg = worker.get_latest_jpeg()
        if jpeg and jpeg is not last_sent:
            last_sent = jpeg
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
        time.sleep(0.025)  # 40 Hz polling for instant sub-50ms frame delivery


# ─── Dynamic Camera CRUD & Auto-Detection ─────────────────────────────────────

@app.get("/api/cameras")
def list_cameras():
    cams = camera_manager.list_cameras()
    with _zones_cache_lock:
        for c in cams:
            c["saved_zones"] = list(_zones_cache.get(c["id"], []))
    return cams


@app.post("/api/cameras/probe")
def probe_camera(req: CameraProbeRequest):
    """Auto-detects port, protocol (RTSPS/RTSP), model, and stream path before adding."""
    return auto_detect_camera(req.ip, req.username, req.password, preferred_subtype=req.subtype)


@app.post("/api/cameras")
def add_camera(req: CameraCreateRequest):
    worker, info = camera_manager.add_camera(
        name=req.name,
        ip=req.ip,
        username=req.username,
        password=req.password,
        subtype=req.subtype,
        auto_detect=req.auto_detect,
        port=req.port,
        protocol=req.protocol,
        stream_path=req.stream_path,
    )
    return {
        "message": f"Added camera {worker.name}",
        "camera": worker.to_public_dict(),
        "auto_detect": info,
    }


@app.put("/api/cameras/{camera_id}")
def update_camera(camera_id: str, req: CameraUpdateRequest):
    worker = camera_manager.update_camera(
        camera_id,
        name=req.name,
        ip=req.ip,
        username=req.username,
        password=req.password,
        subtype=req.subtype,
        enabled=req.enabled,
        re_detect=req.re_detect,
    )
    if not worker:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"message": "Camera updated", "camera": worker.to_public_dict()}


@app.delete("/api/cameras/{camera_id}")
def delete_camera(camera_id: str):
    ok = camera_manager.remove_camera(camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Camera not found")
    with _zones_cache_lock:
        _zones_cache.pop(camera_id, None)
    return {"message": "Camera removed"}


@app.get("/api/cameras/{camera_id}/stream")
def camera_video_stream(camera_id: str):
    if not camera_manager.get_worker(camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")
    return StreamingResponse(
        _stream_cached_jpegs(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ─── Per-Camera Persistent Zones (PostgreSQL) ─────────────────────────────────

@app.get("/api/cameras/{camera_id}/zones")
def get_camera_zones(camera_id: str):
    with _zones_cache_lock:
        return list(_zones_cache.get(camera_id, []))


@app.post("/api/cameras/{camera_id}/zones")
def update_camera_zones(camera_id: str, zones: List[ZoneModel]):
    db = SessionLocal()
    try:
        db.query(ZoneRecord).filter(ZoneRecord.camera_id == camera_id).delete()
        saved = []
        for z in zones:
            rec = ZoneRecord(
                id=z.id,
                camera_id=camera_id,
                name=z.name,
                shape=z.shape,
                x=z.x,
                y=z.y,
                width=z.width,
                height=z.height,
                points=z.points,
                allowed_classes=z.allowed_classes,
                active=z.active,
            )
            db.add(rec)
            saved.append(z.model_dump())
        db.commit()

        with _zones_cache_lock:
            _zones_cache[camera_id] = saved

        return {
            "message": "Zones saved to PostgreSQL",
            "camera_id": camera_id,
            "count": len(saved),
            "zones": saved,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ─── Discovery, Status, Snapshots & Logs ──────────────────────────────────────

@app.post("/api/network/scan")
def scan_network_for_cameras():
    found = discover_lan_cameras()
    return {"status": "scan complete", "found_devices": found}


@app.get("/api/status")
def get_status():
    cams = list_cameras()
    return {
        "connected": any(c["connected"] for c in cams),
        "camera_count": len(cams),
        "confidence": detector.confidence_thresh,
        "cameras": cams,
    }


@app.get("/api/classes")
def get_available_classes():
    return {"classes": detector.get_available_classes()}


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
def trigger_manual_snapshot(req: Optional[ManualSnapshotRequest] = None):
    cam_id = req.camera_id if req else None
    worker = camera_manager.get_worker(cam_id)
    if not worker:
        raise HTTPException(status_code=404, detail="No camera available")

    ret, frame = worker.get_latest_raw_frame()
    if not ret or frame is None:
        raise HTTPException(status_code=400, detail="No active frame available to snapshot")

    zones = _get_zones_for_camera(worker.id)
    eval_results, annotated = detector.evaluate_zones(frame, zones, camera_id=worker.id)
    occupied_count = sum(1 for r in eval_results if r["occupied"])
    status = "occupied" if occupied_count > 0 else "empty"

    all_labels = []
    for r in eval_results:
        all_labels.extend([o["label"] for o in r.get("detected_objects", [])])

    filename = storage_manager.save_snapshot(
        annotated,
        zone_name=f"{worker.name}_manual",
        status=status,
        detected_labels=all_labels,
    )
    storage_manager.log_event(
        camera_id=worker.id,
        zone_id=f"{worker.id}:manual",
        zone_name=f"{worker.name} (Manual)",
        status=status,
        detected_objects=[],
        snapshot_filename=filename,
    )
    return {"message": "Snapshot saved", "filename": filename, "url": f"/api/snapshots/{filename}"}


@app.get("/api/events")
def list_events(limit: int = 50, camera_id: Optional[str] = None):
    return storage_manager.get_recent_events(limit=limit, camera_id=camera_id)


@app.get("/api/events/export")
def export_events_csv(camera_id: Optional[str] = None):
    import csv, io
    events = storage_manager.get_recent_events(limit=500, camera_id=camera_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp", "Camera ID", "Zone ID", "Zone Name", "Status", "Detected Objects", "Snapshot"])
    for ev in events:
        objs = ", ".join([f"{o.get('label')} ({int(o.get('confidence', 0)*100)}%)" for o in ev.get("detected_objects", [])])
        writer.writerow([
            ev.get("timestamp", ""),
            ev.get("camera_id", "") or "",
            ev.get("zone_id", ""),
            ev.get("zone_name", ""),
            ev.get("status", ""),
            objs,
            ev.get("snapshot", "") or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zone_events_log.csv"},
    )
