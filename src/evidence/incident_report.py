"""Incident report formatting and packaging module for AutoAlert."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import json


@dataclass
class IncidentReport:
    """Consolidated incident report data container."""
    incident_id: str
    event_type: str
    camera_id: str
    timestamp_sec: float
    confidence_score: float
    verification_status: str
    reasons: List[str]
    evidence_manifest: Dict[str, Any]
    plate_readings: Optional[List[Dict[str, Any]]] = None
    location: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "confidence_score": round(self.confidence_score, 3),
            "verification_status": self.verification_status,
            "reasons": self.reasons,
            "evidence": self.evidence_manifest,
            "plate_readings": self.plate_readings or [],
            "location": self.location,
        }

    def save_json(self, output_file: str) -> None:
        """Write formatted incident report to JSON file."""
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
