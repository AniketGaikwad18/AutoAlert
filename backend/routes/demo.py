"""Controlled demonstration routes for AutoAlert emergency response."""

import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import IncidentRepository
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload
from src.coordination.response_coordinator import ResponseCoordinator

from pydantic import BaseModel

router = APIRouter(tags=["demo"])

# In-memory lock to prevent accidental concurrent multi-triggers
_is_demo_processing = False


class DemoExecuteRequest(BaseModel):
    scenario_id: str = "collision_junction"


class DemoAcknowledgeRequest(BaseModel):
    incident_id: Optional[str] = None
    agency: str = "police"  # "police" or "ambulance"


@router.get("/api/demo/scenarios")
@router.get("/api/v1/demo/scenarios")
def get_demo_scenarios():
    """Retrieve preset demonstration exhibition scenarios."""
    from src.demo.demo_engine import SCENARIOS
    return [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "description": s.description,
            "camera_id": s.camera_id,
            "camera_name": s.camera_name,
            "location_name": s.location_name,
            "video_filename": s.video_filename,
            "expected_event_type": s.expected_event_type,
            "is_emergency": s.is_emergency,
        }
        for s in SCENARIOS.values()
    ]


@router.get("/api/demo/camera1")
@router.get("/api/v1/demo/camera1")
def get_demo_camera1():
    """Retrieve demo camera 1 profile and preset."""
    from src.demo.demo_engine import SCENARIOS
    s = SCENARIOS["collision_junction"]
    return {
        "camera_id": s.camera_id,
        "camera_name": s.camera_name,
        "location_name": s.location_name,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "demo_mode": True,
        "video_filename": s.video_filename,
        "expected_event_type": s.expected_event_type,
    }


@router.post("/api/demo/execute")
@router.post("/api/v1/demo/execute")
def execute_demo_scenario(req: DemoExecuteRequest, db: Session = Depends(get_db)):
    """Execute end-to-end demo workflow with preset scenario."""
    from src.demo.demo_engine import demo_manager
    res = demo_manager.execute_demo_flow(scenario_id=req.scenario_id)
    inc_data = None
    if res.incident:
        inc_data = res.incident.model_dump() if hasattr(res.incident, "model_dump") else (res.incident.to_dict() if hasattr(res.incident, "to_dict") else res.incident)
    return {
        "demo_mode": True,
        "execution_success": res.success,
        "workflow_completed": res.workflow_completed,
        "incident": inc_data,
        "emergency_route": res.emergency_route.to_dict() if res.emergency_route else None,
        "notifications": res.simulated_notifications,
        "simulated_notifications": res.simulated_notifications,
        "summary": res.summary.to_dict() if hasattr(res.summary, "to_dict") else (asdict(res.summary) if hasattr(res.summary, "__dataclass_fields__") else res.summary),
    }


@router.post("/api/demo/trigger")
@router.post("/api/v1/demo/trigger")
def trigger_demo_incident(
    video_source: Optional[str] = "Traffic Junction Cam 1",
    db: Session = Depends(get_db)
):
    """Trigger a controlled, judge-ready live emergency response demonstration."""
    global _is_demo_processing
    if _is_demo_processing:
        raise HTTPException(
            status_code=429,
            detail="A demonstration is currently in progress. Please wait a moment."
        )

    _is_demo_processing = True
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inc_suffix = datetime.now(timezone.utc).strftime("%M%S")
        incident_id = f"INC-DEMO-{inc_suffix}"
        camera_id = "CAM-01"
        location_desc = "Shivajinagar Junction, Pune"

        coordinator = ResponseCoordinator(simulation_mode=True)
        response_data = coordinator.orchestrate_response(
            incident_id=incident_id,
            camera_id=camera_id,
            location_desc=location_desc,
            initial_timestamp=now_iso,
            is_demo=True
        )

        # Formulate standardized IncidentPackage
        pkg = IncidentPackage(
            incident_id=incident_id,
            incident_type="Possible Road Accident",
            camera_id=camera_id,
            timestamp=now_iso,
            confidence_score=0.885,
            verification_status="verified",
            involved_track_ids=[1, 2],
            reasons=[
                "Abrupt vehicle deceleration ratio 0.82 (severe impact dynamics)",
                "Spatial convergence to 42.0px with 38° trajectory deflection",
                "Temporal interaction persisted across multiple consecutive video frames"
            ],
            signals={
                "proximity_px": 42.0,
                "speed_drop_ratio": 0.82,
                "deflection_deg": 38.0
            },
            location=LocationModel(latitude=18.5204, longitude=73.8567, description=location_desc),
            evidence=EvidencePayload(
                directory="outputs/incidents/INC-0001",
                key_frames=["outputs/incidents/INC-0001/keyframe_14_1.jpg", "outputs/incidents/INC-0001/keyframe_18_2.jpg"],
                video_clip="outputs/incidents/INC-0001/clip_INC-0001.mp4"
            ),
            plate_readings=[
                PlateReadingPayload(
                    track_id=1,
                    plate_text="MH12AB1234",
                    confidence=0.86,
                    is_readable=True,
                    format_valid=True
                )
            ]
        )

        persisted = IncidentRepository.create(
            db,
            pkg=pkg,
            source_device="Raspberry Pi AI Box",
            mode="DEMO",
            ambulance_status=response_data["ambulance"]["status"],
            ambulance_unit=response_data["ambulance"]["unit_id"],
            police_station_name=response_data["police"]["station_name"],
            police_status=response_data["police"]["status"],
            timeline_events=response_data["timeline"]
        )

        return {
            "status": "success",
            "message": "Demo incident triggered and orchestrated successfully.",
            "incident_id": persisted.id,
            "ambulance_status": persisted.ambulance_status,
            "police_status": persisted.police_status,
            "timeline": response_data["timeline"]
        }
    finally:
        _is_demo_processing = False


@router.post("/api/demo/acknowledge")
@router.post("/api/v1/demo/acknowledge")
def acknowledge_demo_response(req: DemoAcknowledgeRequest, db: Session = Depends(get_db)):
    """Acknowledge emergency alert as Police Desk officer or confirm Ambulance En Route."""
    inc = IncidentRepository.get_by_id(db, req.incident_id) if req.incident_id else IncidentRepository.get_latest(db)
    if not inc:
        raise HTTPException(status_code=404, detail="No active incident found to acknowledge.")

    timeline = json.loads(inc.timeline_events_json or "[]")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if req.agency == "police":
        inc.police_status = "Acknowledged"
        timeline.append({
            "step": len(timeline) + 1,
            "title": "Police station acknowledges notification",
            "timestamp": now_iso,
            "status": "COMPLETED",
            "details": f"Police desk officer confirmed reception of incident dossier for [{inc.id}]."
        })
    elif req.agency == "ambulance":
        inc.ambulance_status = "En Route"
        timeline.append({
            "step": len(timeline) + 1,
            "title": "Ambulance response updated: Unit En Route",
            "timestamp": now_iso,
            "status": "EN_ROUTE",
            "details": f"{inc.ambulance_unit} confirmed en route to scene (Target ETA: {inc.ambulance_eta})."
        })

    inc.timeline_events_json = json.dumps(timeline)
    db.commit()
    db.refresh(inc)
    return {
        "status": "success",
        "incident_id": inc.id,
        "police_status": inc.police_status,
        "ambulance_status": inc.ambulance_status,
        "timeline": timeline,
    }


@router.post("/api/demo/reset")
@router.post("/api/v1/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    """Reset current demo view to clean state without deleting records."""
    return {
        "status": "reset",
        "message": "Demo state reset. System ready for demonstration trigger."
    }
