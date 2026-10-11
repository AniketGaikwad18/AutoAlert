"""
Modular Number Plate OCR Pipeline & Service for AutoAlert (Phases 9–10).

Executes the step-by-step plate recognition workflow:
  vehicle (TrackedObject)
  → best frames (frame selection from temporal buffer / video)
  → plate detection (LicensePlateDetector locating plate bounding box)
  → crop (PlateCrop extraction)
  → preprocessing (PlatePreprocessor: CLAHE, grayscale, contrast enhancement, Laplacian sharpness)
  → OCR (Pluggable BaseOCREngine: PaddleOCR, EasyOCR, Prototype, or Mock)
  → confidence (raw confidence + format validation bonus)
  → temporal aggregation (PlateTemporalAggregator weighted consensus)
  → returns structured AggregatedPlateReading or 'unreadable' (never invents characters)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import List, Dict, Any, Optional, Union

import numpy as np

from src.tracking.tracker import TrackedObject
from src.license_plate.detector import (
    LicensePlateDetector,
    LicensePlateDetectorConfig,
    PlateDetectionResult,
    BestFramePlateSelector,
)
from src.license_plate.preprocessor import (
    PlatePreprocessor,
    PlatePreprocessorConfig,
    PlateCrop,
)
from src.license_plate.ocr import (
    PlateOCREngine,
    PlateOCRConfig,
    BaseOCREngine,
    OCRResult,
    normalize_plate_text,
    validate_indian_plate_format,
)
from src.license_plate.aggregator import (
    PlateTemporalAggregator,
    PlateAggregatorConfig,
    AggregatedPlateReading,
)

logger = logging.getLogger(__name__)


@dataclass
class LicensePlatePipelineConfig:
    """Configurable parameters for the end-to-end number plate pipeline."""
    detector_config: Optional[LicensePlateDetectorConfig] = None
    preprocessor_config: Optional[PlatePreprocessorConfig] = None
    ocr_config: Optional[PlateOCRConfig] = None
    aggregator_config: Optional[PlateAggregatorConfig] = None
    ocr_backend: Optional[BaseOCREngine] = None


class NumberPlateService:
    """Modular Number Plate Recognition Service.

    Coordinates vehicle tracking history, best frame selection, plate detection,
    crop preprocessing, pluggable OCR extraction (PaddleOCR / EasyOCR / Prototype),
    confidence scoring, and multi-frame temporal consensus aggregation.
    """

    def __init__(self, config: Optional[LicensePlatePipelineConfig] = None) -> None:
        self.config = config or LicensePlatePipelineConfig()

        self.detector = LicensePlateDetector(self.config.detector_config)
        self.preprocessor = PlatePreprocessor(self.config.preprocessor_config)
        if self.config.ocr_backend is not None:
            if isinstance(self.config.ocr_backend, BaseOCREngine):
                self.ocr_engine = self.config.ocr_backend
            else:
                self.ocr_engine = PlateOCREngine(
                    config=self.config.ocr_config,
                    backend_engine=str(self.config.ocr_backend),
                )
        else:
            self.ocr_engine = PlateOCREngine(config=self.config.ocr_config)
        self.aggregator = PlateTemporalAggregator(self.config.aggregator_config)
        self.best_frame_selector = BestFramePlateSelector()

    def set_ocr_backend(self, backend: BaseOCREngine) -> None:
        """Dynamically configure or switch OCR backend (e.g., PaddleOCR, EasyOCR)."""
        if isinstance(backend, BaseOCREngine):
            self.ocr_engine = backend
        else:
            self.ocr_engine.set_backend(backend)

    def process_vehicle_frame(
        self,
        frame: Optional[np.ndarray],
        tracked_vehicle: TrackedObject,
        frame_index: int,
    ) -> PlateDetectionResult:
        """Process a single frame for a tracked vehicle.

        Steps:
          1. Plate Detection in vehicle bbox
          2. Plate Crop extraction
          3. Preprocessing (CLAHE, grayscale, sharpness)
          4. OCR Text Extraction via pluggable backend
          5. Confidence Scoring & Format Validation
          6. Push to temporal aggregator
        """
        # 1-3. Detect and preprocess plate crop
        det_result = self.detector.detect_plate(
            frame=frame,
            tracked_object=tracked_vehicle,
            frame_index=frame_index,
        )

        self.best_frame_selector.add_result(det_result)

        if det_result.detected and det_result.plate_crop is not None:
            # 4-5. Run OCR on detected crop
            ocr_result = self.ocr_engine.read_plate(
                det_result.plate_crop,
                track_id=tracked_vehicle.track_id,
                frame_number=frame_index,
            )
            # 6. Add to temporal aggregator
            self.aggregator.add_reading(ocr_result)
        else:
            # Record unreadable reading for track audit
            unreadable_ocr = OCRResult(
                track_id=tracked_vehicle.track_id,
                frame_number=frame_index,
                raw_text="",
                normalized_text="",
                confidence=0.0,
                is_valid_format=False,
                is_readable=False,
                status="unreadable",
            )
            self.aggregator.add_reading(unreadable_ocr)

        return det_result

    def process_vehicle_track_history(
        self,
        frames: List[np.ndarray],
        tracked_vehicle: TrackedObject,
    ) -> AggregatedPlateReading:
        """Process full temporal history of a vehicle track across recorded frames.

        Parameters
        ----------
        frames : List[np.ndarray]
            List of video frames corresponding to the vehicle's timeline.
        tracked_vehicle : TrackedObject
            Tracked vehicle with snapshot history.

        Returns
        -------
        AggregatedPlateReading
            Consensus license plate reading (or 'unreadable' if text cannot be read).
        """
        track_id = tracked_vehicle.track_id

        # Iterate over snapshots in track history
        for snap in tracked_vehicle.history:
            f_idx = snap.frame_index
            if 0 <= f_idx < len(frames):
                frame_img = frames[f_idx]
                # Create temporary TrackedObject pointing to snapshot bbox
                temp_obj = TrackedObject(
                    track_id=track_id,
                    class_name=tracked_vehicle.class_name,
                    confidence=snap.confidence,
                    bbox=snap.bbox,
                    history=[snap],
                )
                self.process_vehicle_frame(frame_img, temp_obj, frame_index=f_idx)

        # Compute temporal aggregation consensus
        return self.get_aggregated_reading(track_id)

    def get_aggregated_reading(self, track_id: int) -> AggregatedPlateReading:
        """Retrieve aggregated consensus reading for a given vehicle track ID."""
        return self.aggregator.aggregate_track(track_id)

    def get_best_crop(self, track_id: int) -> Optional[PlateCrop]:
        """Retrieve highest-quality crop selected for vehicle track ID."""
        return self.best_frame_selector.get_best_crop(track_id)

    def reset(self) -> None:
        """Reset internal temporal aggregation and frame selection state."""
        self.aggregator.clear()
        self.best_frame_selector.clear()
        logger.info("NumberPlateService reset")
