from typing import List, Dict, Optional, Any
from pydantic import BaseModel, ConfigDict
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload


class IncidentStatusUpdate(BaseModel):
    """Schema for updating incident simulated notification status."""
    notification_status: str  # pending, notified, acknowledged, responding


class IncidentResponse(BaseModel):
    """API response schema for an incident."""
    id: str
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

    model_config = ConfigDict(from_attributes=True)
