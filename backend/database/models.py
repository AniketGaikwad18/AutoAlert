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
    notification_status = Column(String, default="pending")  # pending/draft, prepared, sent, delivered, acknowledged, response_initiated
    involved_tracks_json = Column(Text, default="[]")
    reasons_json = Column(Text, default="[]")
    signals_json = Column(Text, default="{}")
    location_json = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=True)
    plate_readings_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Coordinated Emergency Response & Device Fields
    source_device = Column(String, default="Raspberry Pi AI Box")
    mode = Column(String, default="DEMO")  # LIVE or DEMO
    ambulance_status = Column(String, default="Awaiting Dispatch")  # Awaiting Dispatch, Dispatch Initiated, Acknowledged, En Route, Arrived
    ambulance_unit = Column(String, default="108 Fast Response Unit #4")
    ambulance_dispatched_at = Column(String, nullable=True)
    ambulance_eta = Column(String, default="~4 mins")
    police_station_name = Column(String, default="Shivajinagar Central Police Headquarters")
    police_status = Column(String, default="Notification Pending")  # Notification Pending, Notification Sent, Delivered, Acknowledged
    police_notified_at = Column(String, nullable=True)
    timeline_events_json = Column(Text, default="[]")
    notification_message = Column(Text, nullable=True)
    notification_history_json = Column(Text, default="[]")


class DeviceModel(Base):
    """Field-deployed IoT AI Box (Raspberry Pi)."""
    __tablename__ = "devices"

    device_id = Column(String, primary_key=True, index=True)
    device_name = Column(String, default="Raspberry Pi 5 AI Box")
    ip_address = Column(String, default="192.168.1.105")
    last_heartbeat = Column(DateTime, nullable=True)
    is_connected = Column(Boolean, default=False)
    telemetry_json = Column(Text, default="{}")


class CameraModel(Base):
    """Persisted CCTV camera node."""
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_desc = Column(String, default="")
    merchant_name = Column(String, default="Highway Junction Superstore")
    is_active = Column(Boolean, default=True)
    status = Column(String, default="active")



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
