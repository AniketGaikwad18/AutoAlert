"""
Unit tests for Stage 16 Streamlit Command Center Dashboard components and API client.
"""

from __future__ import annotations

import unittest
from backend.repository import repository
from backend.schemas.incident import IncidentPackageCreateSchema, LocationSchema, PlateReadingSchema
from dashboard.api_client import DashboardAPIClient
from dashboard.components.incident_card import format_timestamp


class TestDashboardComponents(unittest.TestCase):
    """Test suite for dashboard API client and component logic."""

    def setUp(self):
        repository.reset()
        self.client = DashboardAPIClient()

    def test_timestamp_formatting(self):
        """Verify format_timestamp outputs expected UTC string or fallback."""
        formatted = format_timestamp(1700000000.0)
        self.assertIn("2023", formatted)
        self.assertIn("UTC", formatted)

        self.assertEqual(format_timestamp(None), "Unknown timestamp")

    def test_api_client_repository_fallback(self):
        """Verify API client correctly falls back to local repository when API server is offline."""
        inc_data = IncidentPackageCreateSchema(
            incident_id="INC-DASHBOARD-001",
            incident_type="vehicle_collision",
            camera_id="CAM-MAIN-01",
            timestamp=12345.0,
            verification_status="verified",
            confidence_score=0.91,
            created_at="2026-09-17T12:00:00Z",
            location=LocationSchema(latitude=18.5204, longitude=73.8567, name="Main Square"),
            plate_readings=[
                PlateReadingSchema(
                    track_id=1,
                    plate_number="MH12CD5678",
                    confidence=0.95,
                    format_validated=True,
                    status="verified_reading",
                )
            ],
        )
        repository.add_incident(inc_data)

        # Retrieve list via client fallback
        incidents = self.client.list_incidents()
        self.assertGreaterEqual(len(incidents), 1)
        self.assertTrue(any(i["incident_id"] == "INC-DASHBOARD-001" for i in incidents))

        # Retrieve single incident details
        single_inc = self.client.get_incident("INC-DASHBOARD-001")
        self.assertIsNotNone(single_inc)
        self.assertEqual(single_inc["incident_id"], "INC-DASHBOARD-001")
        self.assertEqual(single_inc["confidence_score"], 0.91)
        self.assertEqual(len(single_inc["plate_readings"]), 1)
        self.assertEqual(single_inc["plate_readings"][0]["plate_number"], "MH12CD5678")

    def test_api_client_list_cameras_and_facilities(self):
        """Verify client returns seeded cameras and simulated facilities."""
        cameras = self.client.list_cameras()
        self.assertGreaterEqual(len(cameras), 1)
        self.assertTrue(any(c["camera_id"] == "CAM-MAIN-01" for c in cameras))

        facilities = self.client.list_facilities()
        self.assertGreaterEqual(len(facilities), 1)
        self.assertTrue(facilities[0]["is_simulated"])


if __name__ == "__main__":
    unittest.main()
