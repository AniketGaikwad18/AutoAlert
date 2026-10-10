"""Optical Character Recognition (OCR) module for vehicle license plates.

Extracts, normalizes, and validates plate text.
Explicitly adheres to AutoAlert Rules 9 & 10:
- OCR output is never treated as ground truth.
- Supports unreadable / low-confidence results.
- Never fabricates missing characters.
- Indian plate format matching is a validation aid, never an excuse to invent characters.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import re
import cv2
import numpy as np
import logging
from src.license_plate.preprocessor import preprocess_plate_image

logger = logging.getLogger("autoalert.license_plate.ocr")

# Indian Registration regex patterns (Standard: MH12AB1234, BH Series: 22BH1234AA)
INDIAN_PLATE_REGEX = re.compile(
    r"^(?:[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}|[0-9]{2}BH[0-9]{4}[A-Z]{1,2})$"
)


def normalize_plate_text(text: str) -> str:
    """Normalize OCR text: uppercase, remove non-alphanumeric noise, remove whitespace."""
    if not text:
        return ""
    # Remove all non-alphanumeric chars
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(text)).upper()
    return cleaned


def validate_indian_plate_format(normalized_text: str) -> Tuple[bool, str]:
    """Validate text structure against standard Indian motor vehicle registration rules."""
    if not normalized_text:
        return False, "empty_text"
    if INDIAN_PLATE_REGEX.match(normalized_text):
        return True, "valid_indian_standard"
    return False, "non_standard_or_partial"


@dataclass
class OCRReading:
    """Structured OCR reading from an individual frame crop."""
    raw_text: str
    normalized_text: str
    confidence: float
    track_id: Optional[int]
    frame_number: Optional[int]
    timestamp_sec: Optional[float]
    is_valid_format: bool
    format_note: str
    is_readable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "confidence": round(self.confidence, 4),
            "track_id": self.track_id,
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3) if self.timestamp_sec is not None else None,
            "is_valid_format": self.is_valid_format,
            "format_note": self.format_note,
            "is_readable": self.is_readable,
        }


class LicensePlateOCR:
    """Extracts characters from license plate crops with confidence scoring."""

    def __init__(self, min_confidence: float = 0.50, engine_name: str = "easyocr"):
        self.min_confidence = min_confidence
        self.engine_name = engine_name
        self._reader = None
        self._init_engine()

    def _init_engine(self) -> None:
        """Initialize EasyOCR or fallback reader."""
        if self.engine_name == "easyocr":
            try:
                import easyocr
                # Initialize English OCR reader on CPU
                self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
                logger.info("Initialized EasyOCR engine successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR ({e}); will use heuristic fallback.")
                self._reader = None

    def read_plate(
        self,
        plate_crop: np.ndarray,
        track_id: Optional[int] = None,
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> OCRReading:
        """Run OCR on preprocessed plate crop."""
        if plate_crop is None or plate_crop.size == 0:
            return OCRReading(
                raw_text="",
                normalized_text="",
                confidence=0.0,
                track_id=track_id,
                frame_number=frame_number,
                timestamp_sec=timestamp_sec,
                is_valid_format=False,
                format_note="empty_crop",
                is_readable=False,
            )

        processed = preprocess_plate_image(plate_crop, target_height=64, apply_clahe=True)

        raw_text = ""
        conf = 0.0

        if self._reader is not None:
            try:
                results = self._reader.readtext(processed)
                if results:
                    # Combine high confidence text chunks
                    texts = [r[1] for r in results]
                    confs = [r[2] for r in results]
                    raw_text = " ".join(texts)
                    conf = float(np.mean(confs))
            except Exception as e:
                logger.error(f"EasyOCR inference error: {e}")

        norm_text = normalize_plate_text(raw_text)
        is_valid_fmt, fmt_note = validate_indian_plate_format(norm_text)
        is_readable = bool(norm_text and conf >= self.min_confidence)

        return OCRReading(
            raw_text=raw_text,
            normalized_text=norm_text,
            confidence=conf,
            track_id=track_id,
            frame_number=frame_number,
            timestamp_sec=timestamp_sec,
            is_valid_format=is_valid_fmt,
            format_note=fmt_note,
            is_readable=is_readable,
        )
