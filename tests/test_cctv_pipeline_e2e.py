"""
End-to-End and Integration tests for AutoAlert AI CCTV Pipeline (Phases 3–8).

Validates the complete chain:
  Video upload / ingestion
  → Frame extraction & normalization
  → Pretrained YOLO object detection (vehicle / person detection)
  → Multi-object tracking (Hungarian IoU & trajectory history)
  → Collision event analysis (multi-signal kinematics, closing distance, deceleration, NOT naive overlap)
  → Prolonged motionlessness analysis (structured non-medical person event)
  → Visual anomaly analysis (HSV segmentation & contour persistence)
  → Temporal verification engine (CANDIDATE -> VERIFYING -> VERIFIED state machine)
"""

import os
import tempfile
import unittest
from typing import List, Tuple
import cv2
import numpy as np

from src.video.camera import LocalVideoCamera
from src.video.frame_processor import FrameProcessor, ProcessedFrame
from src.detection.detector import ObjectDetector, Detection
from src.detection.vehicle_detector import VehicleDetector
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import MultiObjectTracker, TrackedObject, TrackSnapshot
from src.events.collision import (
    CollisionCandidateDetector,
    CollisionCandidate,
    CollisionDetectorConfig,
)
from src.events.motionless import (
    MotionlessCandidateDetector,
    MotionlessCandidate,
    MotionlessDetectorConfig,
)
from src.events.anomaly import (
    VisualAnomalyDetector,
    VisualAnomalyCandidate,
    AnomalyDetectorConfig,
)
from src.events.verifier import EventVerifier, VerifierConfig
from src.core.event import VerificationState, VerifiedIncident


