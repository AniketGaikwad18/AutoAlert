"""Stage 8 Visual Anomaly Detection Tests."""

import numpy as np
import cv2
import pytest
from src.events.anomaly import VisualAnomalyDetector, VisualAnomalyCandidate, LIMITATION_STATEMENT


def create_red_patch_frame(width=300, height=300, patch_size=40) -> np.ndarray:
    """Create a BGR frame with a distinct red patch in the center."""
    frame = np.ones((height, width, 3), dtype=np.uint8) * 128  # Gray background
    x1, y1 = 100, 100
    cv2.circle(frame, (x1, y1), patch_size // 2, (0, 0, 220), -1)  # Pure red in BGR
    return frame


def test_positive_persistent_red_anomaly():
    """Test sustained red contour over multiple frames produces a VisualAnomalyCandidate."""
    detector = VisualAnomalyDetector(
        min_area_px=100.0,
        persistence_threshold_frames=3
    )

    frame = create_red_patch_frame(patch_size=40)  # Area ~ pi * 20^2 ~ 1250px
    cands = []
    for f in range(1, 5):
        step_cands = detector.evaluate(frame, frame_number=f, timestamp_sec=f * 0.033)
        if step_cands:
            cands.extend(step_cands)

    assert len(cands) >= 1
    c = cands[0]
    assert isinstance(c, VisualAnomalyCandidate)
    assert c.status == "candidate"
    assert "blood" not in c.description.lower()
    assert "red/liquid-like" in c.description.lower()
    assert c.contour_area_px >= 100.0
    assert c.limitations == LIMITATION_STATEMENT


def test_negative_no_red_content():
    """Negative case: Frame containing neutral gray and blue objects emits zero candidates."""
    detector = VisualAnomalyDetector(persistence_threshold_frames=2)
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.circle(frame, (100, 100), 30, (220, 0, 0), -1)  # Pure BLUE in BGR

    cands = detector.evaluate(frame, frame_number=1, timestamp_sec=0.0)
    assert len(cands) == 0


def test_negative_tiny_noise_speckle():
    """Negative case: Tiny speckle (below min_area_px) is filtered out."""
    detector = VisualAnomalyDetector(min_area_px=300.0, persistence_threshold_frames=2)
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(frame, (50, 50), (53, 53), (0, 0, 255), -1)  # Area = 9px

    for f in range(1, 4):
        cands = detector.evaluate(frame, frame_number=f, timestamp_sec=f * 0.033)
        assert len(cands) == 0


def test_negative_single_frame_fleeting_flash():
    """Negative case: Red appears for only 1 frame then disappears (no persistence)."""
    detector = VisualAnomalyDetector(persistence_threshold_frames=3)
    red_frame = create_red_patch_frame()
    black_frame = np.zeros((300, 300, 3), dtype=np.uint8)

    # Frame 1: Red flash
    cands1 = detector.evaluate(red_frame, frame_number=1, timestamp_sec=0.0)
    assert len(cands1) == 0

    # Frame 2 & 3: Gone
    cands2 = detector.evaluate(black_frame, frame_number=2, timestamp_sec=0.033)
    cands3 = detector.evaluate(black_frame, frame_number=3, timestamp_sec=0.066)
    assert len(cands2) == 0
    assert len(cands3) == 0
