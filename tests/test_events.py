"""Stage 9 Event Verification Engine Tests."""

import pytest
from src.core.event import VerificationState, VerifiedIncidentTrigger
from src.events.verifier import EventVerifier


def test_verification_lifecycle_success():
    """Test candidate moving from verifying to verified upon reaching consecutive hits."""
    verifier = EventVerifier(
        min_confidence_threshold=0.70,
        min_consecutive_hits=2
    )

    # Hit 1: Enters VERIFYING state
    state, trigger = verifier.process_candidate(
        candidate_id="CAND-01",
        event_type="vehicle_collision",
        score=0.85,
        camera_id="CAM-01",
        timestamp_sec=10.0,
        track_ids=[1, 2],
        reasons=["Sudden velocity drop"]
    )
    assert state == VerificationState.VERIFYING
    assert trigger is None

    # Hit 2: Reaches min_consecutive_hits=2 -> Elevated to VERIFIED
    state, trigger = verifier.process_candidate(
        candidate_id="CAND-01",
        event_type="vehicle_collision",
        score=0.87,
        camera_id="CAM-01",
        timestamp_sec=10.2,
        track_ids=[1, 2],
        reasons=["Sudden velocity drop"]
    )
    assert state == VerificationState.VERIFIED
    assert trigger is not None
    assert isinstance(trigger, VerifiedIncidentTrigger)
    assert trigger.incident_id.startswith("INC-")
    assert trigger.confidence_score == pytest.approx(0.86, 0.01)
    assert trigger.track_ids == [1, 2]
    assert len(trigger.decision_reasons) >= 2


def test_verification_low_confidence_rejection():
    """Test candidate below minimum confidence threshold is rejected immediately."""
    verifier = EventVerifier(min_confidence_threshold=0.75)
    state, trigger = verifier.process_candidate(
        candidate_id="CAND-LOW",
        event_type="vehicle_collision",
        score=0.45,
        camera_id="CAM-01",
        timestamp_sec=1.0,
        track_ids=[3, 4]
    )
    assert state == VerificationState.REJECTED
    assert trigger is None


def test_duplicate_suppression_cooldown():
    """Test that immediate duplicate candidates for the same event are suppressed."""
    verifier = EventVerifier(
        min_consecutive_hits=1,
        duplicate_cooldown_sec=15.0
    )

    # First event verified
    state1, trigger1 = verifier.process_candidate(
        candidate_id="CAND-A",
        event_type="vehicle_collision",
        score=0.90,
        camera_id="CAM-01",
        timestamp_sec=100.0,
        track_ids=[5, 6]
    )
    assert state1 == VerificationState.VERIFIED
    assert trigger1 is not None

    # Second event on same camera, same event type, same tracks within cooldown window (t=105s)
    state2, trigger2 = verifier.process_candidate(
        candidate_id="CAND-B",
        event_type="vehicle_collision",
        score=0.92,
        camera_id="CAM-01",
        timestamp_sec=105.0,
        track_ids=[5, 6]
    )
    assert state2 == VerificationState.REJECTED
    assert trigger2 is None


def test_candidate_session_expiry():
    """Test stale incomplete candidate sessions expire after timeout."""
    verifier = EventVerifier(
        min_consecutive_hits=3,
        candidate_expiry_sec=5.0
    )

    # Hit 1 at t=0.0
    verifier.process_candidate(
        candidate_id="CAND-STALE",
        event_type="prolonged_motionlessness",
        score=0.80,
        camera_id="CAM-02",
        timestamp_sec=0.0
    )

    # Check expiry at t=6.0 (exceeds 5.0s window)
    expired = verifier.prune_expired_sessions(current_timestamp_sec=6.0)
    assert "CAND-STALE" in expired
    assert len(verifier._sessions) == 0