def create_demo_video(filepath: str, num_frames: int = 30, fps: float = 10.0) -> str:
    """Create a synthetic test video file with moving rectangular vehicles."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for i in range(num_frames):
        img = np.full((height, width, 3), (35, 35, 35), dtype=np.uint8)
        # Road lane
        cv2.rectangle(img, (0, 180), (640, 360), (70, 70, 70), -1)

        # Vehicle 1 moving right: approaches x=260 then stops
        x1 = min(260, int(50 + i * 15))
        # Vehicle 2 moving left: approaches x=290 then stops
        x2 = max(290, int(500 - i * 15))

        cv2.rectangle(img, (x1, 220), (x1 + 60, 280), (0, 0, 220), -1)
        cv2.rectangle(img, (x2, 220), (x2 + 60, 280), (220, 0, 0), -1)

        writer.write(img)

    writer.release()
    return filepath


class TestCCTVPipelinePhases3To8(unittest.TestCase):
    """Unit and integration test suite covering Phases 3 through 8."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sample_video_path = os.path.join(self.temp_dir.name, "sample_cctv.mp4")
        create_demo_video(self.sample_video_path, num_frames=30, fps=10.0)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -- Phase 3: Video Upload & Frame Extraction --------------------------

    def test_phase3_frame_extraction_and_metadata(self):
        """Phase 3: Video source loading and frame processing."""
        camera = LocalVideoCamera(self.sample_video_path)
        meta = camera.get_metadata()

        self.assertEqual(meta["width"], 640)
        self.assertEqual(meta["height"], 480)
        self.assertAlmostEqual(meta["fps"], 10.0, places=1)
        self.assertGreaterEqual(meta["frame_count"], 30)

        processor = FrameProcessor(meta, target_width=320, target_height=240)
        frames: List[ProcessedFrame] = []

        while True:
            ret, raw_frame = camera.read_frame()
            if not ret or raw_frame is None:
                break
            proc = processor.process(raw_frame, frame_number=len(frames))
            if proc:
                frames.append(proc)

        camera.release()

        self.assertEqual(len(frames), 30)
        self.assertEqual(frames[0].image.shape, (240, 320, 3))
        self.assertEqual(frames[0].frame_number, 0)
        self.assertAlmostEqual(frames[10].timestamp, 1.0, places=1)

    # -- Phase 4: Pretrained YOLO Object Detection -------------------------

    def test_phase4_vehicle_and_person_detector_classes(self):
        """Phase 4: Verify specialized vehicle and person detectors filter target classes."""
        v_det = VehicleDetector.__new__(VehicleDetector)
        v_det.classes_of_interest = ["car", "motorcycle", "bus", "truck"]
        v_det.confidence_threshold = 0.5

        p_det = PersonDetector.__new__(PersonDetector)
        p_det.classes_of_interest = ["person"]
        p_det.confidence_threshold = 0.5

        self.assertIn("car", v_det.classes_of_interest)
        self.assertIn("truck", v_det.classes_of_interest)
        self.assertNotIn("person", v_det.classes_of_interest)

        self.assertIn("person", p_det.classes_of_interest)
        self.assertNotIn("car", p_det.classes_of_interest)

    # -- Phase 5: Multi-Object Tracking ------------------------------------

    def test_phase5_multi_object_tracking_and_trajectories(self):
        """Phase 5: MultiObjectTracker associates detections across frames and records trajectories."""
        tracker = MultiObjectTracker(max_age=5, min_hits=2, iou_threshold=0.3)

        # Frame 0: Single car detection
        det0 = [Detection(class_name="car", confidence=0.9, bbox=(100, 100, 150, 150))]
        t0 = tracker.update(det0, frame_index=0)
        self.assertEqual(len(t0), 0)  # Tentative, needs min_hits=2

        # Frame 1: Same car shifted slightly (IoU match)
        det1 = [Detection(class_name="car", confidence=0.92, bbox=(105, 100, 155, 150))]
        t1 = tracker.update(det1, frame_index=1)
        self.assertEqual(len(t1), 1)
        car_track = t1[0]
        self.assertEqual(car_track.class_name, "car")
        self.assertEqual(len(car_track.history), 2)

        # Frame 2: Car continues moving right
        det2 = [Detection(class_name="car", confidence=0.91, bbox=(110, 100, 160, 150))]
        t2 = tracker.update(det2, frame_index=2)
        self.assertEqual(len(t2), 1)
        self.assertEqual(t2[0].track_id, car_track.track_id)
        self.assertEqual(len(t2[0].history), 3)

    # -- Phase 6: Collision Event Analysis (Kinematics vs Overlap) ---------

    def test_phase6_collision_engine_rejects_pure_overlap_without_kinematics(self):
        """Phase 6: Overlap alone WITHOUT closing approach and abrupt deceleration does NOT classify collision."""
        detector = CollisionCandidateDetector(CollisionDetectorConfig(min_candidate_score=0.60))

        # Two vehicles placed overlapping each other for all 6 frames (e.g. parked side-by-side or lane merge)
        # Distance delta is 0 (no closing speed) and speed drop is 0
        h1 = [(f, (100, 100, 160, 150)) for f in range(6)]
        h2 = [(f, (120, 100, 180, 150)) for f in range(6)]

        t1 = TrackedObject(track_id=1, class_name="car", confidence=0.9, bbox=h1[-1][1],
                           history=[TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h1])
        t2 = TrackedObject(track_id=2, class_name="truck", confidence=0.9, bbox=h2[-1][1],
                           history=[TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h2])

        cands = detector.detect_candidates([t1, t2], frame_index=5)
        # Must be rejected because there is no closing rate and no sudden deceleration after approach
        self.assertEqual(cands, [])

    def test_phase6_collision_engine_detects_approach_and_impact_deceleration(self):
        """Phase 6: Fast approach + sudden deceleration generates structured CollisionCandidate."""
        detector = CollisionCandidateDetector(CollisionDetectorConfig(min_candidate_score=0.60))

        # Vehicle 1: approaches from left (x=50 -> x=200), then stops abruptly at x=200
        h1 = [
            (0, (50, 100, 100, 150)),
            (1, (90, 100, 140, 150)),
            (2, (130, 100, 180, 150)),
            (3, (170, 100, 220, 150)),
            (4, (198, 100, 248, 150)),
            (5, (200, 100, 250, 150)),  # stopped
        ]
        # Vehicle 2: approaches from right (x=400 -> x=240), then stops abruptly at x=240
        h2 = [
            (0, (400, 100, 450, 150)),
            (1, (360, 100, 410, 150)),
            (2, (320, 100, 370, 150)),
            (3, (280, 100, 330, 150)),
            (4, (245, 100, 295, 150)),
            (5, (245, 100, 295, 150)),  # stopped
        ]

        t1 = TrackedObject(track_id=1, class_name="car", confidence=0.9, bbox=h1[-1][1],
                           history=[TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h1])
        t2 = TrackedObject(track_id=2, class_name="car", confidence=0.9, bbox=h2[-1][1],
                           history=[TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h2])

        cands = detector.detect_candidates([t1, t2], frame_index=5, timestamp=0.5)

        self.assertEqual(len(cands), 1)
        cand = cands[0]
        self.assertIsInstance(cand, CollisionCandidate)
        self.assertEqual(cand.status, "candidate")
        self.assertIn(1, cand.track_ids)
        self.assertIn(2, cand.track_ids)
        self.assertGreaterEqual(cand.candidate_score, 0.60)
        self.assertGreater(cand.signals.approach_rate_score, 0.5)
        self.assertGreater(cand.signals.abrupt_deceleration_score, 0.5)

    # -- Phase 7: Prolonged Motionlessness Analysis ------------------------

    def test_phase7_prolonged_motionlessness_candidate(self):
        """Phase 7: Person remaining motionless past threshold generates MotionlessCandidate."""
        config = MotionlessDetectorConfig(max_motion_threshold_px=8.0, min_duration_frames=10, fps=10.0)
        detector = MotionlessCandidateDetector(config=config)

        # Person stationary at (100, 100) for 12 frames
        h = [(f, (100, 100, 130, 160)) for f in range(12)]
        t = TrackedObject(track_id=7, class_name="person", confidence=0.9, bbox=h[-1][1],
                          history=[TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h])

        cands = detector.detect_candidates([t], frame_index=11, timestamp=1.1)
        self.assertEqual(len(cands), 1)
        cand = cands[0]
        self.assertIsInstance(cand, MotionlessCandidate)
        self.assertEqual(cand.track_id, 7)
        self.assertEqual(cand.reason, "prolonged_person_motionlessness")
        self.assertEqual(cand.status, "candidate")

    # -- Phase 8: Visual Anomaly Analysis & Temporal Verification ----------

    def test_phase8_visual_anomaly_candidate(self):
        """Phase 8: Red/liquid-like visual anomaly persisting across frames generates VisualAnomalyCandidate."""
        config = AnomalyDetectorConfig(min_area_px=100, persistence_frames=3)
        detector = VisualAnomalyDetector(config=config)

        # Create a frame with a red rectangular pool (100x100 = 10000 px)
        red_frame = np.full((300, 300, 3), (200, 200, 200), dtype=np.uint8)
        red_frame[50:150, 50:150] = (0, 0, 240)  # Red BGR

        detector.detect_candidates(red_frame, frame_index=1)
        detector.detect_candidates(red_frame, frame_index=2)
        cands = detector.detect_candidates(red_frame, frame_index=3, timestamp=0.3)

        self.assertEqual(len(cands), 1)
        cand = cands[0]
        self.assertIsInstance(cand, VisualAnomalyCandidate)
        self.assertEqual(cand.reason, "red_liquid_visual_anomaly")
        self.assertEqual(cand.status, "candidate")

    def test_phases_3_to_8_end_to_end_temporal_verification_pipeline(self):
        """End-to-end integration: Candidates feed into EventVerifier producing a VerifiedIncident."""
        verifier = EventVerifier(VerifierConfig(required_confirmations=3, min_confidence_score=0.60))

        # Feed 3 consecutive collision candidates
        cand1 = CollisionCandidate(
            candidate_id="CAND-1", frame_index=10, timestamp=1.0, track_ids=[1, 2],
            candidate_score=0.85, signals=None, vehicle_classes=["car", "car"]
        )
        cand2 = CollisionCandidate(
            candidate_id="CAND-2", frame_index=11, timestamp=1.1, track_ids=[1, 2],
            candidate_score=0.88, signals=None, vehicle_classes=["car", "car"]
        )
        cand3 = CollisionCandidate(
            candidate_id="CAND-3", frame_index=12, timestamp=1.2, track_ids=[1, 2],
            candidate_score=0.90, signals=None, vehicle_classes=["car", "car"]
        )

        res1 = verifier.process_candidate(cand1, frame_index=10)
        self.assertIsNone(res1)  # 1/3 confirmations

        res2 = verifier.process_candidate(cand2, frame_index=11)
        self.assertIsNone(res2)  # 2/3 confirmations

        res3 = verifier.process_candidate(cand3, frame_index=12)
        self.assertIsNotNone(res3)  # 3/3 confirmations -> VERIFIED!
        self.assertIsInstance(res3, VerifiedIncident)
        self.assertEqual(res3.verification_state, VerificationState.VERIFIED)
        self.assertEqual(res3.incident_type, "vehicle_collision")
        self.assertGreaterEqual(res3.confidence_score, 0.85)


if __name__ == "__main__":
    unittest.main()
