import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    BASE_DIR: Path = BASE_DIR
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:root@127.0.0.1:5432/camera_monitor"
    )
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "")

    STORAGE_DIR: Path = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
    SNAPSHOTS_DIR: Path = STORAGE_DIR / "snapshots"
    DETECTION_CONFIDENCE: float = float(os.getenv("DETECTION_CONFIDENCE", "0.45"))
    AUTO_SNAPSHOT_COOLDOWN: float = float(os.getenv("AUTO_SNAPSHOT_COOLDOWN", "5.0"))
    AI_DETECTION_INTERVAL: float = float(os.getenv("AI_DETECTION_INTERVAL", "0.25"))

settings = Settings()
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
