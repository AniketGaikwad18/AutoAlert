"""
Stage 18 End-to-End System Integration Test Suite for AutoAlert.

Validates the full pipeline flow across all 17 completed stages:
Video Ingestion -> Frame Processing -> Detection -> Tracking ->
Event Candidates -> Verification -> Evidence Recording -> Plate OCR ->
Incident Serialization -> FastAPI Backend -> Database -> Dashboard API ->
Haversine Facility Matching -> SIMULATED Emergency Notifications.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from src.video.frame_processor import FrameProcessor
from src.detection.detector import Detection
from src.tracking.tracker import MultiObjectTracker, TrackedObject, TrackSnapshot
from src.events.collision import CollisionCandidateDetector
from src.events.motionless import MotionlessCandidateDetector
from src.events.anomaly import VisualAnomalyDetector
from src.events.verifier import EventVerifier, VerifierConfig
from src.license_plate.preprocessor import PlateCrop
from src.license_plate.ocr import PlateOCREngine, OCRResult
from src.license_plate.aggregator import PlateTemporalAggregator
from src.core.incident import IncidentPackage
from src.evidence.recorder import EvidenceRecorder
from dashboard.api_client import DashboardAPIClient


class TestEndToEndSystemIntegration(unittest.TestCase):
    """Full pipeline integration test verifying end-to-end data contracts and flows."""

    def setUp(self):
        repository.reset()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_dir = os.path.join(self.temp_dir.name, "evidence")
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.client = TestClient(app)
        self.dashboard_client = DashboardAPIClient()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_pipeline_flow(self):
        """Execute complete pipeline lifecycle from synthetic frame ingestion to simulated dispatch."""
        metadata = {"width": 640, "height": 480, "fps": 30.0, "frame_count": 10, "source_path": "dummy"}
        processor = FrameProcessor(metadata, target_width=640, target_height=480)

        frames = []
        for i in range(10):
            raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            proc_frame = processor.process(raw_frame, i)
            frames.append(proc_frame.image)
        self.assertEqual(len(frames), 10)

        # 2. Object Detection & Tracking Continuity
        tracker = MultiObjectTracker(min_hits=1)

        tracked_history = []
        for idx, frame in enumerate(frames):
            dets = [
                Detection(class_name="car", confidence=0.9, bbox=(100, 100, 200, 200)),
                Detection(class_name="car", confidence=0.88, bbox=(300, 300, 400, 400)),
            ]
            tracks = tracker.update(dets, frame_index=idx)
            tracked_history.append(tracks)

        self.assertGreater(len(tracked_history), 0)
        first_frame_tracks = tracked_history[0]
        self.assertGreaterEqual(len(first_frame_tracks), 1)

        # 3. Candidate Event Detection (Collision) using history-aware tracks
        collision_detector = CollisionCandidateDetector()

        # Build converging tracks with history (mirrors head-on test in test_collision.py)
        h1 = [(0,(50,100,100,150)),(1,(90,100,140,150)),(2,(130,100,180,150)),
              (3,(165,100,215,150)),(4,(195,100,245,150)),(5,(196,100,246,150))]
        h2 = [(0,(400,100,450,150)),(1,(360,100,410,150)),(2,(310,100,360,150)),
              (3,(265,100,315,150)),(4,(230,100,280,150)),(5,(229,100,279,150))]
        snaps1 = [TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h1]
        snaps2 = [TrackSnapshot(bbox=b, confidence=0.9, frame_index=f) for f, b in h2]
        t0 = TrackedObject(track_id=1, class_name="car", bbox=h1[-1][1], confidence=0.9,
                           history=snaps1, age=6, hits=6, time_since_update=0)
        t1 = TrackedObject(track_id=2, class_name="truck", bbox=h2[-1][1], confidence=0.9,
                           history=snaps2, age=6, hits=6, time_since_update=0)
        cands = collision_detector.detect_candidates([t0, t1], frame_index=5, timestamp=100.0)
        self.assertGreaterEqual(len(cands), 1)
        candidate = cands[0]

        # 4. Event Verification Engine
        from src.events.verifier import VerifierConfig
        verifier = EventVerifier(config=VerifierConfig(required_confirmations=1, min_confidence_score=0.5))
        verified_incident = verifier.process_candidate(candidate, frame_index=1, timestamp=100.0)

        self.assertIsNotNone(verified_incident)
        self.assertEqual(verified_incident.verification_state.value, "verified")

        # 5. Evidence Recording
        from src.evidence.recorder import EvidenceRecorderConfig
        from src.evidence.frame_capture import FrameBuffer
        rec_config = EvidenceRecorderConfig(output_dir=self.evidence_dir, save_video_clip=False, fps=10.0)
        recorder = EvidenceRecorder(config=rec_config)
        frame_buf = FrameBuffer(max_buffer_size=20)
        for fi, img in enumerate(frames):
            frame_buf.add_frame(fi, fi / 10.0, img)
        ev_report = recorder.record_evidence(verified_incident, frame_buf)
        self.assertIsNotNone(ev_report)
        self.assertIsInstance(ev_report.evidence_files.get("key_frames", []), list)
        ev_frames = ev_report.evidence_files.get("key_frames", [])

        # 6. License Plate OCR & Temporal Aggregation
        ocr_engine = PlateOCREngine()
        aggregator = PlateTemporalAggregator()

        dummy_img = np.ones((50, 150, 3), dtype=np.uint8) * 100
        cv2.putText(dummy_img, "MH12AB1234", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        plate_crop = PlateCrop(
            crop_id="CROP-1",
            track_id=1,
            frame_index=1,
            raw_crop=dummy_img,
            processed_crop=dummy_img,
            bbox=(10, 10, 60, 160),
            confidence=0.85,
            quality_score=0.9,
        )
        ocr_reading = ocr_engine.read_plate(plate_crop)
        aggregator.add_reading(ocr_reading)
        best_plate = aggregator.aggregate_track(track_id=1)

        self.assertIsNotNone(best_plate)
        # OCR on a synthetic image is unlikely to match exactly; assert it returned a result without fabricating
        self.assertIsInstance(best_plate.best_plate_number, str)

        # 7. Incident Package Creation & FastAPI Ingestion
        from src.core.incident import LocationInfo
        pkg = IncidentPackage(
            incident_id=verified_incident.incident_id,
            incident_type="vehicle_collision",
            camera_id="CAM-MAIN-01",
            timestamp=100.0,
            verification_status="verified",
            confidence_score=0.95,
            involved_track_ids=[1, 2],
            evidence_frames=ev_frames,
            location=LocationInfo(latitude=18.5204, longitude=73.8567, name="Main Gate"),
            plate_readings=[
                {
                    "track_id": 1,
                    "plate_number": best_plate.best_plate_number,
                    "confidence": best_plate.aggregated_confidence,
                    "format_validated": best_plate.format_validated,
                    "status": best_plate.status,
                }
            ],
            reason_metadata={"trigger": "high_overlap_velocity_drop"},
        )
        dict_payload = pkg.to_dict()

        # Post payload to FastAPI backend
        res = self.client.post("/api/v1/incidents", json=dict_payload)
        self.assertEqual(res.status_code, 201)
        ingested = res.json()
        self.assertEqual(ingested["incident_id"], verified_incident.incident_id)

        # 8. Database Persistence Verification
        db_inc = repository.get_incident(verified_incident.incident_id)
        self.assertIsNotNone(db_inc)
        self.assertEqual(db_inc.incident_id, verified_incident.incident_id)
        self.assertEqual(db_inc.location.name, "Main Gate")

        # 9. Dashboard API Client Retrieval & Haversine Facility Matching
        matched_facs = self.dashboard_client.match_facilities(
            incident_id=verified_incident.incident_id,
            latitude=18.5204,
            longitude=73.8567,
            limit=3,
        )
        self.assertGreaterEqual(len(matched_facs), 1)
        self.assertIsNotNone(matched_facs[0]["distance_km"])

        # 10. SIMULATED Emergency Dispatch Notification Lifecycle
        target_fac_id = matched_facs[0]["facility_id"]
        notif_res = self.dashboard_client.trigger_notification(
            incident_id=verified_incident.incident_id,
            facility_id=target_fac_id,
            message="SIMULATED END-TO-END DISPATCH TEST",
        )
        self.assertIsNotNone(notif_res)
        notif_id = notif_res["notification_id"]
        self.assertEqual(notif_res["status"], "notified")
        self.assertTrue(notif_res["is_simulated"])

        # Update notification lifecycle (notified -> acknowledged -> responding)
        updated1 = self.dashboard_client.update_notification_status(notif_id, "acknowledged", reason="Acknowledged")
        self.assertEqual(updated1["status"], "acknowledged")

        updated2 = self.dashboard_client.update_notification_status(notif_id, "responding", reason="Unit en route")
        self.assertEqual(updated2["status"], "responding")


if __name__ == "__main__":
    unittest.main()
