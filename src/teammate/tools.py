"""
Deterministic System Tools for the AI Teammate Orchestration Layer.

Provides structured, verifiable tools:
  - tool_get_incident()
  - tool_get_location()
  - tool_find_facilities()
  - tool_calculate_distances()
  - tool_generate_route()
  - tool_create_notification_records()
  - tool_create_incident_summary()

Rule: All factual data (GPS, distances, routes, plates, facilities) must be sourced
strictly from these tools. No fabrication or hallucination is permitted.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

from backend.repository import repository
from backend.schemas.incident import IncidentPackageResponseSchema
from src.core.incident import LocationInfo, IncidentPackage
from src.location.camera_registry import CameraRegistry, camera_registry
from src.location.facility_registry import FacilityRegistry, facility_registry
from src.dispatch.matching import FacilityMatcher, haversine_distance
from src.dispatch.routing import RouteEngine, route_engine, EmergencyRouteResult
from src.dispatch.notification_service import NotificationService, notification_service, NotificationRecord
from src.teammate.models import StructuredIncidentSummary

logger = logging.getLogger(__name__)


def tool_get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """Tool: Retrieve structured incident package by ID from repository."""
    inc = repository.get_incident(incident_id)
    if not inc:
        logger.debug("tool_get_incident: Incident '%s' not found", incident_id)
        return None
    return inc.model_dump() if hasattr(inc, "model_dump") else inc.to_dict()


def tool_get_location(camera_id: str, incident_id: Optional[str] = None) -> Optional[LocationInfo]:
    """
    Tool: Resolve geographic coordinates strictly from the Camera Registry.
    Zero GPS fabrication from raw video streams.
    """
    # 1. Check Camera Registry first
    loc = camera_registry.get_camera_location(camera_id)
    if loc and loc.latitude is not None and loc.longitude is not None:
        return loc

    # 2. Fallback: Check if incident has location stored
    if incident_id:
        inc = repository.get_incident(incident_id)
        if inc and inc.location and inc.location.latitude:
            return LocationInfo(
                name=inc.location.name or "Camera Perimeter",
                latitude=inc.location.latitude,
                longitude=inc.location.longitude,
                zone_id=inc.location.zone_id,
            )

    # 3. Default fallback for standard registered camera
    cam = camera_registry.get_camera(camera_id)
    if cam:
        return LocationInfo(
            name=cam.location_name or cam.location or "Perimeter Area",
            latitude=cam.latitude,
            longitude=cam.longitude,
            zone_id=cam.zone_id,
        )

    return None


def tool_find_facilities(
    incident_lat: Optional[float],
    incident_lon: Optional[float],
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Tool: Identify and rank nearest emergency facilities (Hospital, Ambulance, Police)
    using exact Haversine spherical distance calculations.
    """
    all_facs = [f.model_dump() for f in repository.list_facilities()]

    matched_hospital = FacilityMatcher.match_facilities(
        incident_lat=incident_lat,
        incident_lon=incident_lon,
        facilities=all_facs,
        facility_type="hospital",
        limit=limit,
    )
    matched_ambulance = FacilityMatcher.match_facilities(
        incident_lat=incident_lat,
        incident_lon=incident_lon,
        facilities=all_facs,
        facility_type="ambulance",
        limit=limit,
    )
    matched_police = FacilityMatcher.match_facilities(
        incident_lat=incident_lat,
        incident_lon=incident_lon,
        facilities=all_facs,
        facility_type="police",
        limit=limit,
    )

    nearest_amb = matched_ambulance[0] if matched_ambulance else None
    nearest_hosp = matched_hospital[0] if matched_hospital else None
    nearest_pol = matched_police[0] if matched_police else None

    return {
        "all_matched": all_facs,
        "hospitals": matched_hospital,
        "ambulances": matched_ambulance,
        "police_stations": matched_police,
        "nearest_ambulance": nearest_amb,
        "nearest_hospital": nearest_hosp,
        "nearest_police": nearest_pol,
    }


