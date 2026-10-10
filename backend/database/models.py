"""SQLAlchemy ORM models for AutoAlert persistence."""

from sqlalchemy import Column, String, Float, Boolean, Text, Integer, DateTime
from datetime import datetime
from backend.database.database import Base


class IncidentModel(Base):
    """Persisted incident entity."""
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True)
    incident_type = Column(String, index=True, nullable=False)
    camera_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    verification_status = Column(String, default="verified")
    notification_status = Column(String, default="pending")  # pending, notified, acknowledged, responding
    involved_tracks_json = Column(Text, default="[]")
    reasons_json = Column(Text, default="[]")
    signals_json = Column(Text, default="{}")
    location_json = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=True)
    plate_readings_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class CameraModel(Base):
    """Persisted CCTV camera node."""
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_desc = Column(String, default="")
    is_active = Column(Boolean, default=True)


class FacilityModel(Base):
    """Persisted simulated emergency response facility."""
    __tablename__ = "facilities"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, index=True, nullable=False)  # hospital, ambulance, police
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    phone = Column(String, default="")
    status = Column(String, default="active")
    extra_info_json = Column(Text, default="{}")
