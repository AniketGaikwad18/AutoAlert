"""
End-to-End and Integration tests for AutoAlert CCTV Video Simulation Mode (Stage 21 Enhancement).

Validates:
  1. Camera selection and metadata lookup.
  2. Camera location resolution from registry (no video GPS fabrication).
  3. Video ingestion from local/uploaded video file.
  4. Video-to-camera association and incident location assignment.
  5. AI detection, tracking, collision event candidate, and verification flow.
  6. Facility distance calculation via Haversine.
  7. Nearby emergency facility categorization and sorting (ambulance, police, hospital).
  8. Missing/invalid camera rejection handling.
  9. Missing location coordinates handling.
  10. Simulated notification creation and lifecycle state management.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import cv2
import numpy as np

from backend.repository import repository
from backend.schemas.camera import CameraSchema
from backend.schemas.facility import FacilitySchema
from src.core.incident import IncidentPackage
from src.location.camera_registry import CameraRegistry
from src.simulation.controller import CCTVSimulationService, SimulationProgressStep, SimulationResult


def create_synthetic_collision_video(filepath: str, num_frames: int = 30, fps: float = 10.0) -> str:
    """Helper to generate a synthetic video with converging vehicle blocks."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for i in range(num_frames):
        img = np.full((height, width, 3), (30, 30, 30), dtype=np.uint8)

        # Draw road
        cv2.rectangle(img, (0, 200), (640, 380), (60, 60, 60), -1)

        # Vehicle 1 moving right
        x1 = min(280, int(40 + i * 12))
        # Vehicle 2 moving left
        x2 = max(310, int(520 - i * 12))

        cv2.rectangle(img, (x1, 240), (x1 + 60, 300), (0, 0, 220), -1)
        cv2.rectangle(img, (x2, 240), (x2 + 60, 300), (220, 0, 0), -1)

        writer.write(img)

    writer.release()
    return filepath


