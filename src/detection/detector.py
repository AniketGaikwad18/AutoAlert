"""Object detection module for AutoAlert.

Wraps deep learning detectors (e.g. Ultralytics YOLO) and produces
strongly typed, structured detection objects without tight coupling to
frame acquisition or downstream tracking.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger("autoalert.detection")


@dataclass
class BoundingBox:
    """Normalized or absolute coordinate bounding box representation."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def center(self) -> Tuple[float, float]:
        return (self.center_x, self.center_y)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_xyxy(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }

    def iou(self, other: "BoundingBox") -> float:
        """Calculate Intersection over Union (IoU) with another bounding box."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter_area = iw * ih

        union_area = self.area + other.area - inter_area
        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area


@dataclass
class Detection:
    """Structured detection candidate output by object detection models."""
    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_number: Optional[int] = None
    timestamp_sec: Optional[float] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3) if self.timestamp_sec is not None else None,
        }


class BaseDetector:
    """Abstract interface for object detectors."""

    def detect(
        self,
        frame: np.ndarray,
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> List[Detection]:
        raise NotImplementedError


class YOLOObjectDetector(BaseDetector):
    """Ultralytics YOLO detector with class filtering and error resilience."""

    COCO_CLASSES_OF_INTEREST = ["person", "car", "motorcycle", "bus", "truck"]

    def __init__(
        self,
        model_path: str = "models/detection/yolov8n.pt",
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        classes_of_interest: Optional[List[str]] = None,
        device: str = "cpu"
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.classes_of_interest = classes_of_interest or self.COCO_CLASSES_OF_INTEREST
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self) -> bool:
        """Attempt to load Ultralytics YOLO model."""
        try:
            from ultralytics import YOLO
            path = Path(self.model_path)
            if path.exists():
                self.model = YOLO(str(path))
            elif Path("yolov8n.pt").exists():
                self.model = YOLO("yolov8n.pt")
            else:
                # If neither exists and model_path is explicitly yolov8n.pt, load it
                if "yolov8n" in self.model_path:
                    self.model = YOLO("yolov8n.pt")
                else:
                    logger.warning(f"Model file not found at '{self.model_path}'.")
                    self.model = None
                    return False

            logger.info(f"Loaded YOLO model successfully on device '{self.device}'")
            return True
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None
            return False

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def detect(
        self,
        frame: np.ndarray,
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> List[Detection]:
        """Execute inference on given frame and return structured detections."""
        if not self.is_ready:
            logger.warning("Detector not initialized; returning empty detections.")
            return []

        if frame is None or frame.size == 0:
            return []

        try:
            results = self.model.predict(
                source=frame,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                device=self.device,
                verbose=False
            )
        except Exception as e:
            logger.error(f"Inference error encountered: {e}")
            return []

        detections: List[Detection] = []
        if not results:
            return detections

        r = results[0]
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            return detections

        names = r.names
        for box in boxes:
            cls_id = int(box.cls[0].item())
            cls_name = names.get(cls_id, str(cls_id))
            conf = float(box.conf[0].item())

            if self.classes_of_interest and cls_name not in self.classes_of_interest:
                continue

            xyxy = box.xyxy[0].tolist()
            bbox = BoundingBox(
                x1=float(xyxy[0]),
                y1=float(xyxy[1]),
                x2=float(xyxy[2]),
                y2=float(xyxy[3])
            )

            detections.append(Detection(
                class_name=cls_name,
                confidence=conf,
                bbox=bbox,
                frame_number=frame_number,
                timestamp_sec=timestamp_sec
            ))

        return detections
