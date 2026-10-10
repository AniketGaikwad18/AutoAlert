"""Stage 7 Prolonged Person Motionlessness Tests."""

import pytest
from src.detection.detector import BoundingBox
from src.tracking.tracker import Track, TrajectoryPoint
from src.events.motionless import MotionlessPersonDetector, MotionlessCandidate


def make_person_track(track_id: int, center_x: float, center_y: float) -> Track:
    """Helper to create a confirmed person track at a specified center position."""
    t = Track(
        track_id=track_id,
        class_name="person",
        confidence=0.88,
        bbox=BoundingBox(center_x - 15, center_y - 40, center_x + 15, center_y + 40),
        hits=5,
        is_confirmed=True
    )
    t.history.append(
        TrajectoryPoint(
            frame_number=1,
            timestamp_sec=0.0,
            center_x=center_x,
            center_y=center_y,
            bbox=t.bbox
        )
    )
    return t


def test_positive_motionless_candidate():
    """Test person remaining within 5px displacement over 4 seconds triggers candidate."""
    detector = MotionlessPersonDetector(
        movement_threshold_px=10.0,
        duration_seconds=3.0,
        min_frames=5
    )

    cands = []
    # Simulate stationary person over 10 frames from t=0.0 to t=4.0
    for i in range(10):
        t = i * 0.45  # total time reaching ~4.05s
        track = make_person_track(1, 100.0 + (i * 0.2), 200.0)  # max displacement < 2px
        step_cands = detector.evaluate([track], frame_number=i + 1, timestamp_sec=t)
        if step_cands:
            cands.extend(step_cands)

    assert len(cands) == 1
    c = cands[0]
    assert isinstance(c, MotionlessCandidate)
    assert c.track_id == 1
    assert c.status == "candidate"
    assert c.motionless_duration_sec >= 3.0
    assert "injured" not in c.reasons[0].lower()


def test_negative_active_walking_person():
    """Negative case: Person walking continuously does not trigger candidate."""
    detector = MotionlessPersonDetector(
        movement_threshold_px=10.0,
        duration_seconds=3.0,
        min_frames=5
    )

    cands = []
    for i in range(10):
        t = i * 0.45
        # Moving 15px per step (displacement grows continuously)
        track = make_person_track(1, 100.0 + (i * 15.0), 200.0)
        step_cands = detector.evaluate([track], frame_number=i + 1, timestamp_sec=t)
        if step_cands:
            cands.extend(step_cands)

    assert len(cands) == 0


def test_motion_resumption_resets_anchor():
    """Test person stationary for 2s, then moving, resets motionless timer."""
    detector = MotionlessPersonDetector(
        movement_threshold_px=10.0,
        duration_seconds=3.0,
        min_frames=5
    )

    # Stationary for 2 seconds (below 3s threshold)
    for i in range(5):
        t = i * 0.4
        track = make_person_track(1, 100.0, 200.0)
        cands = detector.evaluate([track], frame_number=i + 1, timestamp_sec=t)
        assert len(cands) == 0

    # Large movement at frame 6 (displacement 60px)
    track_moved = make_person_track(1, 160.0, 200.0)
    cands = detector.evaluate([track_moved], frame_number=6, timestamp_sec=2.4)
    assert len(cands) == 0
    # State anchor should now be at x=160
    assert detector._motion_state[1]["anchor_x"] == 160.0


def test_disappeared_track_cleaned_up():
    """Test track state is evicted when track disappears."""
    detector = MotionlessPersonDetector()
    track = make_person_track(99, 50.0, 50.0)
    detector.evaluate([track], frame_number=1, timestamp_sec=0.0)
    assert 99 in detector._motion_state

    # Next frame without track 99
    detector.evaluate([], frame_number=2, timestamp_sec=0.5)
    assert 99 not in detector._motion_state
