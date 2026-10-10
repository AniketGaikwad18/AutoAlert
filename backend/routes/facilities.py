"""Emergency response facility route handlers for AutoAlert backend."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import FacilityRepository
from backend.schemas.facility import FacilityResponse
from src.location.facility_matcher import match_nearest_facilities

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=List[FacilityResponse])
def list_facilities(
    type: Optional[str] = Query(None, description="Filter by type: hospital, ambulance, police"),
    db: Session = Depends(get_db)
):
    """Retrieve simulated emergency response facilities."""
    return FacilityRepository.get_all(db, facility_type=type)


@router.get("/nearest")
def get_nearest_facilities(
    latitude: float = Query(..., description="Incident latitude coordinate"),
    longitude: float = Query(..., description="Incident longitude coordinate"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Find the nearest simulated hospital, ambulance unit, and police station using Haversine calculation."""
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

    matched = match_nearest_facilities(latitude, longitude, raw_facs)
    return {
        "status": "success",
        "incident_coordinates": {"latitude": latitude, "longitude": longitude},
        "distance_metric": "Haversine formula (great-circle distance in kilometers)",
        "disclaimer": "PROTOTYPE / SIMULATED DISPATCH: No real emergency calls or dispatches are performed.",
        "matched_facilities": matched,
    }
