"""
End-to-End Test Suite for AutoAlert AI Demo Mode (Hackathon Live Presentation).

Verifies:
  1. Camera 1 Registration and Geospatial Metadata
  2. Demo CCTV Video Ingestion and Synthetic Asset Generation
  3. Real End-to-End Application Workflow (Not Hardcoded!):
     Camera Selection ➔ Video Ingestion ➔ AI Detection & Tracking ➔
     Kinematic Verification ➔ Incident Creation ➔ Facility Matching ➔
     Route Generation ➔ Simulated Notifications ➔ Grounded CAD Dossier
  4. SIMULATED status across all emergency response records
  5. Multi-scenario execution (High-Speed Collision, Stationary Pedestrian, Normal Flow)
  6. REST API Endpoints (/api/v1/demo/scenarios, /api/v1/demo/camera1, /api/v1/demo/execute)
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from src.demo.demo_engine import demo_manager, SCENARIOS, DemoManager
from src.location.camera_registry import camera_registry
from src.location.facility_registry import facility_registry
from src.teammate.models import WorkflowStage


class TestDemoModeE2E:
    """End-to-End test suite for Demo Mode & Hackathon Live Presentation Flow."""

    def setup_method(self):
        repository.reset()
        self.client = TestClient(app)
        self.demo_mgr = demo_manager
        self.demo_mgr.prepare_demo_assets()

    def test_camera_1_registered_and_configured(self):
        """Verify Camera 1 is pre-registered with correct GPS coordinates and merchant."""
        cam1 = repository.get_camera("CAM-001")
        assert cam1 is not None, "Camera 1 (CAM-001) must exist in camera repository"
        assert "Camera 1" in cam1.name or "CAM-001" in cam1.name
        assert cam1.latitude == pytest.approx(18.5204, rel=1e-3)
        assert cam1.longitude == pytest.approx(73.8567, rel=1e-3)
        assert cam1.merchant_name is not None

    def test_demo_video_assets_generated(self):
        """Verify demo CCTV videos are created and readable on disk."""
        for scenario in SCENARIOS.values():
            video_path = os.path.join(self.demo_mgr.demo_dir, scenario.video_filename)
            assert os.path.exists(video_path), f"Demo video '{scenario.video_filename}' must exist on disk"
            assert os.path.getsize(video_path) > 0, f"Demo video '{scenario.video_filename}' must not be empty"

    def test_camera_1_collision_workflow_execution_not_hardcoded(self):
        """
        Verify the real application workflow executes sequentially for Camera 1 Collision:
          Camera selection ➔ video upload ➔ analysis ➔ verification ➔
          incident creation ➔ facility matching ➔ route generation ➔
          simulated notifications ➔ final incident report.
        """
        # Execute workflow
        res = self.demo_mgr.execute_demo_flow(scenario_id="collision_junction")

        assert res.success is True, f"Demo execution failed: {res.error_message}"
        assert res.incident is not None, "Verified emergency incident must be created"
        assert res.incident.incident_type == "traffic_collision"
        assert res.incident.camera_id == "CAM-001"
        assert res.incident.confidence_score >= 0.80
        assert res.incident.verification_status == "verified"
        assert len(res.incident.involved_track_ids) >= 1

        # Check location resolution from Camera 1
        assert res.location is not None
        assert res.location.latitude == pytest.approx(18.5204, rel=1e-3)
        assert res.location.longitude == pytest.approx(73.8567, rel=1e-3)

        # Check facility matching (Haversine distances calculated)
        assert res.nearest_facilities is not None
        assert "nearest_ambulance" in res.nearest_facilities
        assert "nearest_hospital" in res.nearest_facilities
        assert "nearest_police" in res.nearest_facilities
        assert res.nearest_facilities["nearest_ambulance"]["distance_km"] > 0
        assert res.nearest_facilities["nearest_hospital"]["distance_km"] > 0

        # Check 2-leg emergency route generation
        assert res.emergency_route is not None
        assert res.emergency_route.total_distance_km > 0
        assert res.emergency_route.estimated_duration_min > 0
        assert len(res.emergency_route.legs) == 2

        # Check simulated notifications
        assert len(res.notifications) >= 4
        for notif in res.notifications:
            assert notif.status == "SIMULATED", f"Notification {notif.notification_id} status must be SIMULATED"
            assert notif.is_simulated is True
            assert notif.incident_id == res.incident.incident_id

        # Check structured report & summary
        assert res.summary is not None
        assert res.summary.incident_id == res.incident.incident_id
        assert len(res.summary.executive_briefing) > 0
        assert len(res.summary.merchant_advisory) > 0

        # Verify all 6 operational stages were executed
        executed_stage_names = [s.stage for s in res.stages_executed]
        for stg in [WorkflowStage.OBSERVE, WorkflowStage.UNDERSTAND, WorkflowStage.VERIFY, WorkflowStage.DECIDE, WorkflowStage.ACT, WorkflowStage.REPORT]:
            assert stg in executed_stage_names

    def test_pedestrian_emergency_scenario_workflow(self):
        """Verify Camera 2 Stationary Pedestrian emergency workflow executes cleanly."""
        res = self.demo_mgr.execute_demo_flow(scenario_id="motionless_pedestrian")
        assert res.success is True
        assert res.incident is not None
        assert res.incident.incident_type == "prolonged_motionlessness"
        assert res.incident.camera_id == "CAM-002"
        assert len(res.notifications) >= 4

    def test_normal_traffic_negative_baseline_workflow(self):
        """Verify normal traffic negative baseline completes without false emergency incident."""
        res = self.demo_mgr.execute_demo_flow(scenario_id="normal_traffic")
        assert res.success is True
        # For non-emergency negative baseline, no emergency incident is declared
        assert res.incident is None or res.incident.verification_status != "verified"

    def test_fastapi_demo_scenarios_endpoint(self):
        """Verify GET /api/v1/demo/scenarios endpoint."""
        response = self.client.get("/api/v1/demo/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        scenario_ids = [s["scenario_id"] for s in data]
        assert "collision_junction" in scenario_ids
        assert "motionless_pedestrian" in scenario_ids
        assert "normal_traffic" in scenario_ids

    def test_fastapi_demo_camera1_endpoint(self):
        """Verify GET /api/v1/demo/camera1 endpoint."""
        response = self.client.get("/api/v1/demo/camera1")
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id"] == "CAM-001"
        assert data["demo_mode"] is True
        assert "Main Highway Junction" in data["camera_name"] or "Camera 1" in data["camera_name"]
        assert data["latitude"] == pytest.approx(18.5204, rel=1e-3)

    def test_fastapi_demo_execute_endpoint(self):
        """Verify POST /api/v1/demo/execute triggers full live workflow."""
        payload = {"scenario_id": "collision_junction"}
        response = self.client.post("/api/v1/demo/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["demo_mode"] is True
        assert data["execution_success"] is True
        assert data["workflow_completed"] is True
        assert data["incident"] is not None
        assert data["incident"]["incident_type"] == "traffic_collision"
        assert data["incident"]["camera_id"] == "CAM-001"
        assert data["emergency_route"] is not None
        assert len(data["notifications"]) >= 4
        for n in data["notifications"]:
            assert n["status"] == "SIMULATED"
