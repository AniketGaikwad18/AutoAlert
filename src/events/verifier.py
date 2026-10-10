"""Event Verification Engine for AutoAlert.

Applies temporal consistency, confidence thresholds, and duplicate suppression
rules to candidate events before elevating to a verified incident.
Explicit rule: Candidate Event != Verified Incident.
"""

from typing import Dict, List, Optional, Tuple, Any
import logging
from src.core.event import VerificationState, VerifiedIncidentTrigger

logger = logging.getLogger("autoalert.events.verifier")


class EventVerifier:
    """State machine verifying event candidates into actionable incidents."""

    def __init__(
        self,
        min_confidence_threshold: float = 0.65,
        candidate_expiry_sec: float = 6.0,
        duplicate_cooldown_sec: float = 20.0,
        min_consecutive_hits: int = 2
    ):
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
        candidate_id: str,
        event_type: str,
        score: float,
        camera_id: str,
        timestamp_sec: float,
        track_ids: Optional[List[int]] = None,
        signals: Optional[Dict[str, Any]] = None,
        reasons: Optional[List[str]] = None
    ) -> Tuple[VerificationState, Optional[VerifiedIncidentTrigger]]:
        """Process incoming candidate event and evaluate verification state."""
        track_ids = track_ids or []
        signals = signals or {}
        reasons = reasons or []

        supp_key = self._generate_suppression_key(camera_id, event_type, track_ids)

        # 1. Check duplicate suppression cooldown
        if supp_key in self._suppression_cache:
            last_verified = self._suppression_cache[supp_key]
            if (timestamp_sec - last_verified) < self.duplicate_cooldown_sec:
                logger.info(f"Candidate {candidate_id} suppressed as duplicate of recent incident.")
                return VerificationState.REJECTED, None

        # 2. Check candidate quality threshold
        if score < self.min_confidence_threshold:
            logger.info(f"Candidate {candidate_id} rejected: score {score:.2f} < threshold {self.min_confidence_threshold}")
            return VerificationState.REJECTED, None

        # 3. Temporal verification session
        session_key = f"{camera_id}:{event_type}:{candidate_id}"
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
            return VerificationState.VERIFIED, trigger

        return VerificationState.VERIFYING, None

    def prune_expired_sessions(self, current_timestamp_sec: float) -> List[str]:
        """Prune active candidate sessions that timed out without sufficient corroboration."""
        expired_keys = []
        for key, s in list(self._sessions.items()):
            if (current_timestamp_sec - s["last_seen"]) > self.candidate_expiry_sec:
                expired_keys.append(s["candidate_id"])
                del self._sessions[key]
        return expired_keys
