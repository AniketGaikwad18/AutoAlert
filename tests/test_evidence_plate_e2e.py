"""
Comprehensive End-to-End Tests for Evidence Generation & Number Plate Pipeline (Phases 9–10).

Validates:
1. Evidence Generation Pipeline:
   - For every verified incident:
     - saves incident metadata
     - saves evidence frames (verifies physical JPEG files)
     - saves evidence video (verifies physical MP4 video clip)
     - saves timestamp
     - saves camera ID
     - saves location metadata
     - saves detected tracks
2. Modular Number-Plate OCR Pipeline:
   - vehicle → best frames → plate detection → crop → preprocessing → OCR → confidence → temporal aggregation
   - If the plate cannot be read, returns "unreadable"
   - Never invents a plate number
   - Keeps OCR modular so PaddleOCR / EasyOCR / Custom backends can be plugged in without rewriting incident engine
3. Physical verification of all generated evidence files.
"""

import json
import os
import shutil
import tempfile
import unittest
from typing import List
import cv2
import numpy as np

from src.core.event import VerificationState, VerifiedIncident
from src.core.incident import IncidentPackage, LocationInfo
from src.evidence.frame_capture import FrameBuffer, BufferedFrame
from src.evidence.recorder import EvidenceRecorder, EvidenceRecorderConfig, sanitize_filename
from src.evidence.incident_report import IncidentReport, build_incident_package
from src.tracking.tracker import TrackedObject, TrackSnapshot
from src.license_plate.detector import (
    LicensePlateDetector,
    LicensePlateDetectorConfig,
    PlateDetectionResult,
    BestFramePlateSelector,
)
from src.license_plate.preprocessor import PlatePreprocessor, PlateCrop
from src.license_plate.ocr import (
    BaseOCREngine,
    MockOCREngine,
    PaddleOCREngine,
    EasyOCREngine,
    PrototypeOCREngine,
    PlateOCREngine,
    PlateOCRConfig,
    OCRResult,
)
from src.license_plate.aggregator import (
    PlateTemporalAggregator,
    PlateAggregatorConfig,
    AggregatedPlateReading,
)
from src.license_plate.pipeline import (
    NumberPlateService,
    LicensePlatePipelineConfig,
)


def create_synthetic_frame_with_plate(
    width: int = 400,
    height: int = 300,
    draw_plate: bool = True,
    plate_text_noise: bool = False,
) -> np.ndarray:
    """Create a synthetic frame with vehicle and optional license plate."""
    frame = np.full((height, width, 3), (90, 90, 90), dtype=np.uint8)
    # Vehicle rectangle
    cv2.rectangle(frame, (40, 40), (360, 260), (30, 30, 30), -1)

    if draw_plate:
        # License plate white background
        cv2.rectangle(frame, (140, 200), (260, 235), (245, 245, 245), -1)
        if not plate_text_noise:
            # Contrast pattern representing plate characters
            for x in range(150, 250, 10):
                cv2.rectangle(frame, (x, 208), (x + 4, 227), (15, 15, 15), -1)
    return frame


