"""Core event contracts and verification states for AutoAlert."""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class VerificationState(str, Enum):
    """Explicit verification lifecycle states for incident management."""
    CANDIDATE = "candidate"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class VerifiedIncidentTrigger:
    """Trigger payload generated when an event successfully passes verification rules."""
    incident_id: str
    candidate_id: str
    event_type: str
    camera_id: str
    timestamp_sec: float
    confidence_score: float
    track_ids: List[int]
    verification_state: VerificationState
    decision_reasons: List[str]
    signals: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "candidate_id": self.candidate_id,
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "confidence_score": round(self.confidence_score, 3),
            "track_ids": self.track_ids,
            "verification_state": self.verification_state.value,
            "decision_reasons": self.decision_reasons,
            "signals": self.signals,
            "metadata": self.metadata,
        }
