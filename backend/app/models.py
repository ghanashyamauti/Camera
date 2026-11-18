from pydantic import BaseModel, Field
from typing import List, Optional

class ZoneModel(BaseModel):
    id: str
    name: str = "Zone 1"
    shape: str = "rect"  # "rect" or "polygon"
    x: float = Field(0.0, ge=0.0, le=1.0)
    y: float = Field(0.0, ge=0.0, le=1.0)
    width: float = Field(0.0, ge=0.0, le=1.0)
    height: float = Field(0.0, ge=0.0, le=1.0)
    points: Optional[List[List[float]]] = None
    allowed_classes: List[str] = Field(default_factory=list)
    active: bool = True

class CameraProbeRequest(BaseModel):
    ip: str
    username: str = "admin"
    password: str
    subtype: str = "1"

class CameraCreateRequest(BaseModel):
    name: str = "Camera"
    ip: str
    username: str = "admin"
    password: str
    subtype: str = "1"
    auto_detect: bool = True
    port: Optional[int] = None
    protocol: Optional[str] = None
    stream_path: Optional[str] = None

class CameraUpdateRequest(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    subtype: Optional[str] = None
    enabled: Optional[bool] = None
    re_detect: bool = False

class ManualSnapshotRequest(BaseModel):
    note: Optional[str] = "Manual snapshot"
    camera_id: Optional[str] = None
