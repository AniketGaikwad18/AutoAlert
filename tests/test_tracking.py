"""Stage 5 Object Tracking Tests."""

import pytest
from src.detection.detector import BoundingBox, Detection
from src.tracking.tracker import MultiObjectTracker, Track, TrajectoryPoint


def test_tracker_lifecycle_and_continuity():
    """Test track creation, ID persistence across moving frames, and trajectory history."""
    tracker = MultiObjectTracker(min_hits=2, max_age=5)

    # Frame 1: Car appears at (100, 100)
    det1 = Detection("car", 0.9, BoundingBox(100, 100, 150, 150))
    tracks = tracker.update([det1], frame_number=1, timestamp_sec=0.0)
    # min_hits is 2, so not yet confirmed
    assert len(tracks) == 0

    # Frame 2: Car moves slightly to (110, 100)
    det2 = Detection("car", 0.92, BoundingBox(110, 100, 160, 150))
    tracks = tracker.update([det2], frame_number=2, timestamp_sec=0.033)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1
    assert tracks[0].class_name == "car"
    assert len(tracks[0].history) == 2
    assert tracks[0].is_confirmed is True

    # Frame 3: Car continues to (120, 100)
    det3 = Detection("car", 0.88, BoundingBox(120, 100, 170, 150))
    tracks = tracker.update([det3], frame_number=3, timestamp_sec=0.066)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1
    assert len(tracks[0].history) == 3


def test_tracker_disappearing_tracks():
    """Test track deletion after exceeding max_age missed frames."""
    tracker = MultiObjectTracker(min_hits=1, max_age=2)

    # Frame 1: Person appears
    det = Detection("person", 0.85, BoundingBox(50, 50, 80, 120))
    tracks = tracker.update([det], frame_number=1, timestamp_sec=0.0)
    assert len(tracks) == 1
    tid = tracks[0].track_id

    # Frame 2: Person disappears
    tracks = tracker.update([], frame_number=2, timestamp_sec=0.033)
    # Track is still kept in memory until max_age, but not updated
    assert len(tracker.tracks) == 1
    assert tracker.tracks[0].time_since_update == 1

    # Frame 3: Still gone
    tracker.update([], frame_number=3, timestamp_sec=0.066)
    assert len(tracker.tracks) == 1
    assert tracker.tracks[0].time_since_update == 2

    # Frame 4: Exceeds max_age=2, pruned
    tracker.update([], frame_number=4, timestamp_sec=0.100)
    assert len(tracker.tracks) == 0


def test_tracker_multiple_distinct_objects():
    """Test simultaneous tracking of multiple independent objects."""
    tracker = MultiObjectTracker(min_hits=1)

    det_car = Detection("car", 0.9, BoundingBox(10, 10, 50, 50))
    det_person = Detection("person", 0.8, BoundingBox(200, 200, 230, 280))

    tracks = tracker.update([det_car, det_person], frame_number=1, timestamp_sec=0.0)
    assert len(tracks) == 2
    classes = {t.class_name for t in tracks}
    assert classes == {"car", "person"}
    assert tracks[0].track_id != tracks[1].track_id
