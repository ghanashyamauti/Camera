import datetime
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class CameraRecord(Base):
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    ip = Column(String(64), nullable=False)
    port = Column(Integer, default=554, nullable=False)
    username = Column(String(120), nullable=False, default="admin")
    password_enc = Column(Text, nullable=False)
    protocol = Column(String(16), default="rtsps", nullable=False)  # rtsps or rtsp
    subtype = Column(String(32), default="1", nullable=False)
    stream_path = Column(Text, nullable=True)  # e.g. /video/live?channel=1&subtype=1&unicast=true&proto=Onvif&tls=true
    manufacturer = Column(String(120), nullable=True)
    model = Column(String(120), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    zones = relationship("ZoneRecord", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("EventRecord", back_populates="camera", cascade="all, delete-orphan")


class ZoneRecord(Base):
    __tablename__ = "zones"

    id = Column(String(64), primary_key=True, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, default="Zone 1")
    shape = Column(String(24), nullable=False, default="rect")  # rect or polygon
    x = Column(Float, default=0.0, nullable=False)
    y = Column(Float, default=0.0, nullable=False)
    width = Column(Float, default=0.0, nullable=False)
    height = Column(Float, default=0.0, nullable=False)
    points = Column(JSON, nullable=True)  # [[x, y], ...]
    allowed_classes = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    camera = relationship("CameraRecord", back_populates="zones")


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True, index=True)
    zone_id = Column(String(128), nullable=False)
    zone_name = Column(String(160), nullable=False)
    status = Column(String(32), nullable=False)  # occupied / empty
    detected_objects = Column(JSON, nullable=False, default=list)
    snapshot = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    camera = relationship("CameraRecord", back_populates="events")


def init_db():
    Base.metadata.create_all(bind=engine)