class TestEvidenceAndPlatePipelineE2E(unittest.TestCase):
    """End-to-End test suite for Phases 9 & 10."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = EvidenceRecorderConfig(
            output_dir=self.temp_dir,
            save_key_frames=True,
            save_video_clip=True,
            pre_event_buffer_seconds=1.0,
            post_event_buffer_seconds=1.0,
            fps=10.0,
        )
        self.recorder = EvidenceRecorder(config=self.config)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # ----------------------------------------------------------------------
    # Phase 9: Evidence Generation Tests
    # ----------------------------------------------------------------------

    def test_phase9_complete_evidence_package_generation(self):
        """Phase 9: Saves metadata, keyframes, video clip, timestamp, camera_id, location, and tracks."""
        # 1. Prepare circular frame buffer with 30 frames
        buf = FrameBuffer(max_buffer_size=50)
        for f in range(30):
            img = create_synthetic_frame_with_plate(draw_plate=True)
            buf.add_frame(f, timestamp=f * 0.1, image=img)

        # 2. Verified Incident from upstream Stage 9
        incident = VerifiedIncident(
            incident_id="INCIDENT-VEHICLE_COLLISION-F15-001",
            incident_type="vehicle_collision",
            verification_state=VerificationState.VERIFIED,
            confidence_score=0.92,
            initial_candidate_id="COLLISION-CAND-F10",
            first_detected_frame=10,
            verified_frame=15,
            timestamp=1.5,
            track_ids=[1, 2],
            signals_summary={
                "spatial_proximity_score": 0.95,
                "approach_rate_score": 0.88,
                "closing_speed_px_per_frame": 12.5,
            },
            verification_reason="Collision kinematics verified over 3 frames",
        )

        location_dict = {
            "name": "Main Street Junction",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "zone_id": "ZONE-NORTH-A",
        }

        # 3. Record Evidence
        report = self.recorder.record_evidence(
            incident=incident,
            frame_buffer=buf,
            camera_id="CAM-001",
            location=location_dict,
            plate_readings=[{"track_id": 1, "plate_number": "MH12AB1234", "confidence": 0.90}],
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.camera_id, "CAM-001")
        self.assertEqual(report.location, location_dict)
        self.assertEqual(report.track_ids, [1, 2])
        self.assertEqual(report.timestamp, 1.5)
        self.assertEqual(report.incident_id, "INCIDENT-VEHICLE_COLLISION-F15-001")

        # 4. Verify Physical Output Files on Disk
        folder_name = sanitize_filename(incident.incident_id)
        incident_dir = os.path.join(self.temp_dir, folder_name)
        self.assertTrue(os.path.exists(incident_dir))

        # Check JSON Report
        json_path = os.path.join(incident_dir, "incident_report.json")
        self.assertTrue(os.path.exists(json_path))
        with open(json_path, "r", encoding="utf-8") as f:
            saved_json = json.load(f)

        self.assertEqual(saved_json["incident_id"], incident.incident_id)
        self.assertEqual(saved_json["camera_id"], "CAM-001")
        self.assertEqual(saved_json["location"]["name"], "Main Street Junction")
        self.assertEqual(saved_json["track_ids"], [1, 2])
        self.assertEqual(saved_json["timestamp"], 1.5)

        # Check Key Frame JPEGs
        self.assertGreaterEqual(len(report.evidence_files["key_frames"]), 1)
        for kf in report.evidence_files["key_frames"]:
            full_kf_path = os.path.join(self.temp_dir, kf)
            self.assertTrue(os.path.exists(full_kf_path))
            read_img = cv2.imread(full_kf_path)
            self.assertIsNotNone(read_img)
            self.assertEqual(read_img.shape, (300, 400, 3))

        # Check MP4 Video Clip
        clip_rel = report.evidence_files["video_clip"]
        self.assertIsNotNone(clip_rel)
        full_clip_path = os.path.join(self.temp_dir, clip_rel)
        self.assertTrue(os.path.exists(full_clip_path))
        self.assertGreater(os.path.getsize(full_clip_path), 0)

        # 5. Build Unified IncidentPackage
        pkg = build_incident_package(
            verified_incident=incident,
            evidence_files=report.evidence_files,
            camera_id="CAM-001",
            location=LocationInfo(**location_dict),
            plate_readings=[
                AggregatedPlateReading(
                    track_id=1,
                    best_plate_number="MH12AB1234",
                    aggregated_confidence=0.90,
                    readings_count=2,
                    format_validated=True,
                    status="verified_reading",
                )
            ],
        )

        self.assertIsInstance(pkg, IncidentPackage)
        self.assertEqual(pkg.camera_id, "CAM-001")
        self.assertEqual(pkg.location.latitude, 18.5204)
        self.assertEqual(pkg.plate_readings[0].plate_number, "MH12AB1234")

    # ----------------------------------------------------------------------
    # Phase 10: Number-Plate OCR Pipeline Tests
    # ----------------------------------------------------------------------

    def test_phase10_modular_plate_service_flow(self):
        """Phase 10: Full chain: vehicle -> best frames -> plate detection -> crop -> preprocessing -> OCR -> confidence -> temporal aggregation."""
        # Use deterministic mock backend for precise pipeline verification
        mock_backend = MockOCREngine(predefined_text="DL01CA1234", predefined_confidence=0.92)
        service = NumberPlateService(
            LicensePlatePipelineConfig(
                detector_config=LicensePlateDetectorConfig(confidence_threshold=0.25),
                ocr_backend=mock_backend,
            )
        )

        # Generate frames with vehicle and plate
        frames: List[np.ndarray] = []
        for _ in range(5):
            frames.append(create_synthetic_frame_with_plate(draw_plate=True))

        # Create TrackedObject with 3 snapshots
        snapshots = [
            TrackSnapshot(bbox=(40, 40, 360, 260), confidence=0.9, frame_index=0),
            TrackSnapshot(bbox=(40, 40, 360, 260), confidence=0.9, frame_index=1),
            TrackSnapshot(bbox=(40, 40, 360, 260), confidence=0.9, frame_index=2),
        ]
        vehicle_track = TrackedObject(
            track_id=10,
            class_name="car",
            confidence=0.9,
            bbox=(40, 40, 360, 260),
            history=snapshots,
        )

        # Process full track history
        result = service.process_vehicle_track_history(frames, vehicle_track)

        self.assertIsInstance(result, AggregatedPlateReading)
        self.assertEqual(result.track_id, 10)
        self.assertEqual(result.best_plate_number, "DL01CA1234")
        self.assertEqual(result.status, "verified_reading")
        self.assertTrue(result.format_validated)
        self.assertGreaterEqual(result.aggregated_confidence, 0.90)

        # Verify best crop selection hook
        best_crop = service.get_best_crop(10)
        self.assertIsNotNone(best_crop)
        self.assertEqual(best_crop.track_id, 10)
        self.assertGreater(best_crop.quality_score, 0.0)

    def test_phase10_unreadable_plate_returns_unreadable_never_invents_text(self):
        """Phase 10: If the plate cannot be read, return 'unreadable'. Never invent a plate number."""
        service = NumberPlateService(
            LicensePlatePipelineConfig(
                detector_config=LicensePlateDetectorConfig(confidence_threshold=0.40)
            )
        )

        # Vehicle frame with NO plate drawn (flat dark body)
        frames = [create_synthetic_frame_with_plate(draw_plate=False) for _ in range(3)]
        snapshots = [
            TrackSnapshot(bbox=(40, 40, 360, 260), confidence=0.9, frame_index=i)
            for i in range(3)
        ]
        vehicle_no_plate = TrackedObject(
            track_id=88,
            class_name="car",
            confidence=0.9,
            bbox=(40, 40, 360, 260),
            history=snapshots,
        )

        result = service.process_vehicle_track_history(frames, vehicle_no_plate)

        self.assertEqual(result.track_id, 88)
        self.assertEqual(result.best_plate_number, "unreadable")
        self.assertEqual(result.status, "unreadable")
        self.assertFalse(result.format_validated)
        self.assertEqual(result.aggregated_confidence, 0.0)

    def test_phase10_paddleocr_engine_modularity(self):
        """Phase 10: PaddleOCR engine can be plugged in or configured dynamically without rewriting incident engine."""
        service = NumberPlateService()

        # Instantiate PaddleOCR backend adapter
        paddle_backend = PaddleOCREngine()
        self.assertEqual(paddle_backend.name, "paddleocr")

        # Plug into service dynamically
        service.set_ocr_backend(paddle_backend)
        self.assertEqual(service.ocr_engine.engine_name, "paddleocr")

        # Switch to EasyOCR backend
        easy_backend = EasyOCREngine()
        service.set_ocr_backend(easy_backend)
        self.assertEqual(service.ocr_engine.engine_name, "easyocr")


if __name__ == "__main__":
    unittest.main()
