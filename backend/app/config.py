import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend folder
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    BASE_DIR: Path = BASE_DIR
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Camera settings from .env
    CAMERA_IP: str = os.getenv("CAMERA_IP", "192.168.0.100")
    CAMERA_PORT: int = int(os.getenv("CAMERA_PORT", "554"))
    CAMERA_USER: str = os.getenv("CAMERA_USER", "admin")
    CAMERA_PASSWORD: str = os.getenv("CAMERA_PASSWORD", "Admin123!")

    # Default full RTSP source
    DEFAULT_RTSP: str = f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:{CAMERA_PORT}/cam/realmonitor?channel=1&subtype=1"
    CAMERA_SOURCE: str = os.getenv("CAMERA_SOURCE", DEFAULT_RTSP)

    FALLBACK_SOURCE: str = os.getenv("FALLBACK_SOURCE", "demo")
    STORAGE_DIR: Path = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
    SNAPSHOTS_DIR: Path = STORAGE_DIR / "snapshots"
    DETECTION_CONFIDENCE: float = float(os.getenv("DETECTION_CONFIDENCE", "0.45"))
    AUTO_SNAPSHOT_COOLDOWN: float = float(os.getenv("AUTO_SNAPSHOT_COOLDOWN", "5.0"))

settings = Settings()
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
