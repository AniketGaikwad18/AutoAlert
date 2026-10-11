"""Visual anomaly detection module for AutoAlert prototype exhibition.

Implements color and spatial contour filtering with temporal persistence.
Explicitly adheres to AutoAlert Rule 8: Neutral label 'red/liquid-like visual anomaly',
never described as a reliable biological blood detector.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import cv2
import logging
from src.detection.detector import BoundingBox

logger = logging.getLogger("autoalert.events.anomaly")

LIMITATION_STATEMENT = (
    "Color-space segmentation is subject to ambient illumination shifts, red garments, "
    "vehicle tail lights, shadows, and camera color calibration. This module produces "
    "unverified visual anomaly candidates and does not perform biological fluid identification."
)


@dataclass
class VisualAnomalyCandidate:
    """Structured candidate representing a persistent visual anomaly in the camera scene."""
    candidate_id: str
    description: str
    frame_number: int
    timestamp_sec: float
    contour_area_px: float
    bbox: BoundingBox
    persistence_frames: int
    candidate_score: float
    limitations: str = LIMITATION_STATEMENT
    status: str = "candidate"

    @property
    def frame_index(self) -> int:
        return self.frame_number

    @property
    def timestamp(self) -> float:
        return self.timestamp_sec

    @property
    def reason(self) -> str:
        return "red_liquid_visual_anomaly"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "event_type": "visual_anomaly_candidate",
            "description": self.description,
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "contour_area_px": round(self.contour_area_px, 1),
            "bbox": self.bbox.to_dict(),
            "persistence_frames": self.persistence_frames,
            "candidate_score": round(self.candidate_score, 3),
            "status": self.status,
            "limitations": self.limitations,
        }


@dataclass
class AnomalyDetectorConfig:
    """Configuration for visual anomaly detector."""
    hsv_lower1: Tuple[int, int, int] = (0, 90, 60)
    hsv_upper1: Tuple[int, int, int] = (10, 255, 255)
    hsv_lower2: Tuple[int, int, int] = (170, 90, 60)
    hsv_upper2: Tuple[int, int, int] = (180, 255, 255)
    min_area_px: float = 250.0
    max_area_px: float = 60000.0
    persistence_threshold_frames: int = 3
    persistence_frames: Optional[int] = None

    def __init__(
        self,
        hsv_lower1: Tuple[int, int, int] = (0, 90, 60),
        hsv_upper1: Tuple[int, int, int] = (10, 255, 255),
        hsv_lower2: Tuple[int, int, int] = (170, 90, 60),
        hsv_upper2: Tuple[int, int, int] = (180, 255, 255),
        min_area_px: float = 250.0,
        max_area_px: float = 60000.0,
        persistence_threshold_frames: int = 3,
        persistence_frames: Optional[int] = None,
        **kwargs
    ):
        self.hsv_lower1 = hsv_lower1
        self.hsv_upper1 = hsv_upper1
        self.hsv_lower2 = hsv_lower2
        self.hsv_upper2 = hsv_upper2
        self.min_area_px = min_area_px
        self.max_area_px = max_area_px
        pf = persistence_frames if persistence_frames is not None else persistence_threshold_frames
        self.persistence_threshold_frames = pf
        self.persistence_frames = pf
        for k, v in kwargs.items():
            setattr(self, k, v)


class VisualAnomalyDetector:
    """Detects persistent red/liquid-like visual anomalies using OpenCV HSV filtering."""

    def __init__(
        self,
        hsv_lower1: Any = (0, 90, 60),
        hsv_upper1: Tuple[int, int, int] = (10, 255, 255),
        hsv_lower2: Tuple[int, int, int] = (170, 90, 60),
        hsv_upper2: Tuple[int, int, int] = (180, 255, 255),
        min_area_px: float = 250.0,
        max_area_px: float = 60000.0,
        persistence_threshold_frames: int = 3,
        config: Optional[AnomalyDetectorConfig] = None,
    ):
        if isinstance(hsv_lower1, AnomalyDetectorConfig):
            config = hsv_lower1
            hsv_lower1 = (0, 90, 60)

        if config is not None:
            self.hsv_lower1 = np.array(getattr(config, "hsv_lower1", hsv_lower1), dtype=np.uint8)
            self.hsv_upper1 = np.array(getattr(config, "hsv_upper1", hsv_upper1), dtype=np.uint8)
            self.hsv_lower2 = np.array(getattr(config, "hsv_lower2", hsv_lower2), dtype=np.uint8)
            self.hsv_upper2 = np.array(getattr(config, "hsv_upper2", hsv_upper2), dtype=np.uint8)
            self.min_area_px = getattr(config, "min_area_px", min_area_px)
            self.max_area_px = getattr(config, "max_area_px", max_area_px)
            pf = getattr(config, "persistence_frames", getattr(config, "persistence_threshold_frames", persistence_threshold_frames))
            self.persistence_threshold_frames = pf
        else:
            self.hsv_lower1 = np.array(hsv_lower1, dtype=np.uint8)
            self.hsv_upper1 = np.array(hsv_upper1, dtype=np.uint8)
            self.hsv_lower2 = np.array(hsv_lower2, dtype=np.uint8)
            self.hsv_upper2 = np.array(hsv_upper2, dtype=np.uint8)
            self.min_area_px = min_area_px
            self.max_area_px = max_area_px
            self.persistence_threshold_frames = persistence_threshold_frames

        # Active anomaly track persistence: id -> {"bbox": BoundingBox, "frames": int, "area": float}
        self._active_anomalies: List[Dict[str, Any]] = []
        self._candidate_counter = 0

    def detect_candidates(
        self,
        frame: np.ndarray,
        frame_number: int = 0,
        timestamp_sec: float = 0.0,
        **kwargs
    ) -> List[VisualAnomalyCandidate]:
        """Alias for evaluate matching controller and test signature."""
        fn = kwargs.get("frame_index", frame_number)
        ts = kwargs.get("timestamp", timestamp_sec)
        return self.evaluate(frame, frame_number=fn, timestamp_sec=ts)

    def evaluate(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp_sec: float
    ) -> List[VisualAnomalyCandidate]:
        """Detect color contours in current frame and track persistence over consecutive frames."""
        if frame is None or frame.size == 0:
            return []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, self.hsv_lower1, self.hsv_upper1)
        mask2 = cv2.inRange(hsv, self.hsv_lower2, self.hsv_upper2)
        combined_mask = cv2.bitwise_or(mask1, mask2)

        # Morphological noise cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        current_detections: List[Tuple[BoundingBox, float]] = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if self.min_area_px <= area <= self.max_area_px:
                x, y, w, h = cv2.boundingRect(cnt)
                current_detections.append((BoundingBox(float(x), float(y), float(x + w), float(y + h)), area))

        # Associate with prior frame anomalies
        new_active = []
        candidates: List[VisualAnomalyCandidate] = []

        used_curr = set()
        for prev in self._active_anomalies:
            matched_idx = -1
            best_iou = 0.0
            for idx, (curr_bbox, _) in enumerate(current_detections):
                if idx in used_curr:
                    continue
                iou = prev["bbox"].iou(curr_bbox)
                if iou > 0.2 and iou > best_iou:
                    best_iou = iou
                    matched_idx = idx

            if matched_idx != -1:
                curr_bbox, area = current_detections[matched_idx]
                used_curr.add(matched_idx)
                frames_cnt = prev["frames"] + 1
                new_active.append({
                    "bbox": curr_bbox,
                    "frames": frames_cnt,
                    "area": area
                })

                if frames_cnt >= self.persistence_threshold_frames:
                    self._candidate_counter += 1
                    cand_id = f"CAND-ANOM-{self._candidate_counter:04d}"
                    score = min(0.95, 0.5 + (frames_cnt / (self.persistence_threshold_frames * 2)) * 0.45)
                    cand = VisualAnomalyCandidate(
                        candidate_id=cand_id,
                        description="Red/liquid-like visual anomaly candidate",
                        frame_number=frame_number,
                        timestamp_sec=timestamp_sec,
                        contour_area_px=area,
                        bbox=curr_bbox,
                        persistence_frames=frames_cnt,
                        candidate_score=score,
                        status="candidate"
                    )
                    candidates.append(cand)

        # Add remaining new detections as new active entries (starting at 1 frame)
        for idx, (bbox, area) in enumerate(current_detections):
            if idx not in used_curr:
                new_active.append({
                    "bbox": bbox,
                    "frames": 1,
                    "area": area
                })

        self._active_anomalies = new_active
        return candidates
