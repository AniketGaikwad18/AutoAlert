"""
End-to-End Tests for AutoAlert AI Operations Frontend (Phases 15–17).

Verifies:
  - Full DashboardAPIClient integration with FastAPI and fallback
  - Progressive 10-step simulation execution workflow
  - Multi-agency notification timeline retrieval & dispatch
  - 2-Leg emergency route calculation & corridor proximity
  - Streamlit dashboard scripts compilation & integrity
"""

from __future__ import annotations

import os
import tempfile
import pytest
from backend.repository import repository
from dashboard.api_client import DashboardAPIClient
from src.simulation.controller import CCTVSimulationService, SimulationResult
from src.video.demo_generator import generate_sample_collision_video


class TestFrontendPhases15To17E2E:
    """Test suite covering the complete AutoAlert frontend and operations command center."""

    def setup_method(self):
        repository.reset()
        self.client = DashboardAPIClient()
        self.sim_svc = CCTVSimulationService()

    def test_api_client_health_and_infrastructure(self):
        """Verify client connects to backend health check and lists cameras/facilities."""
        health = self.client.check_health()
        assert "status" in health

        cameras = self.client.list_cameras()
        assert len(cameras) >= 1
        assert any(c["camera_id"] == "CAM-001" for c in cameras)

        cam_001 = self.client.get_camera("CAM-001")
        assert cam_001 is not None
        assert cam_001["camera_id"] == "CAM-001"

        facilities = self.client.list_facilities()
        assert len(facilities) >= 3

    def test_progressive_10_step_simulation_execution(self):
        """Test end-to-end execution covering all 10 progressive workflow steps."""
        temp_dir = tempfile.gettempdir()
        test_video_path = os.path.join(temp_dir, "test_frontend_collision.mp4")
        generate_sample_collision_video(test_video_path, num_frames=25)

        assert os.path.exists(test_video_path)

        # Execute simulation pipeline
        result: SimulationResult = self.sim_svc.run_simulation(
            camera_id="CAM-001",
            video_path=test_video_path,
            force_demo_incident=True,
        )

        assert result.success is True
        assert result.verified is True
        assert result.incident is not None

        # Step 5: Incident Result
        assert result.incident.verification_status == "verified"
        assert result.incident.confidence_score >= 0.50

        # Step 6: Evidence & Plate
        assert len(result.evidence_frames) >= 1

        # Step 7: Facilities
        assert result.nearest_ambulance is not None
        assert result.nearest_hospital is not None
        assert result.nearest_police is not None

        # Step 8: Route
        assert result.emergency_route is not None
        assert result.route_distance_km is not None
        assert result.route_distance_km > 0

        # Step 9: Notification Timeline
        assert len(result.notification_timeline) >= 4

        # Clean up
        if os.path.exists(test_video_path):
            os.remove(test_video_path)

    def test_api_client_dispatch_and_timeline(self):
        """Verify manual simulated dispatch triggers and timeline retrieval via client."""
        # 1. Dispatch manual simulated alert
        resp = self.client.dispatch_notification(
            incident_id="INC-FRONTEND-TEST-001",
            recipient_type="ambulance",
            recipient_name="Pune Central EMS",
            message="Test dispatch from frontend command center",
        )
        assert resp is not None
        assert resp.get("status") == "SIMULATED"
        assert resp.get("recipient_type") == "ambulance"

        # 2. Retrieve timeline
        timeline = self.client.get_incident_timeline("INC-FRONTEND-TEST-001")
        assert len(timeline) >= 1
        assert any(t.get("recipient_type") == "ambulance" for t in timeline)

    def test_api_client_route_calculation(self):
        """Verify direct 2-leg route calculation through client."""
        route = self.client.calculate_route(
            incident_lat=18.5204,
            incident_lon=73.8567,
        )
        assert route is not None
        assert "legs" in route
        assert len(route["legs"]) == 2
        assert route.get("total_distance_km", 0) > 0

    def test_dashboard_files_exist_and_compile(self):
        """Verify all dashboard pages and scripts compile without syntax errors."""
        import py_compile

        files_to_check = [
            "dashboard/app.py",
            "dashboard/api_client.py",
            "dashboard/pages/1_Incidents.py",
            "dashboard/pages/2_Cameras.py",
            "dashboard/pages/3_Facilities.py",
            "dashboard/components/incident_card.py",
            "dashboard/components/filters.py",
        ]
        for file_path in files_to_check:
            assert os.path.exists(file_path), f"Missing {file_path}"
            py_compile.compile(file_path, doraise=True)
