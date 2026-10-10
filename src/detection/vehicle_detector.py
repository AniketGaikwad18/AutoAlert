"""Specialized vehicle detector for AutoAlert."""

from typing import List, Optional
import numpy as np
from src.detection.detector import BaseDetector, Detection, YOLOObjectDetector


class VehicleDetector:
    """Specialized detector filtering for vehicle classes: car, motorcycle, bus, truck."""

    VEHICLE_CLASSES = ["car", "motorcycle", "bus", "truck"]

    def __init__(self, base_detector: Optional[BaseDetector] = None):
        self.detector = base_detector or YOLOObjectDetector(
            classes_of_interest=self.VEHICLE_CLASSES
        )

    def detect_vehicles(
        self,
        frame: np.ndarray,
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> List[Detection]:
        """Run detection and filter strictly for vehicles."""
        all_detections = self.detector.detect(
            frame,
            frame_number=frame_number,
            timestamp_sec=timestamp_sec
        )
        return [d for d in all_detections if d.class_name in self.VEHICLE_CLASSES]
