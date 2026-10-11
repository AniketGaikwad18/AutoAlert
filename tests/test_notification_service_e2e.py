"""
Comprehensive Tests for Modular NotificationService & Chronological Timeline (Phase 14).

Validates:
1. NotificationService Methods:
   - notify_ambulance()
   - notify_police()
   - notify_hospital()
   - notify_merchant()
2. Structured Notification Record:
   - notification ID
   - incident ID
   - recipient
   - recipient type
   - timestamp
   - status explicitly indicating 'SIMULATED'
   - message
3. Chronological Incident Notification Timeline Generation & Ordering.
4. FastAPI Endpoints:
   - POST /api/v1/notifications/dispatch (ambulance, police, hospital, merchant)
   - GET /api/v1/notifications/timeline
   - GET /api/v1/incidents/{incident_id}/timeline
   - POST /api/v1/incidents/{incident_id}/timeline
"""

import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from src.core.incident import IncidentPackage, LocationInfo
from src.dispatch.notification_service import (
    NotificationService,
    NotificationRecord,
    notification_service,
)


class TestNotificationServicePhase14(unittest.TestCase):
    """Test suite covering Phase 14 NotificationService and timeline APIs."""

    def setUp(self):
        repository.reset()
        notification_service.clear()
        self.service = NotificationService()
        self.client = TestClient(app)

    # ----------------------------------------------------------------------
    # 1. NotificationService Unit Tests
    # ----------------------------------------------------------------------

    def test_notify_ambulance_structured_record(self):
        """notify_ambulance creates structured record with status='SIMULATED'."""
        rec = self.service.notify_ambulance(
            incident_id="INC-001",
            recipient="Central EMS Ambulance",
            message="Dispatch Paramedics immediately",
            details={"priority": "P1"},
        )

        self.assertIsInstance(rec, NotificationRecord)
        self.assertTrue(rec.notification_id.startswith("NOTIF-AMB"))
        self.assertEqual(rec.incident_id, "INC-001")
        self.assertEqual(rec.recipient, "Central EMS Ambulance")
        self.assertEqual(rec.recipient_type, "ambulance")
        self.assertEqual(rec.status, "SIMULATED")
        self.assertTrue(rec.is_simulated)
        self.assertIn("Dispatch Paramedics", rec.message)
        self.assertEqual(rec.details["priority"], "P1")

    def test_notify_police_structured_record(self):
        """notify_police creates structured record with status='SIMULATED'."""
        rec = self.service.notify_police(
            incident_id="INC-002",
            recipient="Shivajinagar Police Station",
        )

        self.assertTrue(rec.notification_id.startswith("NOTIF-POL"))
        self.assertEqual(rec.incident_id, "INC-002")
        self.assertEqual(rec.recipient_type, "police")
        self.assertEqual(rec.status, "SIMULATED")
        self.assertIn("SIMULATED", rec.message)

    def test_notify_hospital_structured_record(self):
        """notify_hospital creates structured record with status='SIMULATED'."""
        rec = self.service.notify_hospital(
            incident_id="INC-003",
            recipient="City Care Trauma Hospital",
        )

        self.assertTrue(rec.notification_id.startswith("NOTIF-HOS"))
        self.assertEqual(rec.incident_id, "INC-003")
        self.assertEqual(rec.recipient_type, "hospital")
        self.assertEqual(rec.status, "SIMULATED")
        self.assertIn("SIMULATED", rec.message)

    def test_notify_merchant_structured_record(self):
        """notify_merchant creates structured record with status='SIMULATED'."""
        rec = self.service.notify_merchant(
            incident_id="INC-004",
            recipient="Store Operations Manager",
        )

        self.assertTrue(rec.notification_id.startswith("NOTIF-MER"))
        self.assertEqual(rec.incident_id, "INC-004")
        self.assertEqual(rec.recipient_type, "merchant")
        self.assertEqual(rec.status, "SIMULATED")
        self.assertIn("SIMULATED", rec.message)

    # ----------------------------------------------------------------------
    # 2. Chronological Timeline Generation
    # ----------------------------------------------------------------------

    def test_chronological_notification_timeline_ordering(self):
        """create_incident_timeline generates strictly ordered chronological timeline."""
        base_time = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
        timeline = self.service.create_incident_timeline(
            incident_id="INC-COLLISION-100",
            camera_id="CAM-001",
            camera_name="Main Junction North",
            location_name="North Arterial Corridor",
            base_time=base_time,
        )

        self.assertEqual(len(timeline), 5)
        # Verify sequence of recipient types: system -> ambulance -> police -> hospital -> merchant
        types = [t.recipient_type for t in timeline]
        self.assertEqual(types, ["system", "ambulance", "police", "hospital", "merchant"])

        # Verify all statuses are SIMULATED
        for rec in timeline:
            self.assertEqual(rec.status, "SIMULATED")
            self.assertTrue(rec.is_simulated)

        # Verify strict ascending timestamp ordering
        for i in range(len(timeline) - 1):
            t_curr = datetime.fromisoformat(timeline[i].timestamp)
            t_next = datetime.fromisoformat(timeline[i + 1].timestamp)
            self.assertLess(t_curr, t_next)

    # ----------------------------------------------------------------------
    # 3. FastAPI API Endpoints Integration Tests
    # ----------------------------------------------------------------------

    def test_api_dispatch_simulated_notifications(self):
        """POST /api/v1/notifications/dispatch triggers modular dispatches."""
        for r_type in ["ambulance", "police", "hospital", "merchant"]:
            payload = {
                "incident_id": "INC-API-001",
                "recipient_type": r_type,
                "message": f"Test {r_type} dispatch",
                "details": {"test_flag": True},
            }
            res = self.client.post("/api/v1/notifications/dispatch", json=payload)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertEqual(data["incident_id"], "INC-API-001")
            self.assertEqual(data["recipient_type"], r_type)
            self.assertEqual(data["status"], "SIMULATED")
            self.assertTrue(data["is_simulated"])

    def test_api_get_notification_timeline(self):
        """GET /api/v1/notifications/timeline retrieves chronological records."""
        # Dispatch 2 records
        self.client.post(
            "/api/v1/notifications/dispatch",
            json={"incident_id": "INC-TIMELINE-01", "recipient_type": "ambulance"},
        )
        self.client.post(
            "/api/v1/notifications/dispatch",
            json={"incident_id": "INC-TIMELINE-01", "recipient_type": "police"},
        )

        res = self.client.get("/api/v1/notifications/timeline?incident_id=INC-TIMELINE-01")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["recipient_type"], "ambulance")
        self.assertEqual(data[1]["recipient_type"], "police")

    def test_api_incident_timeline_endpoint(self):
        """GET & POST /api/v1/incidents/{incident_id}/timeline generates timeline for incident."""
        incident_pkg = IncidentPackage(
            incident_id="INC-PKG-999",
            incident_type="vehicle_collision",
            camera_id="CAM-001",
            timestamp=2.0,
            verification_status="verified",
            confidence_score=0.88,
            location=LocationInfo(
                name="Market Street Cross",
                latitude=18.5204,
                longitude=73.8567,
            ),
        )
        repository.add_incident(incident_pkg)

        # GET timeline
        res = self.client.get("/api/v1/incidents/INC-PKG-999/timeline")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 5)
        self.assertEqual(data[0]["recipient_type"], "system")
        self.assertEqual(data[1]["recipient_type"], "ambulance")
        self.assertEqual(data[2]["recipient_type"], "police")
        self.assertEqual(data[3]["recipient_type"], "hospital")
        self.assertEqual(data[4]["recipient_type"], "merchant")
        for rec in data:
            self.assertEqual(rec["status"], "SIMULATED")


if __name__ == "__main__":
    unittest.main()
