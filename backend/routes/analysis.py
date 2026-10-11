"""
Video Analysis and Incident Pipeline API Endpoints for AutoAlert.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field

from src.simulation.controller import CCTVSimulationService, SimulationResult
from src.dispatch.routing import route_engine
from backend.repository import repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analysis & Routes"])


class AnalysisRequestSchema(BaseModel):
    camera_id: str = Field(..., description="ID of the registered CCTV camera")
    video_path: Optional[str] = Field(None, description="Local path to video file if already on server")
    demo_mode: bool = Field(True, description="Enable deterministic demo fallback for exhibition")


@router.post(
    "/api/v1/analyze",
    summary="Analyze CCTV video for emergency events",
    description="Processes video frames with YOLO detection, tracking, event analysis, temporal verification, and routing.",
)
@router.post(
    "/analyze",
    summary="Analyze CCTV video (alias)",
    description="Processes video frames with YOLO detection, tracking, event analysis, temporal verification, and routing.",
)
async def analyze_video(
    camera_id: str = Form(...),
    demo_mode: bool = Form(True),
    video: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run full AutoAlert AI pipeline on uploaded CCTV video."""
    temp_video_path = None
    try:
        if video is not None:
            suffix = os.path.splitext(video.filename or ".mp4")[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await video.read()
                tmp.write(content)
                temp_video_path = tmp.name
        else:
            # Check for default demo video assets
            possible_paths = [
                "data/demo_videos/demo_junction_collision.mp4",
                "data/demo_videos/sample_collision_demo.mp4",
                "data/videos/demo_collision.mp4",
            ]
            temp_video_path = next((p for p in possible_paths if os.path.exists(p)), None)
            if not temp_video_path:
                from src.video.demo_generator import generate_sample_collision_video
                d_path = "data/demo_videos/demo_junction_collision.mp4"
                generate_sample_collision_video(d_path)
                temp_video_path = d_path

        service = CCTVSimulationService()
        result: SimulationResult = service.run_simulation(
            camera_id=camera_id,
            video_path=temp_video_path,
            force_demo_incident=demo_mode,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message or "Video analysis failed.",
            )

        return {
            "success": True,
            "verified": result.verified,
            "camera_id": camera_id,
            "camera_name": result.camera.name if result.camera else None,
            "location": result.location.to_dict() if result.location else None,
            "incident": result.incident.to_dict() if result.incident else None,
            "evidence_frames": result.evidence_frames,
            "evidence_video_path": result.evidence_video_path,
            "plate_readings": result.plate_readings,
            "nearby_facilities": result.nearby_facilities,
            "emergency_route": result.emergency_route.to_dict() if result.emergency_route else None,
            "notification_timeline": result.notification_timeline,
            "simulated_notification": result.simulated_notification,
            "total_frames_analyzed": result.total_frames_analyzed,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analysis execution error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error running video analysis: {e}",
        )
    finally:
        if temp_video_path and temp_video_path.startswith(tempfile.gettempdir()):
            try:
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
            except Exception:
                pass


@router.get(
    "/api/v1/incidents/{incident_id}/route",
    summary="Get incident emergency response route",
    description="Calculates or retrieves the OSRM/Haversine response route for a given incident.",
)
@router.get(
    "/incidents/{incident_id}/route",
    summary="Get incident response route (alias)",
)
def get_incident_route(incident_id: str) -> Dict[str, Any]:
    """Retrieve emergency response route for a verified incident."""
    incident = repository.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )

    if not incident.location or not incident.location.latitude or not incident.location.longitude:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident does not have valid GPS coordinates.",
        )

    # Find nearest ambulance and hospital
    all_facs = [f.model_dump() for f in repository.list_facilities()]
    from src.dispatch.matching import FacilityMatcher
    ambulances = FacilityMatcher.match_facilities(
        incident_lat=incident.location.latitude,
        incident_lon=incident.location.longitude,
        facilities=all_facs,
        facility_type="ambulance",
        limit=1,
    )
    hospitals = FacilityMatcher.match_facilities(
        incident_lat=incident.location.latitude,
        incident_lon=incident.location.longitude,
        facilities=all_facs,
        facility_type="hospital",
        limit=1,
    )

    if not ambulances or not hospitals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find both ambulance and hospital facilities.",
        )

    amb = ambulances[0].get("facility", ambulances[0])
    hosp = hospitals[0].get("facility", hospitals[0])

    route_res = route_engine.plan_emergency_route(
        ambulance_lat=amb["latitude"],
        ambulance_lon=amb["longitude"],
        incident_lat=incident.location.latitude,
        incident_lon=incident.location.longitude,
        hospital_lat=hosp["latitude"],
        hospital_lon=hosp["longitude"],
        ambulance_id=amb["facility_id"],
        ambulance_name=amb["name"],
        hospital_id=hosp["facility_id"],
        hospital_name=hosp["name"],
    )

    return route_res.to_dict()


