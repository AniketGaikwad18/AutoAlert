"""Stage 4 Object Detection Tests."""

import numpy as np
import pytest
from src.detection.detector import BoundingBox, Detection, BaseDetector, YOLOObjectDetector
from src.detection.vehicle_detector import VehicleDetector
from src.detection.person_detector import PersonDetector


class MockDetector(BaseDetector):
    """Deterministic mock detector for unit testing without relying on weight downloads."""
    def __init__(self, mock_detections):
        self.mock_detections = mock_detections

    def detect(self, frame, frame_number=None, timestamp_sec=None):
        return self.mock_detections


def test_bounding_box_geometry():
    """Test geometry properties, center point and area computation."""
    box = BoundingBox(x1=10, y1=20, x2=50, y2=80)
    assert box.width == 40
    assert box.height == 60
    assert box.area == 2400
    assert box.center_x == 30
    assert box.center_y == 50
    assert box.to_xyxy() == (10, 20, 50, 80)


def test_bounding_box_iou():
    """Test Intersection over Union (IoU) calculation."""
    box1 = BoundingBox(0, 0, 10, 10) # Area = 100
    box2 = BoundingBox(5, 0, 15, 10) # Area = 100, Intersection = 5x10 = 50, Union = 150
    assert pytest.approx(box1.iou(box2), 0.01) == 50.0 / 150.0

    box3 = BoundingBox(20, 20, 30, 30) # No overlap
    assert box1.iou(box3) == 0.0


def test_detection_serialization():
    """Test structured Detection object to_dict serialization."""
    bbox = BoundingBox(12.5, 34.2, 56.7, 78.9)
    det = Detection(
        class_name="car",
        confidence=0.885,
        bbox=bbox,
        frame_number=10,
        timestamp_sec=0.333
    )
    d = det.to_dict()
    assert d["class_name"] == "car"
    assert d["confidence"] == 0.885
    assert d["frame_number"] == 10
    assert d["bbox"]["x1"] == 12.5


def test_vehicle_and_person_filtering():
    """Test vehicle detector and person detector filter classes correctly."""
    detections = [
        Detection("car", 0.9, BoundingBox(0, 0, 10, 10)),
        Detection("person", 0.85, BoundingBox(10, 10, 20, 20)),
        Detection("truck", 0.78, BoundingBox(30, 30, 50, 50)),
        Detection("dog", 0.65, BoundingBox(5, 5, 15, 15)), # Non-target class
    ]
    mock = MockDetector(detections)

    v_detector = VehicleDetector(base_detector=mock)
    v_results = v_detector.detect_vehicles(np.zeros((100, 100, 3), dtype=np.uint8))
    assert len(v_results) == 2
    assert {d.class_name for d in v_results} == {"car", "truck"}

    p_detector = PersonDetector(base_detector=mock)
    p_results = p_detector.detect_persons(np.zeros((100, 100, 3), dtype=np.uint8))
    assert len(p_results) == 1
    assert p_results[0].class_name == "person"


def test_yolo_detector_instantiation_resilience():
    """Test that YOLO detector handles non-existent paths gracefully."""
    detector = YOLOObjectDetector(model_path="models/detection/non_existent.pt")
    # Should attempt fallback or report ready status cleanly without unhandled crash
    assert isinstance(detector.is_ready, bool)
