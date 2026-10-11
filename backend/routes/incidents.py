"""Incidents API route handlers for AutoAlert backend."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import IncidentRepository
from backend.schemas.incident import IncidentResponse, IncidentStatusUpdate
from src.core.incident import IncidentPackage

from backend.schemas.incident import IncidentResponse, IncidentStatusUpdate, IncidentPackageCreateSchema

router = APIRouter(tags=["incidents"])


def serialize_incident_model(model) -> IncidentResponse:
    """Map SQLAlchemy IncidentModel to API response schema."""
    return IncidentResponse(
        id=model.id,
        incident_id=model.id,
        incident_type=model.incident_type,
        camera_id=model.camera_id,
        timestamp=model.timestamp,
        confidence_score=model.confidence_score,
        verification_status=model.verification_status,
        notification_status=model.notification_status,
        involved_tracks=json.loads(model.involved_tracks_json or "[]"),
        reasons=json.loads(model.reasons_json or "[]"),
        signals=json.loads(model.signals_json or "{}"),
        location=json.loads(model.location_json) if model.location_json else None,
        evidence=json.loads(model.evidence_json) if model.evidence_json else None,
        plate_readings=json.loads(model.plate_readings_json or "[]"),
    )


@router.post("/api/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def receive_incident(package: IncidentPackageCreateSchema, db: Session = Depends(get_db)):
    """Ingest validated incident package from edge AI/IoT Box and trigger response coordinator."""
    try:
        from src.coordination.response_coordinator import ResponseCoordinator
        coordinator = ResponseCoordinator(simulation_mode=True)
        loc_desc = package.location.description if (package.location and package.location.description) else "Monitored Junction CCTV"
        t_stamp = str(package.timestamp) if package.timestamp else "2026-10-11T12:00:00Z"
        resp_data = coordinator.orchestrate_response(
            incident_id=package.incident_id,
            camera_id=package.camera_id,
            location_desc=loc_desc,
            initial_timestamp=t_stamp,
            is_demo=False
        )
        model = IncidentRepository.create(
            db,
            pkg=package,
            source_device="Raspberry Pi AI Box",
            mode="LIVE DEVICE",
            ambulance_status=resp_data["ambulance"]["status"],
            ambulance_unit=resp_data["ambulance"]["unit_id"],
            police_station_name=resp_data["police"]["station_name"],
            police_status=resp_data["police"]["status"],
            timeline_events=resp_data["timeline"]
        )
        return serialize_incident_model(model)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to persist incident package: {str(e)}"
        )


@router.get("/api/incidents", response_model=List[IncidentResponse])
@router.get("/api/v1/incidents", response_model=List[IncidentResponse])
def list_incidents(
    incident_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve verified incidents with optional filtering."""
    models = IncidentRepository.get_all(db, incident_type=incident_type, camera_id=camera_id, limit=limit)
    return [serialize_incident_model(m) for m in models]


@router.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
@router.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific incident."""
    model = IncidentRepository.get_by_id(db, incident_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )
    return serialize_incident_model(model)


@router.get("/api/incidents/{incident_id}/timeline")
@router.get("/api/v1/incidents/{incident_id}/timeline")
@router.post("/api/incidents/{incident_id}/timeline")
@router.post("/api/v1/incidents/{incident_id}/timeline")
def get_incident_timeline(incident_id: str, db: Session = Depends(get_db)):
    """Retrieve or generate chronological response timeline for an incident."""
    from src.dispatch.notification_service import notification_service
    records = notification_service.get_incident_timeline(incident_id)
    if not records:
        records = notification_service.create_incident_timeline(incident_id=incident_id)
    return [r.to_dict() for r in records]



@router.patch("/api/incidents/{incident_id}/status", response_model=IncidentResponse)
@router.patch("/api/v1/incidents/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: str,
    update: IncidentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update simulated notification state (e.g. pending, notified, acknowledged, responding)."""
    valid_states = {"pending", "notified", "acknowledged", "responding"}
    if update.notification_status not in valid_states:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{update.notification_status}'. Allowed states: {sorted(valid_states)}"
        )

    model = IncidentRepository.update_status(db, incident_id, update.notification_status)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )
    return serialize_incident_model(model)
