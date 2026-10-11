"""Stage 12 Plate OCR and Temporal Aggregation Tests."""

import pytest
from src.license_plate.ocr import normalize_plate_text, validate_indian_plate_format, OCRReading, LicensePlateOCR
from src.license_plate.aggregator import TemporalPlateAggregator, AggregatedPlateResult


def test_normalize_plate_text():
    """Test character normalization and noise removal."""
    assert normalize_plate_text("mh 12 ab 1234") == "MH12AB1234"
    assert normalize_plate_text("DL-01-C-9999\n") == "DL01C9999"
    assert normalize_plate_text("  KA.04.E.7777 ") == "KA04E7777"
    assert normalize_plate_text("") == ""


def test_validate_indian_plate_format():
    """Test format validation for standard Indian registrations."""
    valid1, _ = validate_indian_plate_format("MH12AB1234")
    assert valid1 is True

    valid2, _ = validate_indian_plate_format("22BH1234AA")
    assert valid2 is True

    invalid1, note1 = validate_indian_plate_format("12345")
    assert invalid1 is False
    assert note1 == "non_standard_or_partial"


def test_temporal_plate_aggregator_multi_frame_voting():
    """Test combining multiple noisy readings across frames into a consensus result."""
    aggregator = TemporalPlateAggregator(min_confidence=0.60, min_observations=2)

    # Reading 1: Partial/noisy
    r1 = OCRReading(
        raw_text="MH 12 AB 1234",
        normalized_text="MH12AB1234",
        confidence=0.82,
        track_id=1,
        frame_number=10,
        timestamp_sec=0.33,
        is_valid_format=True,
        format_note="valid_indian_standard",
        is_readable=True
    )
    # Reading 2: Slightly noisy but agreeing
    r2 = OCRReading(
        raw_text="MH12AB1234",
        normalized_text="MH12AB1234",
        confidence=0.88,
        track_id=1,
        frame_number=12,
        timestamp_sec=0.40,
        is_valid_format=True,
        format_note="valid_indian_standard",
        is_readable=True
    )
    # Reading 3: One glitchy outlier
    r3 = OCRReading(
        raw_text="MH12AB123X",
        normalized_text="MH12AB123X",
        confidence=0.45,
        track_id=1,
        frame_number=15,
        timestamp_sec=0.50,
        is_valid_format=False,
        format_note="non_standard_or_partial",
        is_readable=False
    )

    aggregator.add_reading(r1)
    aggregator.add_reading(r2)
    aggregator.add_reading(r3)

    result = aggregator.get_aggregated_result(track_id=1)
    assert isinstance(result, AggregatedPlateResult)
    assert result.is_readable is True
    assert result.plate_text == "MH12AB1234"
    assert result.confidence >= 0.80
    assert result.status in ("verified_reading", "verified_readable")
    assert result.format_valid is True


def test_temporal_plate_aggregator_unreadable():
    """Test low confidence and insufficient readings return unreadable status without inventing text."""
    aggregator = TemporalPlateAggregator(min_confidence=0.70)

    # Single poor reading
    r = OCRReading(
        raw_text="??",
        normalized_text="",
        confidence=0.15,
        track_id=2,
        frame_number=5,
        timestamp_sec=0.16,
        is_valid_format=False,
        format_note="empty_text",
        is_readable=False
    )
    aggregator.add_reading(r)

    result = aggregator.get_aggregated_result(track_id=2)
    assert result.is_readable is False
    assert result.plate_text is None
    assert result.status in ("unreadable", "unreadable_no_text")
