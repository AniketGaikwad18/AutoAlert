"""Stage 6 Vehicle Collision Candidate Detection Tests."""

import pytest
from src.detection.detector import BoundingBox, Detection
from src.tracking.tracker import Track, TrajectoryPoint
from src.events.collision import CollisionCandidateDetector, CollisionCandidate


def create_simulated_track(
    track_id: int,
    class_name: str,
    points: list
) -> Track:
    """Helper to create a Track with populated TrajectoryPoints."""
    track = Track(
        track_id=track_id,
        class_name=class_name,
        confidence=0.9,
        bbox=BoundingBox(points[-1][0]-20, points[-1][1]-20, points[-1][0]+20, points[-1][1]+20),
        hits=len(points),
        is_confirmed=True
    )
    for idx, (x, y, spd) in enumerate(points):
        track.history.append(
            TrajectoryPoint(
                frame_number=idx + 1,
                timestamp_sec=idx * 0.033,
                center_x=float(x),
                center_y=float(y),
                bbox=BoundingBox(x - 20, y - 20, x + 20, y + 20),
                speed=float(spd)
            )
        )
    return track


def test_positive_collision_candidate():
    """Test rapid convergence followed by abrupt deceleration and deflection generates candidate."""
    detector = CollisionCandidateDetector(
        proximity_threshold_px=70.0,
        sudden_deceleration_ratio=0.5,
        min_candidate_score=0.60
    )

    # Track 1: Car moving east at 300 px/s then suddenly stops at (150, 100)
    t1 = create_simulated_track(1, "car", [
        (50, 100, 300.0),
        (100, 100, 300.0),
        (145, 100, 20.0),  # Sudden deceleration & halt near (150, 100)
    ])

    # Track 2: Car moving west from (250, 100) towards (155, 100) and deflects
    t2 = create_simulated_track(2, "car", [
        (250, 100, 300.0),
        (200, 100, 300.0),
        (155, 125, 40.0),  # Sudden halt and 45 degree deflection
    ])

    # Feed frames to build persistence
    cands = []
    for f in range(1, 4):
        cands = detector.evaluate([t1, t2], frame_number=f, timestamp_sec=f * 0.033)

    assert len(cands) == 1
    c = cands[0]
    assert isinstance(c, CollisionCandidate)
    assert c.status == "candidate"
    assert c.track_ids == (1, 2)
    assert c.candidate_score >= 0.60
    assert "distance_px" in c.signals
    assert len(c.reasons) > 0


def test_negative_case_vehicles_passing_each_other():
    """Negative case: Two vehicles pass each other in opposite lanes at constant speed."""
    detector = CollisionCandidateDetector(min_candidate_score=0.65)

    # Vehicles pass parallel at y=100 and y=140 with constant speed (no decel, no deflection)
    t1 = create_simulated_track(1, "car", [
        (100, 100, 250.0),
        (150, 100, 250.0),
        (200, 100, 250.0),
    ])
    t2 = create_simulated_track(2, "car", [
        (200, 140, 250.0),
        (150, 140, 250.0),
        (100, 140, 250.0),
    ])

    cands = detector.evaluate([t1, t2], frame_number=3, timestamp_sec=0.1)
    # Even if they pass near each other, lack of deceleration and deflection keeps score below threshold
    assert len(cands) == 0


def test_negative_case_gentle_stop_at_traffic_light():
    """Negative case: Vehicles stopping normally behind each other with low decel ratio and no deflection."""
    detector = CollisionCandidateDetector(
        proximity_threshold_px=50.0,
        sudden_deceleration_ratio=0.6,
        min_candidate_score=0.65
    )

    t1 = create_simulated_track(1, "car", [
        (100, 100, 20.0),
        (105, 100, 16.0),
        (110, 100, 13.0),  # Slow creeping deceleration (<0.6 ratio)
    ])
    t2 = create_simulated_track(2, "car", [
        (160, 100, 30.0),
        (155, 100, 24.0),
        (150, 100, 19.0),  # Smooth gentle deceleration behind t1 (<0.6 ratio)
    ])

    cands = detector.evaluate([t1, t2], frame_number=3, timestamp_sec=0.1)
    assert len(cands) == 0
