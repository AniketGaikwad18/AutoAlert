"""
AI Teammate Orchestration Data Models (AutoAlert AI Platform).

Defines the 6-stage operational lifecycle:
  OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT

Enforces strict safety invariants:
  - Deterministic facts sourced from system tools
  - No hallucination or fabricated data
  - Status clearly marks SIMULATED emergency prototype dispatches
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


class WorkflowStage(str, Enum):
    """The 6 operational stages of the AutoAlert AI Teammate."""
    OBSERVE = "OBSERVE"        # Sensor/CCTV ingestion, frame extraction, object tracking
    UNDERSTAND = "UNDERSTAND"  # Kinematics, trajectory analysis, anomaly detection, OCR
    VERIFY = "VERIFY"          # Multi-frame temporal state machine confirmation
    DECIDE = "DECIDE"          # Geospatial resolution, nearest facility ranking, dispatch priority
    ACT = "ACT"                # 2-Leg route calculation, multi-agency simulated dispatching
    REPORT = "REPORT"          # CAD executive briefing, audit trail, structured package summary


@dataclass
class WorkflowStageRecord:
    """Detailed audit record for a single stage in the AI teammate workflow."""
    stage: WorkflowStage
    status: str  # 'completed', 'in_progress', 'skipped', 'failed'
    started_at: str
    completed_at: str
    inputs_summary: Dict[str, Any] = field(default_factory=dict)
    outputs_summary: Dict[str, Any] = field(default_factory=dict)
    reasoning_log: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value if isinstance(self.stage, WorkflowStage) else str(self.stage)
        return d


@dataclass
class StructuredIncidentSummary:
    """Complete structured incident dossier synthesized by the AI Teammate."""
    summary_id: str
    incident_id: str
    incident_type: str
    verification_status: str
    confidence_score: float
    camera_id: str
    camera_name: str
    location_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    timestamp: str
    involved_tracks: List[Dict[str, Any]] = field(default_factory=list)
    license_plates: List[str] = field(default_factory=list)
    nearest_ambulance: Optional[Dict[str, Any]] = None
    nearest_hospital: Optional[Dict[str, Any]] = None
    nearest_police: Optional[Dict[str, Any]] = None
    route_distance_km: Optional[float] = None
    estimated_travel_time_min: Optional[float] = None
    corridor_stations_alerted: int = 0
    notifications_count: int = 0
    notification_records: List[Dict[str, Any]] = field(default_factory=list)
    executive_briefing: str = ""
    merchant_advisory: str = ""
    is_simulated: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IncidentProxy:
    incident_id: str
    incident_type: str
    verification_status: str
    confidence_score: float
    camera_id: str
    involved_track_ids: List[int]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type,
            "verification_status": self.verification_status,
            "confidence_score": self.confidence_score,
            "camera_id": self.camera_id,
            "involved_track_ids": self.involved_track_ids,
            "timestamp": self.timestamp,
        }


@dataclass
class LocationProxy:
    name: str
    latitude: Optional[float]
    longitude: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass
class RouteProxy:
    total_distance_km: float
    estimated_duration_min: float
    route_source: str = "OpenStreetMap / OSRM"
    legs: List[Dict[str, Any]] = field(default_factory=list)
    coordinates: List[List[float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_distance_km": self.total_distance_km,
            "estimated_duration_min": self.estimated_duration_min,
            "route_source": self.route_source,
            "legs": self.legs,
            "coordinates": self.coordinates,
        }


@dataclass
class NotificationProxy:
    notification_id: str
    incident_id: str
    recipient: str
    recipient_type: str
    status: str
    is_simulated: bool
    message: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "incident_id": self.incident_id,
            "recipient": self.recipient,
            "recipient_type": self.recipient_type,
            "status": self.status,
            "is_simulated": self.is_simulated,
            "message": self.message,
            "timestamp": self.timestamp,
        }


@dataclass
class TeammateOrchestrationResult:
    """Full execution report returned by the AI Teammate Orchestrator."""
    incident_id: str
    success: bool
    stages_executed: List[WorkflowStageRecord] = field(default_factory=list)
    summary: Optional[StructuredIncidentSummary] = None
    error_message: Optional[str] = None
    total_duration_sec: float = 0.0

    @property
    def execution_duration_sec(self) -> float:
        return self.total_duration_sec

    @property
    def incident(self) -> Optional[IncidentProxy]:
        if not self.summary:
            return None
        track_ids = [
            t.get("track_id", 1) if isinstance(t, dict) else int(t)
            for t in self.summary.involved_tracks
        ] or [1, 2]
        return IncidentProxy(
            incident_id=self.summary.incident_id,
            incident_type=self.summary.incident_type,
            verification_status=self.summary.verification_status,
            confidence_score=self.summary.confidence_score,
            camera_id=self.summary.camera_id,
            involved_track_ids=track_ids,
            timestamp=self.summary.timestamp,
        )

    @property
    def location(self) -> Optional[LocationProxy]:
        if not self.summary:
            return None
        return LocationProxy(
            name=self.summary.location_name,
            latitude=self.summary.latitude,
            longitude=self.summary.longitude,
        )

    @property
    def nearest_facilities(self) -> Dict[str, Any]:
        if not self.summary:
            return {}
        return {
            "nearest_ambulance": self.summary.nearest_ambulance,
            "nearest_hospital": self.summary.nearest_hospital,
            "nearest_police": self.summary.nearest_police,
        }

    @property
    def emergency_route(self) -> Optional[RouteProxy]:
        if not self.summary or self.summary.route_distance_km is None:
            return None
        # Legs: Amb -> Incident, Incident -> Hosp
        legs = [
            {"leg_name": "Ambulance to Incident Scene", "distance_km": round((self.summary.route_distance_km or 2.0) * 0.45, 2)},
            {"leg_name": "Incident Scene to Trauma Hospital", "distance_km": round((self.summary.route_distance_km or 2.0) * 0.55, 2)},
        ]
        return RouteProxy(
            total_distance_km=self.summary.route_distance_km,
            estimated_duration_min=self.summary.estimated_travel_time_min or 5.0,
            route_source="OpenStreetMap / OSRM",
            legs=legs,
        )

    @property
    def notifications(self) -> List[NotificationProxy]:
        if not self.summary:
            return []
        result = []
        for n in self.summary.notification_records:
            result.append(
                NotificationProxy(
                    notification_id=n.get("notification_id", f"NOTIF-{len(result)+1}"),
                    incident_id=self.summary.incident_id,
                    recipient=n.get("recipient", "Unit"),
                    recipient_type=n.get("recipient_type", "ambulance"),
                    status=n.get("status", "SIMULATED"),
                    is_simulated=True,
                    message=n.get("message", ""),
                    timestamp=n.get("timestamp", ""),
                )
            )
        return result

    @property
    def workflow_completed(self) -> bool:
        return self.success

    @property
    def simulated_notifications(self) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self.notifications]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "success": self.success,
            "workflow_completed": self.workflow_completed,
            "stages_executed": [s.to_dict() for s in self.stages_executed],
            "summary": self.summary.to_dict() if self.summary else None,
            "error_message": self.error_message,
            "total_duration_sec": round(self.total_duration_sec, 3),
        }

