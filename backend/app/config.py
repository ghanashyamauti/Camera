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
    CAMERA_SOURCE: str = os.getenv(
        "CAMERA_SOURCE",
        "rtsp://admin:admin123@192.168.1.250:554/cam/realmonitor?channel=1&subtype=1"
    )
    FALLBACK_SOURCE: str = os.getenv("FALLBACK_SOURCE", "demo")
    STORAGE_DIR: Path = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
    SNAPSHOTS_DIR: Path = STORAGE_DIR / "snapshots"
    DETECTION_CONFIDENCE: float = float(os.getenv("DETECTION_CONFIDENCE", "0.45"))
    AUTO_SNAPSHOT_COOLDOWN: float = float(os.getenv("AUTO_SNAPSHOT_COOLDOWN", "5.0"))

settings = Settings()
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
