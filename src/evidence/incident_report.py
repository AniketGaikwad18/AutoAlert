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


def build_incident_package(
    report: Any = None,
    verified_incident: Any = None,
    evidence_files: Any = None,
    camera_id: Optional[str] = None,
    location: Any = None,
    plate_readings: Optional[List[Any]] = None,
    **kwargs
) -> Any:
    """Construct IncidentPackage from IncidentReport, IncidentEvidenceReport, or verified incident components."""
    from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload
    from src.license_plate.aggregator import AggregatedPlateResult

    inc_obj = verified_incident or report

    inc_id = getattr(inc_obj, "incident_id", kwargs.get("incident_id", "INC-001"))
    raw_type = getattr(inc_obj, "event_type", getattr(inc_obj, "incident_type", kwargs.get("incident_type", "collision")))
    inc_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
    cam_id = camera_id or getattr(inc_obj, "camera_id", kwargs.get("camera_id", "CAM-01"))
    timestamp = str(getattr(inc_obj, "timestamp", getattr(inc_obj, "timestamp_sec", kwargs.get("timestamp", ""))))
    confidence = float(getattr(inc_obj, "confidence_score", kwargs.get("confidence_score", 1.0)))
    raw_vstatus = getattr(inc_obj, "verification_state", getattr(inc_obj, "verification_status", "verified"))
    v_status = raw_vstatus.value if hasattr(raw_vstatus, "value") else str(raw_vstatus)
    track_ids = getattr(inc_obj, "track_ids", getattr(inc_obj, "involved_track_ids", []))
    signals = getattr(inc_obj, "signals_summary", getattr(inc_obj, "signals", {}))

    reasons = getattr(inc_obj, "reasons", [])
    if not reasons and hasattr(inc_obj, "verification_reason"):
        reasons = [getattr(inc_obj, "verification_reason")]

    loc = location if location is not None else getattr(report, "location", None)
    loc_model = LocationModel(**loc) if isinstance(loc, dict) else loc

    ev_files = evidence_files if evidence_files is not None else getattr(report, "evidence_files", getattr(report, "evidence_manifest", {}))
    ev_payload = EvidencePayload(
        directory=inc_id,
        key_frames=ev_files.get("key_frames", []) if isinstance(ev_files, dict) else [],
        video_clip=ev_files.get("video_clip") if isinstance(ev_files, dict) else None
    )

    parsed_plates: List[PlateReadingPayload] = []
    raw_plates = plate_readings if plate_readings is not None else getattr(report, "plate_readings", [])
    for p in raw_plates or []:
        if isinstance(p, PlateReadingPayload):
            parsed_plates.append(p)
        elif isinstance(p, AggregatedPlateResult):
            parsed_plates.append(
                PlateReadingPayload(
                    track_id=p.track_id,
                    plate_text=p.best_plate_number,
                    plate_number=p.best_plate_number,
                    confidence=p.aggregated_confidence,
                    is_readable=p.is_readable,
                    format_valid=p.format_validated,
                    status=p.status,
                )
            )
        elif isinstance(p, dict):
            parsed_plates.append(PlateReadingPayload(**p))

    return IncidentPackage(
        incident_id=inc_id,
        incident_type=inc_type,
        camera_id=cam_id,
        timestamp=timestamp,
        confidence_score=confidence,
        verification_status=v_status,
        involved_track_ids=track_ids,
        signals=signals,
        location=loc_model,
        evidence=ev_payload,
        plate_readings=parsed_plates,
        reasons=reasons,
    )

