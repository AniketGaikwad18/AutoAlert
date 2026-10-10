"""License plate image preprocessing module for AutoAlert.

Standardizes plate crops for downstream optical character recognition through
contrast enhancement, grayscale normalization, and adaptive thresholding.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from src.detection.detector import BoundingBox

logger = logging.getLogger("autoalert.license_plate.preprocessor")


def crop_vehicle_roi(frame: np.ndarray, bbox: BoundingBox) -> Optional[np.ndarray]:
    """Safely crop vehicle region of interest from video frame within image boundaries."""
    if frame is None or frame.size == 0:
        return None

    h, w = frame.shape[:2]
    x1 = max(0, min(int(bbox.x1), w - 1))
    y1 = max(0, min(int(bbox.y1), h - 1))
    x2 = max(x1 + 1, min(int(bbox.x2), w))
    y2 = max(y1 + 1, min(int(bbox.y2), h))

    crop = frame[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def preprocess_plate_image(
    plate_img: np.ndarray,
    target_height: int = 64,
    apply_clahe: bool = True,
    apply_threshold: bool = False
) -> np.ndarray:
    """Preprocess license plate crop for robust OCR extraction."""
    if plate_img is None or plate_img.size == 0:
        return plate_img

    # Convert to grayscale if 3-channel
    if len(plate_img.shape) == 3:
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_img.copy()

    # Proportional resize maintaining aspect ratio
    h, w = gray.shape[:2]
    if h > 0 and h != target_height:
        scale = target_height / float(h)
        new_w = max(16, int(w * scale))
        gray = cv2.resize(gray, (new_w, target_height), interpolation=cv2.INTER_CUBIC)

    # Contrast Limiting Adaptive Histogram Equalization
    if apply_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    # Optional binarization
    if apply_threshold:
        _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return gray


def compute_image_sharpness(img: np.ndarray) -> float:
    """Compute Laplacian variance as an indicator of frame blur/sharpness."""
    if img is None or img.size == 0:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
