from typing import List, Dict, Optional, Any
from pydantic import BaseModel, ConfigDict
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload


class IncidentStatusUpdate(BaseModel):
    """Schema for updating incident simulated notification status."""
    notification_status: str  # pending, notified, acknowledged, responding


class IncidentResponse(BaseModel):
    """API response schema for an incident."""
    id: str
    incident_id: Optional[str] = None
    incident_type: str
    camera_id: str
    timestamp: str
    confidence_score: float
    verification_status: str
    notification_status: str
    involved_tracks: List[int]
    reasons: List[str]
    signals: Dict[str, Any]
    location: Optional[Dict[str, Any]]
    evidence: Optional[Dict[str, Any]]
    plate_readings: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True, extra="allow")

    def __init__(self, **data):
        if "incident_id" not in data and "id" in data:
            data["incident_id"] = data["id"]
        elif "id" not in data and "incident_id" in data:
            data["id"] = data["incident_id"]
        super().__init__(**data)


class LocationSchema(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    name: Optional[str] = None
    zone_id: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class PlateReadingSchema(BaseModel):
    track_id: int
    plate_number: Optional[str] = None
    plate_text: Optional[str] = None
    confidence: float = 0.0
    format_validated: bool = False
    is_readable: bool = False
    status: str = "verified_reading"

    model_config = ConfigDict(extra="allow")

    def __init__(self, **data):
        if "plate_number" in data and "plate_text" not in data:
            data["plate_text"] = data["plate_number"]
        elif "plate_text" in data and "plate_number" not in data:
            data["plate_number"] = data["plate_text"]
        super().__init__(**data)


class IncidentPackageCreateSchema(BaseModel):
    incident_id: str
    incident_type: str
    camera_id: str
    timestamp: Any
    verification_status: str = "verified"
    confidence_score: float = 1.0
    created_at: Optional[str] = None
    involved_track_ids: List[int] = []
    evidence_frames: List[str] = []
    evidence_video_path: Optional[str] = None
    location: Optional[LocationSchema] = None
    plate_readings: List[PlateReadingSchema] = []
    reason_metadata: Dict[str, Any] = {}
    reasons: List[str] = []
    signals: Dict[str, Any] = {}

    model_config = ConfigDict(extra="allow")


class IncidentPackageResponseSchema(BaseModel):
    incident_id: str
    id: Optional[str] = None
    incident_type: str
    camera_id: str
    timestamp: Any
    verification_status: str = "verified"
    confidence_score: float = 1.0
    created_at: Optional[str] = None
    involved_track_ids: List[int] = []
    evidence_frames: List[str] = []
    evidence_video_path: Optional[str] = None
    location: Optional[LocationSchema] = None
    plate_readings: List[PlateReadingSchema] = []
    reason_metadata: Dict[str, Any] = {}
    reasons: List[str] = []
    signals: Dict[str, Any] = {}
    notification_status: str = "pending"
    source_device: str = "Raspberry Pi AI Box"
    mode: str = "DEMO"
    ambulance_status: str = "Awaiting Dispatch"
    police_status: str = "Notification Pending"

    model_config = ConfigDict(from_attributes=True, extra="allow")

    def __init__(self, **data):
        if "incident_id" not in data and "id" in data:
            data["incident_id"] = data["id"]
        elif "id" not in data and "incident_id" in data:
            data["id"] = data["incident_id"]
        super().__init__(**data)

