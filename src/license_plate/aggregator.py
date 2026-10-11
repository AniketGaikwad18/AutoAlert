"""Temporal aggregation of license plate readings for AutoAlert.

Combines multiple noisy OCR readings across consecutive video frames for a vehicle
track ID using weighted majority voting.
Adheres to AutoAlert Rules: Never fabricates missing characters; explicitly reports
unreadable/low-confidence status when evidence is insufficient.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from src.license_plate.ocr import OCRReading, validate_indian_plate_format

logger = logging.getLogger("autoalert.license_plate.aggregator")


@dataclass
class AggregatedPlateResult:
    """Consolidated plate result across multiple temporal observations."""
    track_id: int = 1
    plate_text: Optional[str] = None
    confidence: float = 0.0
    readings_count: int = 0
    is_readable: bool = False
    status: str = "unreadable"
    sample_readings: List[Dict[str, Any]] = field(default_factory=list)
    format_valid: bool = False

    def __init__(
        self,
        track_id: int = 1,
        plate_text: Optional[str] = None,
        confidence: float = 0.0,
        readings_count: int = 0,
        is_readable: bool = False,
        status: str = "unreadable",
        sample_readings: Optional[List[Dict[str, Any]]] = None,
        format_valid: bool = False,
        best_plate_number: Optional[str] = None,
        aggregated_confidence: Optional[float] = None,
        format_validated: Optional[bool] = None,
        **kwargs
    ):
        self.track_id = track_id
        self.plate_text = best_plate_number if best_plate_number is not None else plate_text
        self.confidence = aggregated_confidence if aggregated_confidence is not None else confidence
        self.readings_count = readings_count
        self.is_readable = is_readable or bool(self.plate_text and self.plate_text != "unreadable")
        self.status = status
        self.sample_readings = sample_readings or []
        self.format_valid = format_validated if format_validated is not None else format_valid

    @property
    def best_plate_number(self) -> str:
        return self.plate_text if (self.is_readable and self.plate_text) else "unreadable"

    @property
    def aggregated_confidence(self) -> float:
        return self.confidence

    @property
    def format_validated(self) -> bool:
        return self.format_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "plate_text": self.plate_text,
            "confidence": round(self.confidence, 4),
            "readings_count": self.readings_count,
            "is_readable": self.is_readable,
            "status": self.status,
            "format_valid": self.format_valid,
            "sample_readings": self.sample_readings,
        }


# Stage 15-20 aliases
AggregatedPlateReading = AggregatedPlateResult


@dataclass
class PlateAggregatorConfig:
    """Configuration for temporal plate aggregator."""
    min_confidence: float = 0.50
    min_observations: int = 1


class TemporalPlateAggregator:
    """Aggregates and filters multiple OCR readings across frames for each vehicle track."""

    def __init__(
        self,
        min_confidence: Union[float, PlateAggregatorConfig, None] = 0.50,
        min_observations: int = 1,
        config: Optional[PlateAggregatorConfig] = None
    ):
        if isinstance(min_confidence, PlateAggregatorConfig):
            config = min_confidence
            min_confidence = 0.50

        if config is not None:
            self.min_confidence = config.min_confidence if config.min_confidence is not None else 0.50
            self.min_observations = config.min_observations if config.min_observations is not None else 1
        else:
            self.min_confidence = min_confidence if min_confidence is not None else 0.50
            self.min_observations = min_observations if min_observations is not None else 1
        self._history: Dict[int, List[OCRReading]] = defaultdict(list)

    def add_reading(self, reading: OCRReading) -> None:
        """Add a frame reading for a vehicle track."""
        if reading.track_id is not None:
            self._history[reading.track_id].append(reading)

    def aggregate_track(self, track_id: int) -> AggregatedPlateResult:
        """Alias for get_aggregated_result."""
        return self.get_aggregated_result(track_id)

    def get_aggregated_result(self, track_id: int) -> AggregatedPlateResult:
        """Combine accumulated readings for the vehicle track into an aggregated result."""
        readings = self._history.get(track_id, [])
        if not readings:
            return AggregatedPlateResult(
                track_id=track_id,
                plate_text=None,
                confidence=0.0,
                readings_count=0,
                is_readable=False,
                status="unreadable",
                format_valid=False,
            )

        # Filter for non-empty normalized candidates
        valid_readings = [r for r in readings if r.normalized_text and len(r.normalized_text) >= 4]

        if not valid_readings:
            return AggregatedPlateResult(
                track_id=track_id,
                plate_text=None,
                confidence=0.0,
                readings_count=len(readings),
                is_readable=False,
                status="unreadable",
                format_valid=False,
                sample_readings=[r.to_dict() for r in readings[:3]],
            )

        # Weighted voting across candidate strings
        candidate_weights: Dict[str, float] = defaultdict(float)
        candidate_confs: Dict[str, List[float]] = defaultdict(list)

        for r in valid_readings:
            text = r.normalized_text
            # Indian format match adds weighting bonus to the candidate
            weight = r.confidence * (1.2 if r.is_valid_format else 1.0)
            candidate_weights[text] += weight
            candidate_confs[text].append(r.confidence)

        best_candidate, best_weight = max(candidate_weights.items(), key=lambda item: item[1])
        avg_conf = float(sum(candidate_confs[best_candidate]) / len(candidate_confs[best_candidate]))
        is_fmt_valid, _ = validate_indian_plate_format(best_candidate)

        is_readable = avg_conf >= self.min_confidence and len(valid_readings) >= self.min_observations
        status = "verified_reading" if is_readable else "unreadable"

        return AggregatedPlateResult(
            track_id=track_id,
            plate_text=best_candidate if is_readable else None,
            confidence=avg_conf if is_readable else 0.0,
            readings_count=len(readings),
            is_readable=is_readable,
            status=status,
            format_valid=is_fmt_valid if is_readable else False,
            sample_readings=[r.to_dict() for r in readings[:5]],
        )

    def clear(self) -> None:
        """Clear all historical readings."""
        self._history.clear()


# Stage 15-20 alias
PlateTemporalAggregator = TemporalPlateAggregator

