"""
End-to-End Tests for AutoAlert AI Teammate Orchestration Layer.

Verifies:
  - 6-Stage Operational Workflow: OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT
  - Deterministic execution across all system tools
  - Factual, grounded executive briefings and merchant advisories (zero hallucination)
  - Clear SIMULATED emergency prototype dispatches
  - FastAPI endpoints for AI Teammate orchestration
"""

from __future__ import annotations

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from backend.schemas.incident import IncidentPackageCreateSchema, LocationSchema, PlateReadingSchema
from src.teammate.orchestrator import AITeammateOrchestrator, ai_teammate
from src.teammate.models import WorkflowStage, TeammateOrchestrationResult
from src.teammate.tools import (
    tool_get_incident,
    tool_get_location,
    tool_find_facilities,
    tool_calculate_distances,
    tool_generate_route,
    tool_create_notification_records,
    tool_create_incident_summary,
)
from src.video.demo_generator import generate_sample_collision_video


class TestAITeammateOrchestratorE2E:
    """Test suite for AI Teammate Orchestration Layer."""

    def setup_method(self):
        repository.reset()
        self.client = TestClient(app)
        self.orchestrator = AITeammateOrchestrator()

        # Seed verified incident for deterministic testing
        self.test_incident = IncidentPackageCreateSchema(
            incident_id="INC-TEAMMATE-001",
            incident_type="traffic_collision",
            camera_id="CAM-001",
            timestamp=1700000000.0,
            verification_status="verified",
            confidence_score=0.94,
            created_at="2026-10-02T10:00:00Z",
            involved_track_ids=[1, 2],
            evidence_frames=["data/evidence/test_frame_1.jpg"],
            location=LocationSchema(
                name="North Arterial Highway Intersection",
                latitude=18.5204,
                longitude=73.8567,
                zone_id="ZONE-NORTH-A",
            ),
            plate_readings=[
                PlateReadingSchema(
                    track_id=1,
                    plate_number="MH12AB1234",
                    confidence=0.96,
                    format_validated=True,
                    status="verified",
                )
            ],
            reason_metadata={"severity": "CRITICAL", "closing_speed_kmh": 65.4},
        )
        repository.add_incident(self.test_incident)

    def test_deterministic_tools_execution(self):
        """Verify each tool returns exact, structured, non-fabricated system data."""
        # 1. tool_get_incident
        inc = tool_get_incident("INC-TEAMMATE-001")
        assert inc is not None
        assert inc["incident_id"] == "INC-TEAMMATE-001"
        assert inc["confidence_score"] == 0.94

        # 2. tool_get_location
        loc = tool_get_location(camera_id="CAM-001")
        assert loc is not None
        assert loc.latitude == 18.5204
        assert loc.longitude == 73.8567

        # 3. tool_find_facilities & calculate_distances
        facs_res = tool_find_facilities(incident_lat=loc.latitude, incident_lon=loc.longitude, limit=3)
        assert facs_res["nearest_ambulance"] is not None
        assert facs_res["nearest_hospital"] is not None
        assert facs_res["nearest_police"] is not None

        # 4. tool_generate_route
        route = tool_generate_route(
            ambulance=facs_res["nearest_ambulance"],
            incident_lat=loc.latitude,
            incident_lon=loc.longitude,
            hospital=facs_res["nearest_hospital"],
        )
        assert route is not None
        assert route.total_distance_km > 0
        assert len(route.legs) == 2

        # 5. tool_create_notification_records
        notifs = tool_create_notification_records(
            incident_id="INC-TEAMMATE-001",
            ambulance_name=facs_res["nearest_ambulance"]["name"],
            police_name=facs_res["nearest_police"]["name"],
            hospital_name=facs_res["nearest_hospital"]["name"],
            merchant_name="Store Operations",
            location_name=loc.name,
            camera_id="CAM-001",
        )
        assert len(notifs) >= 4
        assert all(n.status == "SIMULATED" for n in notifs)

        # 6. tool_create_incident_summary
        summary = tool_create_incident_summary(
            incident=inc,
            location=loc,
            facilities_result=facs_res,
            route_result=route,
            notification_records=notifs,
            camera_name="Camera 1 — Main Highway Junction",
            executive_briefing="Test Briefing",
            merchant_advisory="Test Advisory",
        )
        assert summary.incident_id == "INC-TEAMMATE-001"
        assert summary.confidence_score == 0.94
        assert summary.is_simulated is True
        assert len(summary.license_plates) == 1
        assert summary.license_plates[0] == "MH12AB1234"

    def test_orchestrate_verified_incident_workflow(self):
        """Verify the DECIDE ➔ ACT ➔ REPORT workflow on a verified incident."""
        result: TeammateOrchestrationResult = self.orchestrator.orchestrate_verified_incident(
            incident_id="INC-TEAMMATE-001",
            camera_id="CAM-001",
            custom_merchant_name="Highway Junction Superstore",
        )

        assert result.success is True
        assert result.incident_id == "INC-TEAMMATE-001"
        assert result.summary is not None

        # Verify stages executed
        stage_names = [s.stage for s in result.stages_executed]
        assert WorkflowStage.DECIDE in stage_names
        assert WorkflowStage.ACT in stage_names
        assert WorkflowStage.REPORT in stage_names

        # Verify factual synthesis
        summary = result.summary
        assert "MH12AB1234" in summary.executive_briefing
        assert "North Arterial" in summary.executive_briefing
        assert "SIMULATED" in summary.executive_briefing
        assert "Highway Junction Superstore" in summary.merchant_advisory

    def test_orchestrate_raw_cctv_stream_6_stages(self):
        """Verify full 6-stage lifecycle on CCTV video: OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT."""
        temp_dir = tempfile.gettempdir()
        v_path = os.path.join(temp_dir, "teammate_test_video.mp4")
        generate_sample_collision_video(v_path, num_frames=25)

        progress_log = []

        def on_progress(stage, details):
            progress_log.append((stage, details))

        res: TeammateOrchestrationResult = self.orchestrator.orchestrate_cctv_stream(
            video_path=v_path,
            camera_id="CAM-001",
            force_demo_incident=True,
            progress_callback=on_progress,
        )

        assert res.success is True
        assert len(res.stages_executed) >= 6

        stages_enum = [s.stage for s in res.stages_executed]
        assert WorkflowStage.OBSERVE in stages_enum
        assert WorkflowStage.UNDERSTAND in stages_enum
        assert WorkflowStage.VERIFY in stages_enum
        assert WorkflowStage.DECIDE in stages_enum
        assert WorkflowStage.ACT in stages_enum
        assert WorkflowStage.REPORT in stages_enum

        if os.path.exists(v_path):
            os.remove(v_path)

    def test_fastapi_teammate_endpoints(self):
        """Verify FastAPI endpoints for orchestrating incidents and generating briefings."""
        # 1. POST /api/v1/teammate/orchestrate
        resp = self.client.post(
            "/api/v1/teammate/orchestrate",
            json={"incident_id": "INC-TEAMMATE-001", "merchant_name": "Test Store"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["incident_id"] == "INC-TEAMMATE-001"
        assert len(data["stages_executed"]) >= 3

        # 2. GET /api/v1/teammate/status/{incident_id}
        status_resp = self.client.get("/api/v1/teammate/status/INC-TEAMMATE-001")
        assert status_resp.status_code == 200
        assert status_resp.json()["incident_id"] == "INC-TEAMMATE-001"

        # 3. POST /api/v1/teammate/briefing
        brief_resp = self.client.post(
            "/api/v1/teammate/briefing",
            json={"incident_id": "INC-TEAMMATE-001"},
        )
        assert brief_resp.status_code == 200
        b_data = brief_resp.json()
        assert "CAD DISPATCH OPERATIONAL BRIEFING" in b_data["executive_briefing"]
        assert "MH12AB1234" in b_data["executive_briefing"]
        assert b_data["is_simulated"] is True
