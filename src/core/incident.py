"""Incident object and serialized payload contract for AutoAlert.

Provides the standardized contract between edge vision analysis and
central FastAPI backend ingestion.
Explicitly adheres to AutoAlert Rules:
- Validates required fields.
- Does not fabricate GPS or OCR data (leaves null/empty when unmeasured).
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class LocationModel(BaseModel):
    """Geographic coordinate model for CCTV camera mounting location."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    name: Optional[str] = None
    zone_id: Optional[str] = None
    description: Optional[str] = None


LocationInfo = LocationModel



class EvidencePayload(BaseModel):
    """File paths for recorded incident evidence artifacts."""
    directory: str
    key_frames: List[str] = Field(default_factory=list)
    video_clip: Optional[str] = None


class PlateReadingPayload(BaseModel):
    """Plate reading details associated with vehicle tracks in an incident."""
    track_id: int
    plate_text: Optional[str] = None
    plate_number: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_readable: bool = False
    format_valid: bool = False
    format_validated: Optional[bool] = None
    status: Optional[str] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, **data):
        if "plate_number" in data and "plate_text" not in data:
            data["plate_text"] = data["plate_number"]
        if "format_validated" in data and "format_valid" not in data:
            data["format_valid"] = data["format_validated"]
        super().__init__(**data)


class IncidentPackage(BaseModel):
    """Standardized transmission payload emitted by edge box to central backend."""
    incident_id: str
    incident_type: str
    camera_id: str
    timestamp: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    verification_status: str = "verified"
    involved_track_ids: List[int] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)
    location: Optional[Any] = None
    evidence: Optional[Any] = None
    plate_readings: List[PlateReadingPayload] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> str:
        return str(v)

    @field_validator("incident_id", "camera_id", "incident_type")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or blank")
        return v.strip()

    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON-serializable dictionary."""
        return self.model_dump()

    def to_dict(self) -> Dict[str, Any]:
        """Alias for to_json_dict / model_dump."""
        return self.model_dump()