def create_synthetic_normal_video(filepath: str, num_frames: int = 20, fps: float = 10.0) -> str:
    """Helper to generate a normal video with no collision."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for i in range(num_frames):
        img = np.full((height, width, 3), (30, 30, 30), dtype=np.uint8)
        # Empty static scene
        cv2.rectangle(img, (0, 200), (640, 380), (60, 60, 60), -1)
        writer.write(img)

    writer.release()
    return filepath


class TestCCTVSimulationMode(unittest.TestCase):
    """Integration test suite for CCTV Video Simulation service and workflows."""

    def setUp(self):
        repository.reset()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_dir = os.path.join(self.temp_dir.name, "evidence")
        self.video_collision = os.path.join(self.temp_dir.name, "collision.mp4")
        self.video_normal = os.path.join(self.temp_dir.name, "normal.mp4")

        create_synthetic_collision_video(self.video_collision, num_frames=30, fps=10.0)
        create_synthetic_normal_video(self.video_normal, num_frames=20, fps=10.0)

        # Configure custom CameraRegistry with test cameras
        self.registry = CameraRegistry()
        self.registry.register_camera(
            CameraSchema(
                camera_id="CAM-DEMO-01",
                name="Camera 1 — Main Junction",
                location_name="Demo Location A — North Arterial Intersection",
                latitude=18.5204,
                longitude=73.8567,
                zone_id="ZONE-NORTH-A",
                status="active",
                enabled=True,
            )
        )
        self.registry.register_camera(
            CameraSchema(
                camera_id="CAM-NO-GPS",
                name="Camera Without GPS",
                location_name="Basement Parking",
                latitude=None,
                longitude=None,
                zone_id="ZONE-BASEMENT",
                status="active",
                enabled=True,
            )
        )

        # Register simulated facilities
        repository.add_facility(
            FacilitySchema(
                facility_id="EMS-SIM-01",
                name="Paramedic Ambulance Unit 1 (Simulated)",
                type="ambulance",
                phone_contact="555-0111",
                latitude=18.5220,
                longitude=73.8580,
                available=True,
                is_simulated=True,
            )
        )
        repository.add_facility(
            FacilitySchema(
                facility_id="POLICE-SIM-01",
                name="Traffic Police Precinct 1 (Simulated)",
                type="police",
                phone_contact="555-0122",
                latitude=18.5280,
                longitude=73.8510,
                available=True,
                is_simulated=True,
            )
        )
        repository.add_facility(
            FacilitySchema(
                facility_id="HOSP-SIM-01",
                name="Emergency Hospital 1 (Simulated)",
                type="hospital",
                phone_contact="555-0133",
                latitude=18.5190,
                longitude=73.8610,
                available=True,
                is_simulated=True,
            )
        )

        self.service = CCTVSimulationService(
            registry=self.registry,
            output_dir=self.evidence_dir,
            max_analysis_frames=50,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_simulation_flow_verified_incident(self):
        """Test full simulation execution with a collision video, camera binding, and facility matching."""
        progress_steps = []

        def on_step(step: SimulationProgressStep):
            progress_steps.append(step)

        result: SimulationResult = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-DEMO-01",
            progress_callback=on_step,
        )

        # 1. Overall Success & Verification
        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertIsNotNone(result.incident)
        self.assertGreater(len(progress_steps), 0)

        # 2. Camera Association & Provenance
        self.assertEqual(result.camera.camera_id, "CAM-DEMO-01")
        self.assertEqual(result.incident.camera_id, "CAM-DEMO-01")
        self.assertIsNotNone(result.location)
        self.assertEqual(result.location.name, "Demo Location A — North Arterial Intersection")
        self.assertEqual(result.location.latitude, 18.5204)
        self.assertEqual(result.location.longitude, 73.8567)

        # Invariant check: Incident location came from camera registry
        self.assertEqual(result.incident.location.latitude, 18.5204)
        self.assertEqual(result.incident.location.longitude, 73.8567)

        # 3. Incident Package in Database
        persisted = repository.get_incident(result.incident.incident_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.incident_id, result.incident.incident_id)
        self.assertEqual(persisted.camera_id, "CAM-DEMO-01")

        # 4. Nearby Facilities Grouping & Haversine Distance
        facs = result.nearby_facilities
        self.assertIn("ambulance", facs)
        self.assertIn("police", facs)
        self.assertIn("hospital", facs)
        self.assertGreaterEqual(len(facs["ambulance"]), 1)
        self.assertGreaterEqual(len(facs["police"]), 1)
        self.assertGreaterEqual(len(facs["hospital"]), 1)

        # Verify Haversine distance is calculated
        nearest_amb = facs["ambulance"][0]
        self.assertIsNotNone(nearest_amb["distance_km"])
        self.assertGreater(nearest_amb["distance_km"], 0.0)

        # 5. Simulated Notification
        notif = result.simulated_notification
        self.assertIsNotNone(notif)
        self.assertEqual(notif["status"], "notified")
        self.assertTrue(notif["is_simulated"])
        self.assertEqual(notif["incident_id"], result.incident.incident_id)

    def test_missing_camera_id_handling(self):
        """Verify simulation rejects non-existent camera ID gracefully."""
        result = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-NON-EXISTENT",
        )
        self.assertFalse(result.success)
        self.assertIn("not registered", result.error_message)

    def test_missing_location_coordinates_handling(self):
        """Verify simulation with camera lacking GPS operates safely and returns distance_km as None."""
        result = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-NO-GPS",
        )
        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertIsNone(result.location.latitude)
        self.assertIsNone(result.location.longitude)

        # Facilities should be returned with distance_km = None
        facs = result.nearby_facilities.get("all", [])
        if facs:
            self.assertIsNone(facs[0].get("distance_km"))

    def test_non_event_video_handling(self):
        """Verify simulation on normal footage correctly reports no verified incident."""
        result = self.service.run_simulation(
            video_path=self.video_normal,
            camera_id="CAM-DEMO-01",
        )
        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertIsNone(result.incident)
        self.assertEqual(result.detected_events_count, 0)

    def test_simulated_notification_lifecycle(self):
        """Verify state transitions for simulated notifications created during simulation."""
        result = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-DEMO-01",
        )
        self.assertTrue(result.success)
        notif_id = result.simulated_notification["notification_id"]

        # Advance status: notified -> acknowledged -> responding
        updated_ack = repository.update_notification_status(notif_id, "acknowledged", reason="Operator reviewed")
        self.assertIsNotNone(updated_ack)
        self.assertEqual(updated_ack.status, "acknowledged")

        updated_resp = repository.update_notification_status(notif_id, "responding", reason="Unit en route")
        self.assertIsNotNone(updated_resp)
        self.assertEqual(updated_resp.status, "responding")


if __name__ == "__main__":
    unittest.main()
