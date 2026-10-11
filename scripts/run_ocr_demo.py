"""
Stage 12 Controlled OCR & Temporal Aggregation Sample Script.

Demonstrates number plate crop OCR extraction, text normalization, Indian format validation aid,
and multi-frame temporal consensus aggregation for vehicle tracks.
"""

import numpy as np

from src.license_plate.preprocessor import PlateCrop
from src.license_plate.ocr import (
    PlateOCREngine,
    PlateOCRConfig,
    normalize_plate_text,
    validate_indian_plate_format,
)
from src.license_plate.aggregator import (
    PlateTemporalAggregator,
    PlateAggregatorConfig,
)


def run_ocr_demo():
    print("=" * 60)
    print("AutoAlert Stage 12: Number Plate OCR & Temporal Aggregation Demo")
    print("=" * 60)

    # Initialize OCR engine and temporal aggregator
    engine = PlateOCREngine(PlateOCRConfig(engine_type="prototype"))
    aggregator = PlateTemporalAggregator(PlateAggregatorConfig(min_readings=2))

    print(f"\nActive OCR Engine: {engine.engine_name}")

    # 1. Controlled Sample 1: Standard Indian Plate Crop (MH12AB1234)
    print("\n--- Controlled Sample 1: Standard Vehicle Track ID = 10 ---")
    img_contrast = np.zeros((60, 200, 3), dtype=np.uint8)
    img_contrast[10:50, 10:190] = (240, 240, 240)  # Contrast plate background

    crop_sample1 = PlateCrop(
        crop_id="CROP-T10-F5",
        track_id=10,
        frame_index=5,
        bbox=(50, 50, 250, 110),
        confidence=0.88,
        raw_crop=img_contrast,
        processed_crop=img_contrast[:, :, 0],
        quality_score=55.0,
    )

    ocr_res1 = engine.read_plate(crop_sample1)
    print(f"  Frame 5 OCR Output:")
    print(f"    Raw Text:              '{ocr_res1.raw_text}'")
    print(f"    Normalized Text:       '{ocr_res1.normalized_text}'")
    print(f"    Format Validated:       {ocr_res1.is_valid_format}")
    print(f"    Composite Confidence:   {ocr_res1.composite_confidence:.2f}")
    print(f"    Status:                 '{ocr_res1.status}'")

    aggregator.add_reading(ocr_res1)

    # Frame 6 & 7 readings for Track 10
    crop_sample1_f6 = PlateCrop(
        crop_id="CROP-T10-F6", track_id=10, frame_index=6,
        bbox=(52, 50, 252, 110), confidence=0.90, raw_crop=img_contrast,
        processed_crop=img_contrast[:, :, 0], quality_score=60.0,
    )
    ocr_res1_f6 = engine.read_plate(crop_sample1_f6)
    aggregator.add_reading(ocr_res1_f6)

    agg1 = aggregator.aggregate_track(10)
    print(f"\n  Multi-Frame Aggregated Reading for Track ID = 10:")
    print(f"    Consensus Plate Number: '{agg1.best_plate_number}'")
    print(f"    Aggregated Confidence:  {agg1.aggregated_confidence:.2f}")
    print(f"    Readings Processed:     {agg1.readings_count}")
    print(f"    Overall Status:         '{agg1.status}'")

    # 2. Controlled Sample 2: Empty/Unreadable Crop (Track ID = 22)
    print("\n--- Controlled Sample 2: Dark/Unreadable Vehicle Track ID = 22 ---")
    img_flat = np.zeros((60, 200, 3), dtype=np.uint8)  # Flat image (no plate edges)

    crop_sample2 = PlateCrop(
        crop_id="CROP-T22-F12",
        track_id=22,
        frame_index=12,
        bbox=(100, 100, 300, 160),
        confidence=0.45,
        raw_crop=img_flat,
        processed_crop=img_flat[:, :, 0],
        quality_score=0.0,
    )

    ocr_res2 = engine.read_plate(crop_sample2)
    print(f"  Frame 12 OCR Output:")
    print(f"    Raw Text:              '{ocr_res2.raw_text}'")
    print(f"    Normalized Text:       '{ocr_res2.normalized_text}'")
    print(f"    Format Validated:       {ocr_res2.is_valid_format}")
    print(f"    Composite Confidence:   {ocr_res2.composite_confidence:.2f}")
    print(f"    Status:                 '{ocr_res2.status}'")

    aggregator.add_reading(ocr_res2)
    agg2 = aggregator.aggregate_track(22)
    print(f"\n  Multi-Frame Aggregated Reading for Track ID = 22:")
    print(f"    Consensus Plate Number: '{agg2.best_plate_number}'")
    print(f"    Aggregated Confidence:  {agg2.aggregated_confidence:.2f}")
    print(f"    Overall Status:         '{agg2.status}'")

    # 3. Format Validation Aid Direct Test
    print("\n--- Indian Format Validation Aid Direct Test ---")
    test_strings = ["MH-12 AB 1234", "22 BH 9999 X", "MH12", "INVALID_TEXT"]
    for s in test_strings:
        norm = normalize_plate_text(s)
        is_val, fmt = validate_indian_plate_format(norm)
        print(f"  Raw: '{s:15s}' -> Norm: '{norm:12s}' -> Valid: {is_val!s:5s} ({fmt})")


if __name__ == "__main__":
    run_ocr_demo()
