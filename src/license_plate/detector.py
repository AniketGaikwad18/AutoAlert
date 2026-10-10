"""License plate localization and detection module for AutoAlert.

Detects vehicle license plate bounding regions from tracked vehicle ROIs.
Explicitly adheres to AutoAlert Rules:
- Returns 'not detected' when confidence is low or no plate exists (never invents regions).
- Keeps plate localization decoupled from OCR.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import cv2
import numpy as np
import logging
from src.detection.detector import BoundingBox
from src.license_plate.preprocessor import crop_vehicle_roi, compute_image_sharpness

logger = logging.getLogger("autoalert.license_plate.detector")


@dataclass
class PlateDetection:
    """Structured localization output for a license plate."""
    plate_found: bool
    track_id: Optional[int]
    bbox: Optional[BoundingBox]
    confidence: float
    plate_crop: Optional[np.ndarray]
    frame_number: Optional[int] = None
    timestamp_sec: Optional[float] = None
    detector_type: str = "aspect_ratio_heuristic"  # or 'yolo_plate_model'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plate_found": self.plate_found,
            "track_id": self.track_id,
            "confidence": round(self.confidence, 3),
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3) if self.timestamp_sec is not None else None,
            "detector_type": self.detector_type,
        }


class LicensePlateDetector:
    """Detects license plate regions on tracked vehicles using model weights or geometric contours."""

    def __init__(
        self,
        model_path: Optional[str] = "models/license_plate/yolov8n_plate.pt",
        min_confidence: float = 0.40,
        min_aspect_ratio: float = 2.0,
        max_aspect_ratio: float = 5.5,
    ):
        self.model_path = model_path
        self.min_confidence = min_confidence
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.model = None
        self.detector_type = "aspect_ratio_heuristic"
        self._init_detector()

    def _init_detector(self) -> None:
        """Initialize custom plate model if path exists, otherwise fall back to geometric heuristic."""
        if self.model_path and Path(self.model_path).exists():
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                self.detector_type = "yolo_plate_model"
                logger.info(f"Loaded license plate model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not load custom plate model ({e}), using geometric fallback.")
                self.model = None
                self.detector_type = "aspect_ratio_heuristic"
        else:
            # Fallback documented: Uses rectangular aspect-ratio edge contours without unauthorized downloads
            self.detector_type = "aspect_ratio_heuristic"
            logger.info("Using geometric aspect-ratio contour detection for license plate localization.")

    def detect_plate_in_vehicle_crop(
        self,
        vehicle_crop: np.ndarray,
        vehicle_bbox: BoundingBox,
        track_id: Optional[int] = None,
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> PlateDetection:
        """Locate plate within vehicle image crop. Returns PlateDetection with plate_found=False if not found."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return PlateDetection(
                plate_found=False,
                track_id=track_id,
                bbox=None,
                confidence=0.0,
                plate_crop=None,
                frame_number=frame_number,
                timestamp_sec=timestamp_sec,
                detector_type=self.detector_type,
            )

        if self.model is not None:
            # Run YOLO plate model inference
            try:
                results = self.model.predict(source=vehicle_crop, conf=self.min_confidence, verbose=False)
                if results and results[0].boxes and len(results[0].boxes) > 0:
                    box = results[0].boxes[0]
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()
                    px1, py1, px2, py2 = map(int, xyxy)
                    plate_crop = vehicle_crop[py1:py2, px1:px2]

                    # Global frame bounding box
                    global_bbox = BoundingBox(
                        x1=vehicle_bbox.x1 + px1,
                        y1=vehicle_bbox.y1 + py1,
                        x2=vehicle_bbox.x1 + px2,
                        y2=vehicle_bbox.y1 + py2,
                    )
                    return PlateDetection(
                        plate_found=True,
                        track_id=track_id,
                        bbox=global_bbox,
                        confidence=conf,
                        plate_crop=plate_crop,
                        frame_number=frame_number,
                        timestamp_sec=timestamp_sec,
                        detector_type="yolo_plate_model",
                    )
            except Exception as e:
                logger.error(f"Error during model-based plate inference: {e}")

        # Geometric aspect-ratio contour fallback
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edged = cv2.Canny(blurred, 30, 200)

        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        best_plate_rect = None
        vh, vw = vehicle_crop.shape[:2]

        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.018 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                if h > 0:
                    aspect_ratio = float(w) / float(h)
                    # Indian/Standard vehicle plates have aspect ratio roughly 2.0 to 5.0
                    # and usually occupy 10% to 70% of vehicle width
                    if self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio:
                        if 0.10 * vw <= w <= 0.85 * vw and 0.05 * vh <= h <= 0.40 * vh:
                            best_plate_rect = (x, y, w, h)
                            break

        if best_plate_rect is not None:
            x, y, w, h = best_plate_rect
            plate_crop = vehicle_crop[y:y+h, x:x+w]
            global_bbox = BoundingBox(
                x1=vehicle_bbox.x1 + x,
                y1=vehicle_bbox.y1 + y,
                x2=vehicle_bbox.x1 + x + w,
                y2=vehicle_bbox.y1 + y + h,
            )
            return PlateDetection(
                plate_found=True,
                track_id=track_id,
                bbox=global_bbox,
                confidence=0.72,
                plate_crop=plate_crop,
                frame_number=frame_number,
                timestamp_sec=timestamp_sec,
                detector_type="aspect_ratio_heuristic",
            )

        # Plate not detected; return explicit negative result
        return PlateDetection(
            plate_found=False,
            track_id=track_id,
            bbox=None,
            confidence=0.0,
            plate_crop=None,
            frame_number=frame_number,
            timestamp_sec=timestamp_sec,
            detector_type=self.detector_type,
        )

    def select_best_crop(
        self,
        candidate_frames: List[Tuple[int, float, np.ndarray, BoundingBox]]
    ) -> Optional[Tuple[int, float, np.ndarray, BoundingBox]]:
        """Select clearest/largest vehicle crop among candidate frames based on area and sharpness."""
        if not candidate_frames:
            return None

        best_score = -1.0
        best_candidate = None

        for frame_num, t_sec, frame, bbox in candidate_frames:
            crop = crop_vehicle_roi(frame, bbox)
            if crop is None or crop.size == 0:
                continue
            sharpness = compute_image_sharpness(crop)
            score = (bbox.area ** 0.5) * (sharpness ** 0.5)
            if score > best_score:
                best_score = score
                best_candidate = (frame_num, t_sec, frame, bbox)

        return best_candidate