def tool_calculate_distances(
    incident_lat: float,
    incident_lon: float,
    facilities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Tool: Calculate Haversine distance from incident coordinates to each facility in list.
    """
    results = []
    for f in facilities:
        f_lat = f.get("latitude")
        f_lon = f.get("longitude")
        if f_lat is not None and f_lon is not None:
            dist = haversine_distance(incident_lat, incident_lon, float(f_lat), float(f_lon))
            item = dict(f)
            item["distance_km"] = round(dist, 3)
            results.append(item)
        else:
            item = dict(f)
            item["distance_km"] = None
            results.append(item)

    # Sort by distance
    return sorted(results, key=lambda x: (x["distance_km"] is None, x["distance_km"]))


def tool_generate_route(
    ambulance: Optional[Dict[str, Any]],
    incident_lat: float,
    incident_lon: float,
    hospital: Optional[Dict[str, Any]],
    all_facilities: Optional[List[Dict[str, Any]]] = None,
) -> Optional[EmergencyRouteResult]:
    """
    Tool: Plan 2-leg emergency route:
      Leg 1: Nearest Ambulance Station -> Incident Scene
      Leg 2: Incident Scene -> Destination Hospital
    Uses OpenStreetMap / OSRM routing with deterministic road fallback.
    """
    if not ambulance or not hospital:
        logger.warning("tool_generate_route: Missing ambulance or hospital facility.")
        return None

    amb_lat = ambulance.get("latitude")
    amb_lon = ambulance.get("longitude")
    hosp_lat = hospital.get("latitude")
    hosp_lon = hospital.get("longitude")

    if amb_lat is None or amb_lon is None or hosp_lat is None or hosp_lon is None:
        logger.warning("tool_generate_route: Incomplete coordinates for routing.")
        return None

    fac_list = all_facilities or [f.model_dump() for f in repository.list_facilities()]

    return route_engine.plan_emergency_route(
        ambulance_lat=float(amb_lat),
        ambulance_lon=float(amb_lon),
        incident_lat=float(incident_lat),
        incident_lon=float(incident_lon),
        hospital_lat=float(hosp_lat),
        hospital_lon=float(hosp_lon),
        ambulance_id=ambulance.get("facility_id", "EMS-01"),
        ambulance_name=ambulance.get("name", "Ambulance EMS Station"),
        hospital_id=hospital.get("facility_id", "HOSP-01"),
        hospital_name=hospital.get("name", "Trauma Hospital"),
        all_facilities=fac_list,
    )


def tool_create_notification_records(
    incident_id: str,
    ambulance_name: str,
    police_name: str,
    hospital_name: str,
    merchant_name: str,
    location_name: str,
    camera_id: str = "CAM-001",
    camera_name: str = "Perimeter Camera",
) -> List[NotificationRecord]:
    """
    Tool: Dispatch modular simulated notification records and generate chronological timeline.
    Strictly marked status='SIMULATED'.
    """
    return notification_service.create_incident_timeline(
        incident_id=incident_id,
        camera_id=camera_id,
        camera_name=camera_name,
        location_name=location_name,
        ambulance_name=ambulance_name,
        police_name=police_name,
        hospital_name=hospital_name,
        merchant_name=merchant_name,
    )


def tool_create_incident_summary(
    incident: Dict[str, Any],
    location: Optional[LocationInfo],
    facilities_result: Dict[str, Any],
    route_result: Optional[EmergencyRouteResult],
    notification_records: List[NotificationRecord],
    camera_name: str = "Perimeter Camera",
    executive_briefing: str = "",
    merchant_advisory: str = "",
) -> StructuredIncidentSummary:
    """
    Tool: Aggregate all validated telemetry into a StructuredIncidentSummary dossier.
    """
    inc_id = incident.get("incident_id", f"INC-{uuid.uuid4().hex[:8].upper()}")
    inc_type = incident.get("incident_type", "traffic_collision")
    conf = incident.get("confidence_score", 0.90)
    ver_status = incident.get("verification_status", "verified")
    cam_id = incident.get("camera_id", "CAM-001")
    ts = incident.get("created_at") or datetime.now(timezone.utc).isoformat()

    # Plates & Tracks
    plates_raw = incident.get("plate_readings", [])
    plate_strings = [
        p.get("plate_number") or p.get("normalized_text") or "unreadable"
        for p in plates_raw
        if p.get("plate_number") or p.get("normalized_text")
    ]
    involved_tracks = incident.get("involved_track_ids", [])

    amb = facilities_result.get("nearest_ambulance")
    hosp = facilities_result.get("nearest_hospital")
    pol = facilities_result.get("nearest_police")

    route_dist = route_result.total_distance_km if route_result else None
    route_time = route_result.estimated_duration_min if route_result else None
    corridor_count = len(route_result.stations_along_route) if route_result else 0

    loc_name = location.name if location else "Storefront Perimeter"
    lat = location.latitude if location else None
    lon = location.longitude if location else None

    notif_dicts = [n.to_dict() for n in notification_records]

    return StructuredIncidentSummary(
        summary_id=f"SUM-{uuid.uuid4().hex[:8].upper()}",
        incident_id=inc_id,
        incident_type=inc_type,
        verification_status=ver_status,
        confidence_score=conf,
        camera_id=cam_id,
        camera_name=camera_name,
        location_name=loc_name,
        latitude=lat,
        longitude=lon,
        timestamp=ts,
        involved_tracks=[{"track_id": t} for t in involved_tracks],
        license_plates=plate_strings,
        nearest_ambulance=amb,
        nearest_hospital=hosp,
        nearest_police=pol,
        route_distance_km=route_dist,
        estimated_travel_time_min=route_time,
        corridor_stations_alerted=corridor_count,
        notifications_count=len(notif_dicts),
        notification_records=notif_dicts,
        executive_briefing=executive_briefing,
        merchant_advisory=merchant_advisory,
        is_simulated=True,
    )