@router.get(
    "/api/v1/incidents/{incident_id}/notifications",
    summary="Get notifications for incident",
    description="Lists all simulated notifications triggered for a specific incident.",
)
@router.get(
    "/incidents/{incident_id}/notifications",
    summary="Get notifications for incident (alias)",
)
def get_incident_notifications(incident_id: str):
    """Retrieve simulated notifications for a given incident."""
    return repository.list_notifications(incident_id=incident_id)


class DirectRouteRequestSchema(BaseModel):
    incident_latitude: float = Field(..., description="Incident latitude")
    incident_longitude: float = Field(..., description="Incident longitude")
    ambulance_latitude: Optional[float] = Field(None, description="Optional custom ambulance latitude")
    ambulance_longitude: Optional[float] = Field(None, description="Optional custom ambulance longitude")
    hospital_latitude: Optional[float] = Field(None, description="Optional custom hospital latitude")
    hospital_longitude: Optional[float] = Field(None, description="Optional custom hospital longitude")


@router.post(
    "/api/v1/dispatch/route",
    summary="Calculate 2-leg emergency route",
    description="Calculates 2-leg ambulance response route via OSRM/OpenStreetMap with transparent fallback.",
)
def calculate_direct_route(req: DirectRouteRequestSchema) -> Dict[str, Any]:
    """Calculate 2-leg emergency ambulance response route for given coordinates."""
    from src.location.facility_registry import facility_registry
    
    # Resolve ambulance coordinates if not supplied
    amb_lat, amb_lon = req.ambulance_latitude, req.ambulance_longitude
    amb_name = "Assigned Ambulance Station"
    amb_id = "EMS-DISPATCH"
    if amb_lat is None or amb_lon is None:
        nearest_amb = facility_registry.match_nearest_ambulance(req.incident_latitude, req.incident_longitude)
        if nearest_amb:
            amb_lat = nearest_amb.get("latitude")
            amb_lon = nearest_amb.get("longitude")
            amb_name = nearest_amb.get("name", amb_name)
            amb_id = nearest_amb.get("facility_id", amb_id)

    # Resolve hospital coordinates if not supplied
    hosp_lat, hosp_lon = req.hospital_latitude, req.hospital_longitude
    hosp_name = "Destination Trauma Center"
    hosp_id = "HOSP-DISPATCH"
    if hosp_lat is None or hosp_lon is None:
        nearest_hosp = facility_registry.match_nearest_hospital(req.incident_latitude, req.incident_longitude)
        if nearest_hosp:
            hosp_lat = nearest_hosp.get("latitude")
            hosp_lon = nearest_hosp.get("longitude")
            hosp_name = nearest_hosp.get("name", hosp_name)
            hosp_id = nearest_hosp.get("facility_id", hosp_id)

    if amb_lat is None or amb_lon is None or hosp_lat is None or hosp_lon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unable to resolve ambulance and hospital coordinates for routing.",
        )

    all_facs = [f.model_dump() for f in facility_registry.list_facilities()]

    route_res = route_engine.plan_emergency_route(
        ambulance_lat=float(amb_lat),
        ambulance_lon=float(amb_lon),
        incident_lat=req.incident_latitude,
        incident_lon=req.incident_longitude,
        hospital_lat=float(hosp_lat),
        hospital_lon=float(hosp_lon),
        ambulance_id=amb_id,
        ambulance_name=amb_name,
        hospital_id=hosp_id,
        hospital_name=hosp_name,
        all_facilities=all_facs,
    )

    return route_res.to_dict()


class CorridorAnalysisRequestSchema(BaseModel):
    route_coordinates: List[List[float]] = Field(..., description="List of [lat, lon] points along route")
    corridor_width_meters: float = Field(default=400.0, description="Corridor buffer width in meters")
    incident_latitude: Optional[float] = Field(default=18.5204, description="Incident latitude")
    incident_longitude: Optional[float] = Field(default=73.8567, description="Incident longitude")


CorridorAnalysisRequestSchema.model_rebuild()


@router.post(
    "/api/v1/dispatch/corridor-analysis",
    summary="Analyze infrastructure along emergency route corridor",
    description="Identifies mapped police stations and traffic signals within corridor buffer via OpenStreetMap.",
)
def analyze_route_corridor(req: CorridorAnalysisRequestSchema) -> Dict[str, Any]:
    """Identify mapped police stations and traffic signals along emergency route corridor."""
    from src.dispatch.corridor_analysis import corridor_analyzer
    coords = [(float(c[0]), float(c[1])) for c in req.route_coordinates]
    res = corridor_analyzer.analyze_corridor(
        route_coords=coords,
        corridor_width_meters=req.corridor_width_meters,
        incident_lat=req.incident_latitude or 18.5204,
        incident_lon=req.incident_longitude or 73.8567,
    )
    return res.to_dict()

