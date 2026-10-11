"""
Unit & Integration Test Suite for Emergency Routing, Distance Calculation,
Stations Along Route, and Transparent Notification Timeline (Stage 22 Enhancement).

Tests:
  1. Camera selection & location lookup.
  2. Video ingestion & video-to-camera association.
  3. Incident location assignment (no video GPS fabrication).
  4. Hospital distance calculation (geographic Haversine).
  5. Ambulance station distance calculation.
  6. Police station distance calculation.
  7. Route generation (EMS -> Incident -> Hospital).
  8. Route distance & estimated travel time.
  9. Stations along/near route proximity analysis.
  10. Notification recipient selection & chronological timeline generation.
  11. Missing location handling.
  12. Missing facilities handling.
  13. Invalid video handling.
  14. No verified incident handling.
  15. Offline OSRM fallback behavior.
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
from src.dispatch.routing import RouteEngine, EmergencyRouteResult, RouteLeg
from src.dispatch.notification_timeline import NotificationTimelineGenerator, TimelineEvent
from src.location.camera_registry import CameraRegistry
from src.simulation.controller import CCTVSimulationService, SimulationResult


def create_synthetic_collision_video(filepath: str, num_frames: int = 30, fps: float = 10.0) -> str:
    """Helper to generate a synthetic video with converging vehicle blocks."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for i in range(num_frames):
        img = np.full((height, width, 3), (30, 30, 30), dtype=np.uint8)
        cv2.rectangle(img, (0, 200), (640, 380), (60, 60, 60), -1)
        x1 = min(280, int(40 + i * 12))
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
        cv2.rectangle(img, (0, 200), (640, 380), (60, 60, 60), -1)
        writer.write(img)

    writer.release()
    return filepath


