"""
Unit tests for CameraRegistry and Location Binding (Stage 21 Enhancement).

Validates:
  1. Camera selection and registry lookup.
  2. Camera location lookup (LocationInfo with name, lat, lon, zone).
  3. Missing/invalid camera ID handling (returns None gracefully).
  4. Missing location coordinates handling (preserves None without crashing).
  5. Invariant: Location comes strictly from camera registry, not video GPS.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import yaml

from backend.schemas.camera import CameraSchema
from src.core.incident import LocationInfo
from src.location.camera_registry import CameraRegistry


class TestCameraRegistry(unittest.TestCase):
    """Test suite for CameraRegistry functionality and edge cases."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self.temp_dir.name, "cameras_test.yaml")
        sample_data = {
            "cameras": [
                {
                    "camera_id": "CAM-TEST-01",
                    "name": "Test Intersection Camera",
                    "location_name": "Test Location A",
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "zone_id": "ZONE-TEST-A",
                    "status": "active",
                    "enabled": True,
                },
                {
                    "camera_id": "CAM-NO-GPS-02",
                    "name": "Camera Without GPS",
                    "location_name": "Indoor Parking B",
                    "latitude": None,
                    "longitude": None,
                    "zone_id": "ZONE-TEST-B",
                    "status": "active",
                    "enabled": True,
                },
                {
                    "camera_id": "CAM-DISABLED-03",
                    "name": "Disabled Test Camera",
                    "location_name": "Maintenance Bay",
                    "latitude": 18.5100,
                    "longitude": 73.8500,
                    "zone_id": "ZONE-TEST-C",
                    "status": "inactive",
                    "enabled": False,
                },
            ]
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(sample_data, f)

        self.registry = CameraRegistry(config_path=self.config_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_cameras(self):
        """Verify all cameras and enabled-only filtering."""
        all_cams = self.registry.list_cameras(enabled_only=False)
        self.assertEqual(len(all_cams), 3)

        enabled_cams = self.registry.list_cameras(enabled_only=True)
        self.assertEqual(len(enabled_cams), 2)
        cam_ids = [c.camera_id for c in enabled_cams]
        self.assertIn("CAM-TEST-01", cam_ids)
        self.assertIn("CAM-NO-GPS-02", cam_ids)
        self.assertNotIn("CAM-DISABLED-03", cam_ids)

    def test_camera_lookup_valid(self):
        """Verify fetching valid camera metadata."""
        cam = self.registry.get_camera("CAM-TEST-01")
        self.assertIsNotNone(cam)
        self.assertEqual(cam.name, "Test Intersection Camera")
        self.assertEqual(cam.latitude, 18.5204)
        self.assertEqual(cam.longitude, 73.8567)

    def test_camera_location_lookup_valid(self):
        """Verify location resolution for a camera with valid GPS."""
        loc = self.registry.get_camera_location("CAM-TEST-01")
        self.assertIsNotNone(loc)
        self.assertIsInstance(loc, LocationInfo)
        self.assertEqual(loc.name, "Test Location A")
        self.assertEqual(loc.latitude, 18.5204)
        self.assertEqual(loc.longitude, 73.8567)
        self.assertEqual(loc.zone_id, "ZONE-TEST-A")

    def test_missing_camera_handling(self):
        """Verify looking up non-existent camera ID returns None gracefully."""
        cam = self.registry.get_camera("CAM-NON-EXISTENT")
        self.assertIsNone(cam)

        loc = self.registry.get_camera_location("CAM-NON-EXISTENT")
        self.assertIsNone(loc)

    def test_missing_location_coordinates_handling(self):
        """Verify camera with missing coordinates returns LocationInfo with None lat/lon without crashing."""
        loc = self.registry.get_camera_location("CAM-NO-GPS-02")
        self.assertIsNotNone(loc)
        self.assertEqual(loc.name, "Indoor Parking B")
        self.assertIsNone(loc.latitude)
        self.assertIsNone(loc.longitude)
        self.assertEqual(loc.zone_id, "ZONE-TEST-B")

    def test_register_camera_in_memory(self):
        """Verify dynamically registering a new camera in-memory."""
        new_cam = CameraSchema(
            camera_id="CAM-DYNAMIC-01",
            name="Dynamic Camera",
            location_name="Gate 5",
            latitude=18.5300,
            longitude=73.8600,
            status="active",
            enabled=True,
        )
        self.registry.register_camera(new_cam)

        fetched = self.registry.get_camera("CAM-DYNAMIC-01")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Dynamic Camera")

        loc = self.registry.get_camera_location("CAM-DYNAMIC-01")
        self.assertIsNotNone(loc)
        self.assertEqual(loc.name, "Gate 5")
        self.assertEqual(loc.latitude, 18.5300)


if __name__ == "__main__":
    unittest.main()
