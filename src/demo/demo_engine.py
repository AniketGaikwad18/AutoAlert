"""
AutoAlert AI Demo Mode Engine (Hackathon Live Presentation & Simulation).

Provides self-contained, 100% reliable demonstration execution of the complete
AutoAlert emergency response pipeline without requiring real-world external 911/SMS integrations.

Workflow Executed:
  Camera Selection ➔ Video Upload ➔ AI Analysis ➔ Temporal Verification ➔
  Incident Creation ➔ Facility Matching ➔ Route Generation ➔ Simulated Notifications ➔ Final Report
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

import cv2
import numpy as np

from backend.repository import repository
from backend.schemas.incident import IncidentPackageCreateSchema, LocationSchema, PlateReadingSchema
from src.core.incident import LocationInfo, IncidentPackage
from src.location.camera_registry import camera_registry
from src.location.facility_registry import facility_registry
from src.simulation.controller import CCTVSimulationService, SimulationResult, SimulationProgressStep
from src.teammate.orchestrator import ai_teammate, AITeammateOrchestrator
from src.teammate.models import TeammateOrchestrationResult, StructuredIncidentSummary
from src.teammate.tools import (
    tool_get_incident,
    tool_get_location,
    tool_find_facilities,
    tool_generate_route,
    tool_create_notification_records,
    tool_create_incident_summary,
)
from src.video.demo_generator import generate_sample_collision_video

logger = logging.getLogger(__name__)

DEMO_VIDEOS_DIR = os.path.join("data", "demo_videos")


@dataclass
class DemoScenario:
    """Configuration for a preset exhibition demonstration scenario."""
    scenario_id: str
    name: str
    description: str
    camera_id: str
    camera_name: str
    location_name: str
    latitude: float
    longitude: float
    video_filename: str
    expected_event_type: str
    is_emergency: bool = True
    plate_number: str = "MH12AB1234"
    merchant_name: str = "Highway Junction Superstore"


# Preset Demonstration Scenarios
SCENARIOS = {
    "collision_junction": DemoScenario(
        scenario_id="collision_junction",
        name="High-Speed Collision at Arterial Junction",
        description="Two converging vehicles collide with sudden velocity drop and visible plate MH12AB1234.",
        camera_id="CAM-001",
        camera_name="Camera 1 — Main Highway Junction",
        location_name="Demo Location A — North Arterial Intersection",
        latitude=18.5204,
        longitude=73.8567,
        video_filename="demo_junction_collision.mp4",
        expected_event_type="traffic_collision",
        is_emergency=True,
        plate_number="MH12AB1234",
        merchant_name="Highway Junction Superstore",
    ),
    "motionless_pedestrian": DemoScenario(
        scenario_id="motionless_pedestrian",
        name="Stationary Pedestrian Incident on Expressway",
        description="A pedestrian track stops abruptly on the roadway and remains motionless beyond the safety threshold.",
        camera_id="CAM-002",
        camera_name="Camera 2 — South Expressway Flyover",
        location_name="Demo Location B — South Expressway Corridor",
        latitude=18.5310,
        longitude=73.8440,
        video_filename="demo_motionless_pedestrian.mp4",
        expected_event_type="prolonged_motionlessness",
        is_emergency=True,
        plate_number="unreadable",
        merchant_name="Expressway Plaza",
    ),
    "normal_traffic": DemoScenario(
        scenario_id="normal_traffic",
        name="Normal Commercial Traffic Flow (Negative Baseline)",
        description="Normal vehicle and pedestrian flow with safe braking and zero kinematic anomalies.",
        camera_id="CAM-003",
        camera_name="Camera 3 — Commercial Plaza Crossing",
        location_name="Demo Location C — East Central Plaza",
        latitude=18.5120,
        longitude=73.8650,
        video_filename="demo_normal_flow.mp4",
        expected_event_type="normal_traffic",
        is_emergency=False,
        plate_number="unreadable",
        merchant_name="Central Plaza Retail",
    ),
}


class DemoManager:
    """Manages demo mode execution and asset preparation for live exhibitions."""

    def __init__(self) -> None:
        self.scenarios = SCENARIOS
        self.demo_dir = DEMO_VIDEOS_DIR
        os.makedirs(self.demo_dir, exist_ok=True)
        self.prepare_demo_assets()

    def prepare_demo_assets(self) -> None:
        """Pre-generate sample demonstration video files if not present on disk."""
        try:
            # 1. Collision video
            col_path = os.path.join(self.demo_dir, "demo_junction_collision.mp4")
            if not os.path.exists(col_path):
                generate_sample_collision_video(col_path, num_frames=35, fps=15.0)

            # 2. Motionless video
            mot_path = os.path.join(self.demo_dir, "demo_motionless_pedestrian.mp4")
            if not os.path.exists(mot_path):
                self._generate_motionless_video(mot_path)

            # 3. Normal traffic video
            norm_path = os.path.join(self.demo_dir, "demo_normal_flow.mp4")
            if not os.path.exists(norm_path):
                self._generate_normal_traffic_video(norm_path)
        except Exception as e:
            logger.warning("Error preparing demo video assets: %s", e)

    def _generate_motionless_video(self, target_path: str) -> str:
        """Generate synthetic pedestrian motionless clip."""
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        width, height = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(target_path, fourcc, 15.0, (width, height))

        for idx in range(35):
            img = np.full((height, width, 3), (30, 30, 35), dtype=np.uint8)
            # Sidewalk and road
            cv2.rectangle(img, (0, 200), (640, 480), (45, 45, 55), -1)
            cv2.line(img, (0, 260), (640, 260), (200, 200, 200), 2)

            # Person moving initially, then static on roadway
            px = int(80 + idx * 8) if idx < 12 else 176
            py = 320
            # Draw pedestrian figure
            cv2.circle(img, (px, py - 30), 12, (220, 200, 180), -1)
            cv2.rectangle(img, (px - 8, py - 18), (px + 8, py + 20), (50, 180, 50), -1)

            cv2.putText(img, f"AUTOALERT PEDESTRIAN CAM | Frame {idx:02d}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 2)
            out.write(img)

        out.release()
        return target_path

    def _generate_normal_traffic_video(self, target_path: str) -> str:
        """Generate normal traffic flow clip without collisions."""
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        width, height = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(target_path, fourcc, 15.0, (width, height))

        for idx in range(30):
            img = np.full((height, width, 3), (25, 30, 35), dtype=np.uint8)
            cv2.rectangle(img, (0, 200), (640, 400), (40, 45, 50), -1)
            cv2.line(img, (0, 300), (640, 300), (180, 180, 180), 2)

            # Parallel moving cars maintaining safe distance
            x1 = int(20 + idx * 18)
            x2 = int(220 + idx * 18)

            cv2.rectangle(img, (x1, 230), (x1 + 60, 280), (0, 180, 220), -1)
            cv2.rectangle(img, (x2, 320), (x2 + 65, 370), (220, 100, 0), -1)

            cv2.putText(img, f"AUTOALERT NORMAL FLOW | Frame {idx:02d}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 2)
            out.write(img)

        out.release()
        return target_path

    def get_scenario(self, scenario_id: str) -> Optional[DemoScenario]:
        """Get demo scenario metadata by ID."""
        return self.scenarios.get(scenario_id)

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List all available demo scenarios."""
        return [
            {
                "scenario_id": s.scenario_id,
                "name": s.name,
                "description": s.description,
                "camera_id": s.camera_id,
                "camera_name": s.camera_name,
                "location_name": s.location_name,
                "expected_event_type": s.expected_event_type,
                "is_emergency": s.is_emergency,
                "video_path": os.path.join(self.demo_dir, s.video_filename),
            }
            for s in self.scenarios.values()
        ]

    def execute_demo_flow(
        self,
        scenario_id: str = "collision_junction",
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> TeammateOrchestrationResult:
        """
        Execute the real application workflow end-to-end for a demo scenario:
          1. Camera Selection
          2. Video Ingestion
          3. AI Vision Analysis (YOLO & Hungarian Tracking)
          4. Temporal Multi-Frame Verification
          5. Incident Creation & Database Ingestion
          6. Facility Matching (Haversine distances)
          7. 2-Leg Route Generation (OpenStreetMap / OSRM)
          8. Simulated Notifications (Ambulance, Police, Hospital, Merchant)
          9. Grounded Executive Incident Report & CAD Dossier
        """
        scenario = self.get_scenario(scenario_id) or self.scenarios["collision_junction"]
        video_path = os.path.join(self.demo_dir, scenario.video_filename)

        if not os.path.exists(video_path):
            self.prepare_demo_assets()

        # Execute through AI Teammate Orchestrator
        orchestrator = AITeammateOrchestrator()
        result = orchestrator.orchestrate_cctv_stream(
            video_path=video_path,
            camera_id=scenario.camera_id,
            force_demo_incident=scenario.is_emergency,
            progress_callback=progress_callback,
        )

        return result


# Global singleton demo manager instance
demo_manager = DemoManager()