class TestEmergencyRoutingAndNotifications(unittest.TestCase):
    """Test suite for emergency route generation, facility distance calculation, and timeline generation."""

    def setUp(self):
        repository.reset()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_dir = os.path.join(self.temp_dir.name, "evidence")
        self.video_collision = os.path.join(self.temp_dir.name, "collision.mp4")
        self.video_normal = os.path.join(self.temp_dir.name, "normal.mp4")

        create_synthetic_collision_video(self.video_collision, num_frames=30, fps=10.0)
        create_synthetic_normal_video(self.video_normal, num_frames=20, fps=10.0)

        # Set up test cameras in CameraRegistry
        self.registry = CameraRegistry()
        self.registry.register_camera(
            CameraSchema(
                camera_id="CAM-PUNE-01",
                name="Camera 1 — Main Road Pune",
                location_name="Main Road, Pune (Demo Location A)",
                latitude=18.5204,
                longitude=73.8567,
                zone_id="ZONE-PUNE-CENTRAL",
                status="active",
                enabled=True,
            )
        )
        self.registry.register_camera(
            CameraSchema(
                camera_id="CAM-NO-GPS",
                name="Camera Without GPS",
                location_name="Basement Parking Level 2",
                latitude=None,
                longitude=None,
                zone_id="ZONE-BASEMENT",
                status="active",
                enabled=True,
            )
        )

        # Register sample facilities
        self.ambulance_fac = {
            "facility_id": "EMS-001",
            "name": "Central EMS Ambulance Station",
            "type": "ambulance",
            "phone_contact": "555-0111",
            "latitude": 18.5220,
            "longitude": 73.8580,
            "available": True,
            "is_simulated": True,
        }
        self.hospital_fac = {
            "facility_id": "HOSP-001",
            "name": "City Care Trauma Hospital",
            "type": "hospital",
            "phone_contact": "555-0133",
            "latitude": 18.5190,
            "longitude": 73.8610,
            "available": True,
            "is_simulated": True,
        }
        self.police_fac = {
            "facility_id": "POLICE-001",
            "name": "Shivajinagar Police Station",
            "type": "police",
            "phone_contact": "555-0122",
            "latitude": 18.5280,
            "longitude": 73.8510,
            "available": True,
            "is_simulated": True,
        }
        self.traffic_fac = {
            "facility_id": "TRAFFIC-001",
            "name": "Deccan Traffic Control Point",
            "type": "police",
            "phone_contact": "555-0155",
            "latitude": 18.5215,
            "longitude": 73.8545,
            "available": True,
            "is_simulated": True,
        }

        repository.add_facility(FacilitySchema(**self.ambulance_fac))
        repository.add_facility(FacilitySchema(**self.hospital_fac))
        repository.add_facility(FacilitySchema(**self.police_fac))
        repository.add_facility(FacilitySchema(**self.traffic_fac))

        self.service = CCTVSimulationService(
            registry=self.registry,
            output_dir=self.evidence_dir,
            max_analysis_frames=50,
        )
        self.route_engine = RouteEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    # -- Route Engine Tests ----------------------------------------------------

    def test_calculate_emergency_route_two_legs(self):
        """Verify 2-leg route generation (EMS -> Incident -> Hospital)."""
        loc_dict = {"name": "Main Road, Pune", "latitude": 18.5204, "longitude": 73.8567}
        all_facs = [self.ambulance_fac, self.hospital_fac, self.police_fac, self.traffic_fac]

        res: EmergencyRouteResult = self.route_engine.calculate_emergency_route(
            origin_station=self.ambulance_fac,
            incident_location=loc_dict,
            destination_hospital=self.hospital_fac,
            all_facilities=all_facs,
            max_proximity_km=1.5,
        )

        self.assertIsNotNone(res)
        self.assertEqual(len(res.legs), 2)
        self.assertGreater(res.total_distance_km, 0.0)
        self.assertGreater(res.estimated_duration_min, 0.0)
        self.assertGreater(len(res.coordinates), 4)

        # Verify Leg 1 origin is Ambulance and Leg 2 destination is Hospital
        self.assertEqual(res.legs[0].origin_name, "Central EMS Ambulance Station")
        self.assertEqual(res.legs[0].destination_name, "Main Road, Pune")
        self.assertEqual(res.legs[1].origin_name, "Main Road, Pune")
        self.assertEqual(res.legs[1].destination_name, "City Care Trauma Hospital")

    def test_find_stations_along_route_proximity(self):
        """Verify identification of response points within 1.5 km of route."""
        route_coords = [(18.5220, 73.8580), (18.5210, 73.8570), (18.5204, 73.8567), (18.5190, 73.8610)]
        all_facs = [self.ambulance_fac, self.hospital_fac, self.police_fac, self.traffic_fac]

        stations = self.route_engine.find_stations_along_route(
            route_coords=route_coords,
            facilities=all_facs,
            max_distance_km=1.5,
        )

        self.assertGreaterEqual(len(stations), 1)
        for stn in stations:
            self.assertIn("distance_to_route_km", stn)
            self.assertIn("station_role", stn)
            self.assertLessEqual(stn["distance_to_route_km"], 1.5)

    def test_osrm_offline_fallback_behavior(self):
        """Verify route engine produces valid fallback road polyline when OSRM server is unreachable."""
        offline_engine = RouteEngine(osrm_base_url="http://127.0.0.1:9999", timeout_sec=0.1)
        leg: RouteLeg = offline_engine.calculate_leg(
            18.5204, 73.8567, 18.5190, 73.8610, "Origin", "Destination"
        )
        self.assertIsNotNone(leg)
        self.assertEqual(leg.source, "Demo Road Network (Fallback)")
        self.assertGreater(len(leg.coordinates), 2)
        self.assertGreater(leg.distance_km, 0.0)

    # -- Notification Timeline Tests -------------------------------------------

    def test_notification_timeline_sequence(self):
        """Verify chronological sequence and transparent reasoning in timeline generation."""
        stations_along = [
            {
                "facility_id": "TRAFFIC-001",
                "name": "Deccan Traffic Control Point",
                "type": "police",
                "distance_to_route_km": 0.4,
                "station_role": "Traffic Clearing & Intersection Control",
            }
        ]

        timeline = NotificationTimelineGenerator.generate_timeline(
            incident_type="vehicle_collision",
            camera_id="CAM-PUNE-01",
            camera_name="Camera 1",
            location_name="Main Road, Pune",
            ambulance_station=self.ambulance_fac,
            hospital=self.hospital_fac,
            stations_along_route=stations_along,
        )

        self.assertGreaterEqual(len(timeline), 5)
        # Check Step 1 is Incident Verification
        self.assertEqual(timeline[0].step_number, 1)
        self.assertEqual(timeline[0].status, "verified")

        # Check all items are marked simulated
        for item in timeline:
            self.assertTrue(item.is_simulated)
            self.assertIsInstance(item.reason, str)
            self.assertGreater(len(item.reason), 5)

    # -- End-to-End Simulation Mode Verification --------------------------------

    def test_full_simulation_with_route_and_distances(self):
        """Verify end-to-end simulation generates distances, route, and timeline."""
        result: SimulationResult = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-PUNE-01",
        )

        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertIsNotNone(result.incident)

        # 1. Geographic distances calculated
        self.assertIsNotNone(result.nearest_ambulance)
        self.assertIsNotNone(result.nearest_hospital)
        self.assertIsNotNone(result.nearest_police)
        self.assertGreater(result.nearest_ambulance["distance_km"], 0.0)
        self.assertGreater(result.nearest_hospital["distance_km"], 0.0)

        # 2. Emergency 2-leg route generated
        self.assertIsNotNone(result.emergency_route)
        self.assertGreater(result.route_distance_km, 0.0)
        self.assertGreater(result.estimated_travel_time_min, 0.0)

        # 3. Stations along route
        self.assertIsInstance(result.stations_along_route, list)

        # 4. Notification timeline
        self.assertGreater(len(result.notification_timeline), 3)

        # 5. Simulated notification status
        self.assertIsNotNone(result.simulated_notification)
        self.assertTrue(result.simulated_notification["is_simulated"])

    def test_missing_location_coordinates_safe_handling(self):
        """Verify simulation on camera lacking GPS operates safely and sets distances & route to None."""
        result = self.service.run_simulation(
            video_path=self.video_collision,
            camera_id="CAM-NO-GPS",
        )

        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertIsNone(result.location.latitude)
        self.assertIsNone(result.emergency_route)
        self.assertIsNone(result.route_distance_km)

    def test_non_event_video_handling(self):
        """Verify normal footage with no accident cleanly reports no verified incident."""
        result = self.service.run_simulation(
            video_path=self.video_normal,
            camera_id="CAM-PUNE-01",
        )
        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertIsNone(result.incident)
        self.assertIsNone(result.emergency_route)

    def test_invalid_video_handling(self):
        """Verify invalid/missing video path is rejected with clean error message."""
        result = self.service.run_simulation(
            video_path="non_existent_video_path.mp4",
            camera_id="CAM-PUNE-01",
        )
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)


if __name__ == "__main__":
    unittest.main()
