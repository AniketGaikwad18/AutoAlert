"""Emergency response facility route handlers for AutoAlert backend."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import FacilityRepository
from backend.schemas.facility import FacilityResponse
from src.location.facility_matcher import match_nearest_facilities

router = APIRouter(tags=["facilities"])


@router.get("/api/facilities", response_model=List[FacilityResponse])
@router.get("/api/v1/facilities", response_model=List[FacilityResponse])
def list_facilities(
    type: Optional[str] = Query(None, description="Filter by type: hospital, ambulance, police"),
    db: Session = Depends(get_db)
):
    """Retrieve simulated emergency response facilities."""
    return FacilityRepository.get_all(db, facility_type=type)


@router.get("/api/facilities/nearest")
@router.get("/api/v1/facilities/nearest")
@router.get("/api/facilities/match")
@router.get("/api/v1/facilities/match")
@router.post("/api/facilities/match")
@router.post("/api/v1/facilities/match")
async def get_nearest_facilities(
    latitude: Optional[float] = Query(None, description="Incident latitude coordinate"),
    longitude: Optional[float] = Query(None, description="Incident longitude coordinate"),
    req_body: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Find the nearest simulated hospital, ambulance unit, and police station using Haversine calculation."""
    if req_body and isinstance(req_body, dict):
        if latitude is None:
            latitude = req_body.get("latitude") or req_body.get("incident_latitude")
        if longitude is None:
            longitude = req_body.get("longitude") or req_body.get("incident_longitude")

    lat = float(latitude if latitude is not None else 18.5204)
    lon = float(longitude if longitude is not None else 73.8567)

    all_facs = FacilityRepository.get_all(db)
    raw_facs = [
        {
            "id": f.id,
            "name": f.name,
            "type": f.type,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "phone": f.phone,
            "status": f.status,
        }
        for f in all_facs
    ]

    matched = match_nearest_facilities(lat, lon, raw_facs)
    amb = matched.get("ambulance", [None])[0] if matched.get("ambulance") else None
    hosp = matched.get("hospital", [None])[0] if matched.get("hospital") else None
    pol = matched.get("police", [None])[0] if matched.get("police") else None
    all_matched = []
    for flist in matched.values():
        if isinstance(flist, list):
            all_matched.extend(flist)

    return {
        "status": "success",
        "incident_coordinates": {"latitude": lat, "longitude": lon},
        "distance_metric": "Haversine formula (great-circle distance in kilometers)",
        "disclaimer": "PROTOTYPE / SIMULATED DISPATCH: No real emergency calls or dispatches are performed.",
        "matched_facilities": matched,
        "nearest_ambulance": amb,
        "nearest_hospital": hosp,
        "nearest_police": pol,
        "nearby_facilities": all_matched,
    }
