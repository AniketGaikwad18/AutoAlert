"""
Unit and API integration tests for Stage 17 Facility Matching and SIMULATED Notifications.
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from backend.schemas.incident import IncidentPackageCreateSchema, LocationSchema
from src.dispatch.matching import haversine_distance, FacilityMatcher
from src.dispatch.notification import SimulatedNotification


class TestDispatchAndNotification(unittest.TestCase):
    """Test suite for Haversine distance, facility matching, and notification state transitions."""

    def setUp(self):
        repository.reset()
        self.client = TestClient(app)

    def test_haversine_distance(self):
        """Verify Haversine distance formula accuracy."""
        # Distance between Pune Railway Station (18.5284, 73.8742) and Shaniwar Wada (18.5196, 73.8553)
        dist = haversine_distance(18.5284, 73.8742, 18.5196, 73.8553)
        self.assertGreater(dist, 1.5)
        self.assertLess(dist, 3.0)

        # Same location distance is 0.0
        same_dist = haversine_distance(18.5204, 73.8567, 18.5204, 73.8567)
        self.assertEqual(same_dist, 0.0)

    def test_facility_matcher_ranking(self):
        """Verify FacilityMatcher ranks facilities by Haversine distance."""
        facilities = [
            {"facility_id": "F1", "name": "Far Hospital", "type": "hospital", "latitude": 18.6000, "longitude": 73.9000},
            {"facility_id": "F2", "name": "Near Hospital", "type": "hospital", "latitude": 18.5210, "longitude": 73.8570},
            {"facility_id": "F3", "name": "Police Station", "type": "police", "latitude": 18.5250, "longitude": 73.8590},
        ]
        # Incident at (18.5204, 73.8567)
        matched = FacilityMatcher.match_facilities(
            incident_lat=18.5204,
            incident_lon=73.8567,
            facilities=facilities,
            facility_type="hospital",
            limit=5,
        )

        self.assertEqual(len(matched), 2)
        self.assertEqual(matched[0]["facility_id"], "F2")
        self.assertLess(matched[0]["distance_km"], matched[1]["distance_km"])

    def test_facility_matcher_missing_coords(self):
        """Verify FacilityMatcher handles missing/None coordinates gracefully."""
        facilities = [
            {"facility_id": "F1", "name": "Hospital", "type": "hospital", "latitude": 18.5204, "longitude": 73.8567},
        ]
        matched = FacilityMatcher.match_facilities(
            incident_lat=None,
            incident_lon=None,
            facilities=facilities,
        )
        self.assertEqual(len(matched), 1)
        self.assertIsNone(matched[0]["distance_km"])

    def test_simulated_notification_lifecycle(self):
        """Verify notification state machine transitions (pending -> notified -> acknowledged -> responding)."""
        notif = SimulatedNotification(
            incident_id="INC-DISPATCH-01",
            facility_id="FAC-HOSPITAL-01",
            facility_type="hospital",
            facility_name="City Central Emergency Hospital",
        )
        self.assertEqual(notif.status, "pending")
        self.assertTrue(notif.is_simulated)

        # pending -> notified
        res1 = notif.transition_to("notified", reason="Dispatch triggered")
        self.assertTrue(res1)
        self.assertEqual(notif.status, "notified")

        # notified -> acknowledged
        res2 = notif.transition_to("acknowledged", reason="Acknowledged by operator")
        self.assertTrue(res2)
        self.assertEqual(notif.status, "acknowledged")

        # acknowledged -> responding
        res3 = notif.transition_to("responding", reason="Unit en route")
        self.assertTrue(res3)
        self.assertEqual(notif.status, "responding")

        self.assertEqual(len(notif.history), 3)

    def test_api_match_facilities_endpoint(self):
        """POST /api/v1/notifications/match returns facilities ranked by distance."""
        res = self.client.post(
            "/api/v1/notifications/match",
            json={"latitude": 18.5204, "longitude": 73.8567, "limit": 3},
        )
        self.assertEqual(res.status_code, 200)
        matched = res.json()
        self.assertGreaterEqual(len(matched), 1)
        self.assertTrue(matched[0]["is_simulated"])

    def test_api_trigger_and_update_notification(self):
        """POST /api/v1/notifications triggers dispatch; PATCH /{id}/status updates lifecycle."""
        # 1. Create incident first
        inc_payload = {
            "incident_id": "INC-NOTIF-TEST-001",
            "incident_type": "vehicle_collision",
            "camera_id": "CAM-MAIN-01",
            "timestamp": 12345.0,
            "verification_status": "verified",
            "confidence_score": 0.95,
            "location": {"latitude": 18.5204, "longitude": 73.8567, "name": "Main Square"},
        }
        self.client.post("/api/v1/incidents", json=inc_payload)

        # 2. Trigger simulated dispatch to FAC-HOSPITAL-01
        trigger_res = self.client.post(
            "/api/v1/notifications",
            json={
                "incident_id": "INC-NOTIF-TEST-001",
                "facility_id": "FAC-HOSPITAL-01",
                "message": "SIMULATED DISPATCH TEST",
            },
        )
        self.assertEqual(trigger_res.status_code, 201)
        notif = trigger_res.json()
        notif_id = notif["notification_id"]
        self.assertEqual(notif["status"], "notified")
        self.assertTrue(notif["is_simulated"])

        # 3. Update status to acknowledged
        patch_res1 = self.client.patch(
            f"/api/v1/notifications/{notif_id}/status",
            json={"status": "acknowledged", "reason": "Operator confirmed receipt"},
        )
        self.assertEqual(patch_res1.status_code, 200)
        self.assertEqual(patch_res1.json()["status"], "acknowledged")

        # 4. Update status to responding
        patch_res2 = self.client.patch(
            f"/api/v1/notifications/{notif_id}/status",
            json={"status": "responding", "reason": "Ambulance en route to scene"},
        )
        self.assertEqual(patch_res2.status_code, 200)
        self.assertEqual(patch_res2.json()["status"], "responding")

        # 5. List notifications for incident
        list_res = self.client.get("/api/v1/notifications?incident_id=INC-NOTIF-TEST-001")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 1)


if __name__ == "__main__":
    unittest.main()
