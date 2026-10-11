"""Event Verification Engine for AutoAlert.

Applies temporal consistency, confidence thresholds, and duplicate suppression
rules to candidate events before elevating to a verified incident.
Explicit rule: Candidate Event != Verified Incident.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from src.core.event import VerificationState, VerifiedIncidentTrigger, VerifiedIncident

logger = logging.getLogger("autoalert.events.verifier")


@dataclass
class VerifierConfig:
    """Configuration for event verification rules."""
    min_confidence_score: float = 0.65
    candidate_expiry_sec: float = 6.0
    duplicate_cooldown_sec: float = 20.0
    required_confirmations: int = 2
    min_consecutive_hits: int = 2


class EventVerifier:
    """State machine verifying event candidates into actionable incidents."""

    def __init__(
        self,
        min_confidence_threshold: Any = 0.65,
        candidate_expiry_sec: float = 6.0,
        duplicate_cooldown_sec: float = 20.0,
        min_consecutive_hits: int = 2,
        config: Optional[VerifierConfig] = None
    ):
        if isinstance(min_confidence_threshold, VerifierConfig):
            config = min_confidence_threshold
            min_confidence_threshold = 0.65

        if config is not None:
            self.min_confidence_threshold = getattr(config, "min_confidence_score", getattr(config, "min_confidence_threshold", 0.65))
            self.candidate_expiry_sec = getattr(config, "candidate_expiry_sec", candidate_expiry_sec)
            self.duplicate_cooldown_sec = getattr(config, "duplicate_cooldown_sec", duplicate_cooldown_sec)
            self.min_consecutive_hits = getattr(config, "required_confirmations", getattr(config, "min_consecutive_hits", min_consecutive_hits))
        else:
            self.min_confidence_threshold = min_confidence_threshold
            self.candidate_expiry_sec = candidate_expiry_sec
            self.duplicate_cooldown_sec = duplicate_cooldown_sec
            self.min_consecutive_hits = min_consecutive_hits

        # candidate_key -> session dict
        self._sessions: Dict[str, Dict[str, Any]] = {}
        # suppression_key -> last_verified_timestamp
        self._suppression_cache: Dict[str, float] = {}
        self._incident_counter = 0

    def _generate_suppression_key(self, camera_id: str, event_type: str, track_ids: List[int]) -> str:
        """Create deterministic key for suppressing ongoing repetitive reports."""
        sorted_tracks = ",".join(map(str, sorted(track_ids))) if track_ids else "scene"
        return f"{camera_id}:{event_type}:{sorted_tracks}"

    def process_candidate(
        self,
        candidate_or_id: Any = None,
        candidate_id: Optional[str] = None,
        event_type: Optional[str] = None,
        score: Optional[float] = None,
        camera_id: str = "CAM-01",
        timestamp_sec: float = 0.0,
        track_ids: Optional[List[int]] = None,
        signals: Optional[Dict[str, Any]] = None,
        reasons: Optional[List[str]] = None,
        **kwargs
    ) -> Any:
        """Process incoming candidate event and evaluate verification state."""
        cand_input = candidate_or_id if candidate_or_id is not None else candidate_id
        is_candidate_obj = cand_input is not None and not isinstance(cand_input, str)
        if is_candidate_obj:
            cand = cand_input
            candidate_id = getattr(cand, "candidate_id", "CAND-01")
            event_type = getattr(cand, "event_type", "vehicle_collision")
            score = float(getattr(cand, "candidate_score", getattr(cand, "confidence", 1.0)))
            timestamp_sec = float(kwargs.get("timestamp", getattr(cand, "timestamp_sec", getattr(cand, "timestamp", 0.0))))
            track_ids = list(getattr(cand, "track_ids", []))
            signals = getattr(cand, "signals", {})
            reasons = getattr(cand, "reasons", [])
        else:
            candidate_id = str(cand_input or "CAND-01")
            event_type = event_type or "unknown"
            score = float(score if score is not None else 1.0)
            if "timestamp" in kwargs:
                timestamp_sec = float(kwargs["timestamp"])
            track_ids = track_ids or []
            signals = signals or {}
            reasons = reasons or []

        supp_key = self._generate_suppression_key(camera_id, event_type, track_ids)

        # 1. Check duplicate suppression cooldown
        if supp_key in self._suppression_cache:
            last_verified = self._suppression_cache[supp_key]
            if (timestamp_sec - last_verified) < self.duplicate_cooldown_sec:
                logger.info(f"Candidate {candidate_id} suppressed as duplicate of recent incident.")
                return None if is_candidate_obj else (VerificationState.REJECTED, None)

        # 2. Check candidate quality threshold
        if score < self.min_confidence_threshold:
            logger.info(f"Candidate {candidate_id} rejected: score {score:.2f} < threshold {self.min_confidence_threshold}")
            return None if is_candidate_obj else (VerificationState.REJECTED, None)

        # 3. Temporal verification session
        session_key = supp_key if track_ids else f"{camera_id}:{event_type}:{candidate_id}"
        if session_key not in self._sessions:
            self._sessions[session_key] = {
                "first_seen": timestamp_sec,
                "last_seen": timestamp_sec,
                "hits": 1,
                "scores": [score],
                "track_ids": track_ids,
                "camera_id": camera_id,
                "event_type": event_type,
                "candidate_id": candidate_id,
                "signals": signals,
                "reasons": reasons,
            }
        else:
            session = self._sessions[session_key]
            session["last_seen"] = timestamp_sec
            session["hits"] += 1
            session["scores"].append(score)

        session = self._sessions[session_key]

        # 4. Check if session meets verification rules
        if session["hits"] >= self.min_consecutive_hits:
            avg_score = float(sum(session["scores"]) / len(session["scores"]))
            self._incident_counter += 1
            inc_id = f"INC-{self._incident_counter:04d}"

            trigger = VerifiedIncidentTrigger(
                incident_id=inc_id,
                candidate_id=candidate_id,
                event_type=event_type,
                camera_id=camera_id,
                timestamp_sec=timestamp_sec,
                confidence_score=avg_score,
                track_ids=track_ids,
                verification_state=VerificationState.VERIFIED,
                decision_reasons=[
                    f"Passed confidence threshold {avg_score:.2f} >= {self.min_confidence_threshold}",
                    f"Sustained verification across {session['hits']} temporal samples",
                ] + reasons,
                signals=signals,
            )

            # Record cooldown to suppress immediate duplicates
            self._suppression_cache[supp_key] = timestamp_sec
            del self._sessions[session_key]
            logger.info(f"Incident verified: [{inc_id}] {event_type} on camera {camera_id}")
            if is_candidate_obj:
                return VerifiedIncident(
                    incident_id=inc_id,
                    incident_type=event_type,
                    verification_state=VerificationState.VERIFIED,
                    confidence_score=avg_score,
                    initial_candidate_id=candidate_id,
                    first_detected_frame=kwargs.get("frame_index", 0),
                    verified_frame=kwargs.get("frame_index", 0),
                    timestamp=timestamp_sec,
                    track_ids=track_ids,
                    signals_summary=signals
                )
            return VerificationState.VERIFIED, trigger

        return None if is_candidate_obj else (VerificationState.VERIFYING, None)

    def prune_expired_sessions(self, current_timestamp_sec: float) -> List[str]:
        """Prune active candidate sessions that timed out without sufficient corroboration."""
        expired_keys = []
        for key, s in list(self._sessions.items()):
            if (current_timestamp_sec - s["last_seen"]) > self.candidate_expiry_sec:
                expired_keys.append(s["candidate_id"])
                del self._sessions[key]
        return expired_keys
