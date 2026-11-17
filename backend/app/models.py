from pydantic import BaseModel, Field
from typing import List, Optional

class ZoneModel(BaseModel):
    id: str
    name: str = "Zone 1"
    # Normalized coordinates [0.0 - 1.0] relative to video width & height
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., ge=0.0, le=1.0)
    height: float = Field(..., ge=0.0, le=1.0)
    active: bool = True

class DetectedObject(BaseModel):
    label: str
    confidence: float
    bbox: List[float] # [x1, y1, x2, y2] normalized
    in_zone: bool = False

class ZoneStatus(BaseModel):
    id: str
    name: str
    occupied: bool
    status: str # "occupied" or "empty"
    detected_objects: List[DetectedObject] = []
    x: float
    y: float
    width: float
    height: float

class CameraConfigRequest(BaseModel):
    source: str # RTSP URL, or "webcam", or "demo"
    confidence: Optional[float] = 0.45

class ManualSnapshotRequest(BaseModel):
    note: Optional[str] = "Manual snapshot"
