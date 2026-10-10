"""Stage 11 License Plate Detection Tests."""

import numpy as np
import cv2
import pytest
from src.detection.detector import BoundingBox
from src.license_plate.preprocessor import crop_vehicle_roi, preprocess_plate_image, compute_image_sharpness
from src.license_plate.detector import LicensePlateDetector, PlateDetection


def create_synthetic_vehicle_with_plate(has_plate: bool = True) -> np.ndarray:
    """Create a synthetic vehicle crop image with or without a license plate rectangle."""
    # 200x300 dark car back
    car_img = np.ones((200, 300, 3), dtype=np.uint8) * 40

    if has_plate:
        # White plate with aspect ratio ~ 3.5 (120x35 px)
        # Position: x=90 to 210, y=140 to 175
        cv2.rectangle(car_img, (90, 140), (210, 175), (250, 250, 250), -1)
        # Black border
        cv2.rectangle(car_img, (90, 140), (210, 175), (10, 10, 10), 2)
        # Draw some mock text lines
        cv2.putText(car_img, "MH12AB1234", (98, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

    return car_img


def test_plate_detection_positive_detection():
    """Test locating plate rectangle on synthetic vehicle crop."""
    detector = LicensePlateDetector(model_path=None)
    vehicle_img = create_synthetic_vehicle_with_plate(has_plate=True)
    v_bbox = BoundingBox(100, 100, 400, 300)

    det = detector.detect_plate_in_vehicle_crop(
        vehicle_crop=vehicle_img,
        vehicle_bbox=v_bbox,
        track_id=42,
        frame_number=15,
        timestamp_sec=0.5
    )

    assert isinstance(det, PlateDetection)
    assert det.plate_found is True
    assert det.track_id == 42
    assert det.plate_crop is not None
    assert det.bbox is not None
    assert det.bbox.x1 > v_bbox.x1


def test_plate_detection_negative_not_found():
    """Test that vehicle without plate returns plate_found=False without inventing a box."""
    detector = LicensePlateDetector(model_path=None)
    vehicle_img = create_synthetic_vehicle_with_plate(has_plate=False)
    v_bbox = BoundingBox(100, 100, 400, 300)

    det = detector.detect_plate_in_vehicle_crop(
        vehicle_crop=vehicle_img,
        vehicle_bbox=v_bbox,
        track_id=10
    )

    assert det.plate_found is False
    assert det.plate_crop is None
    assert det.bbox is None
    assert det.confidence == 0.0


def test_plate_preprocessor_clahe_and_grayscale():
    """Test CLAHE and normalization utilities."""
    sample = np.ones((50, 150, 3), dtype=np.uint8) * 100
    processed = preprocess_plate_image(sample, target_height=64, apply_clahe=True)
    assert processed.shape[0] == 64
    assert len(processed.shape) == 2  # Grayscale output


def test_select_best_crop():
    """Test selection of clearest frame from buffer."""
    detector = LicensePlateDetector()
    frame_blurry = np.ones((200, 200, 3), dtype=np.uint8) * 128
    frame_sharp = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(frame_sharp, (20, 20), (180, 180), (255, 255, 255), 4)

    bbox = BoundingBox(0, 0, 200, 200)
    candidates = [
        (1, 0.0, frame_blurry, bbox),
        (2, 0.1, frame_sharp, bbox),
    ]

    best = detector.select_best_crop(candidates)
    assert best is not None
    assert best[0] == 2  # Frame 2 is significantly sharper
