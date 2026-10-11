"""
API Endpoints for Emergency Facility Matching and SIMULATED Notifications (Phase 14).

NOTE: All notification dispatch operations, SMS logs, and facility routing
are strictly SIMULATED PROTOTYPE DATA. No real emergency calls or external APIs are executed.
Status explicitly indicates 'SIMULATED'.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.dispatch.matching import FacilityMatcher
from src.dispatch.notification import SimulatedNotification
from src.dispatch.notification_service import notification_service, NotificationRecord
from backend.schemas.notification import (
    MatchFacilitiesRequestSchema,
    FacilityMatchResultSchema,
    NotificationCreateSchema,
    NotificationStatusUpdateSchema,
    NotificationResponseSchema,
)
from backend.repository import repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications (Simulated)"])


class DirectNotificationRequest(BaseModel):
    """Request schema for direct simulated notification dispatch."""
    incident_id: str = Field(..., description="Target incident ID")
    recipient_type: str = Field(..., description="Target recipient type: 'ambulance', 'police', 'hospital', 'merchant'")
    recipient_name: Optional[str] = Field(None, description="Optional custom recipient facility or merchant name")
    message: Optional[str] = Field(None, description="Optional custom dispatch message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Optional contextual metadata")


class NotificationRecordSchema(BaseModel):
    """Response schema for a structured simulated notification."""
    notification_id: str
    incident_id: str
    recipient: str
    recipient_type: str
    timestamp: str
    status: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    is_simulated: bool = True


@router.post(
    "/match",
    response_model=List[FacilityMatchResultSchema],
    summary="Match nearest emergency facilities",
    description="Calculates Haversine distance from incident GPS coordinates to registered emergency facilities.",
)
def match_facilities(payload: MatchFacilitiesRequestSchema) -> List[FacilityMatchResultSchema]:
    """Rank emergency facilities by Haversine distance from incident location."""
    lat, lon = payload.latitude, payload.longitude

    if payload.incident_id and (lat is None or lon is None):
        incident = repository.get_incident(payload.incident_id)
        if incident and incident.location:
            lat = incident.location.latitude
            lon = incident.location.longitude

    all_facs = [f.model_dump() for f in repository.list_facilities()]
    matched = FacilityMatcher.match_facilities(
        incident_lat=lat,
        incident_lon=lon,
        facilities=all_facs,
        facility_type=payload.facility_type,
        limit=payload.limit,
    )
    return [FacilityMatchResultSchema(**m) for m in matched]


@router.post(
    "/dispatch",
    response_model=NotificationRecordSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch modular simulated notification",
    description="Dispatches a simulated notification to ambulance, police, hospital, or merchant.",
)
def dispatch_simulated_notification(payload: DirectNotificationRequest) -> NotificationRecordSchema:
    """Trigger a modular simulated notification dispatch (ambulance/police/hospital/merchant)."""
    rec_type = payload.recipient_type.lower()
    incident_id = payload.incident_id
    rec_name = payload.recipient_name
    msg = payload.message
    details = payload.details

    if rec_type == "ambulance":
        record = notification_service.notify_ambulance(
            incident_id=incident_id,
            recipient=rec_name or "Central EMS Ambulance Station (Simulated)",
            message=msg,
            details=details,
        )
    elif rec_type == "police":
        record = notification_service.notify_police(
            incident_id=incident_id,
            recipient=rec_name or "Shivajinagar Police Station (Simulated)",
            message=msg,
            details=details,
        )
    elif rec_type == "hospital":
        record = notification_service.notify_hospital(
            incident_id=incident_id,
            recipient=rec_name or "City Care Trauma Hospital (Simulated)",
            message=msg,
            details=details,
        )
    elif rec_type == "merchant":
        record = notification_service.notify_merchant(
            incident_id=incident_id,
            recipient=rec_name or "Store Manager / Operations (Simulated)",
            message=msg,
            details=details,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown recipient_type '{payload.recipient_type}'. Supported: ambulance, police, hospital, merchant.",
        )

    return NotificationRecordSchema(**record.to_dict())


@router.get(
    "/timeline",
    response_model=List[NotificationRecordSchema],
    summary="Get chronological notification timeline",
    description="Retrieve chronological notification records for an incident or all dispatches.",
)
def get_notification_timeline(
    incident_id: Optional[str] = Query(None, description="Optional incident ID filter"),
    recipient_type: Optional[str] = Query(None, description="Optional recipient type filter"),
) -> List[NotificationRecordSchema]:
    """Retrieve chronological notification timeline."""
    records = notification_service.list_all_notifications(incident_id=incident_id, recipient_type=recipient_type)
    return [NotificationRecordSchema(**r.to_dict()) for r in records]


@router.post(
    "",
    response_model=NotificationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger simulated emergency dispatch notification",
    description="Creates a simulated notification record sent to an emergency response facility.",
)
def create_simulated_notification(
    payload: NotificationCreateSchema,
) -> NotificationResponseSchema:
    """Create and trigger a simulated emergency response notification."""
    facilities = repository.list_facilities()
    target_facility = next((f for f in facilities if f.facility_id == payload.facility_id), None)

    if not target_facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility with ID '{payload.facility_id}' not found.",
        )

    incident = repository.get_incident(payload.incident_id)
    distance_km = None
    if incident and incident.location and incident.location.latitude and incident.location.longitude and target_facility.latitude and target_facility.longitude:
        from src.dispatch.matching import haversine_distance
        distance_km = haversine_distance(
            incident.location.latitude,
            incident.location.longitude,
            target_facility.latitude,
            target_facility.longitude,
        )

    sim_notif = SimulatedNotification(
        incident_id=payload.incident_id,
        facility_id=payload.facility_id,
        facility_type=target_facility.type,
        facility_name=target_facility.name,
        status="notified",
        distance_km=distance_km,
        message=payload.message or f"SIMULATED EMERGENCY DISPATCH: Incident {payload.incident_id} reported.",
        is_simulated=True,
    )
    sim_notif.history.append({
        "previous_status": "pending",
        "new_status": "notified",
        "timestamp": sim_notif.created_at,
        "reason": "Simulated dispatch notification sent to facility",
    })

    # Also record in NotificationService
    if target_facility.type == "ambulance":
        notification_service.notify_ambulance(
            incident_id=payload.incident_id,
            recipient=target_facility.name,
            message=sim_notif.message,
            details={"facility_id": target_facility.facility_id, "distance_km": distance_km},
        )
    elif target_facility.type == "police":
        notification_service.notify_police(
            incident_id=payload.incident_id,
            recipient=target_facility.name,
            message=sim_notif.message,
            details={"facility_id": target_facility.facility_id, "distance_km": distance_km},
        )
    elif target_facility.type == "hospital":
        notification_service.notify_hospital(
            incident_id=payload.incident_id,
            recipient=target_facility.name,
            message=sim_notif.message,
            details={"facility_id": target_facility.facility_id, "distance_km": distance_km},
        )

    schema = NotificationResponseSchema(
        notification_id=sim_notif.notification_id,
        incident_id=sim_notif.incident_id,
        facility_id=sim_notif.facility_id,
        facility_type=sim_notif.facility_type,
        facility_name=sim_notif.facility_name,
        status=sim_notif.status,
        distance_km=sim_notif.distance_km,
        message=sim_notif.message,
        is_simulated=True,
        created_at=sim_notif.created_at,
        updated_at=sim_notif.updated_at,
        history=sim_notif.history,
    )

    return repository.add_notification(schema)


@router.patch(
    "/{notification_id}/status",
    response_model=NotificationResponseSchema,
    summary="Update simulated notification dispatch status",
    description="Updates dispatch status e.g., acknowledged, responding, rejected.",
)
def update_notification_status(
    notification_id: str,
    payload: NotificationStatusUpdateSchema,
) -> NotificationResponseSchema:
    """Update status transition for a simulated notification dispatch."""
    updated = repository.update_notification_status(
        notification_id=notification_id,
        new_status=payload.status,
        reason=payload.reason or f"Status changed to {payload.status}",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification ID '{notification_id}' not found.",
        )
    return updated


@router.get(
    "",
    response_model=List[NotificationResponseSchema],
    summary="List simulated notification dispatches",
    description="Retrieve list of simulated notification records with optional filtering.",
)
def list_notifications(
    incident_id: Optional[str] = Query(default=None, description="Filter by incident_id"),
    facility_id: Optional[str] = Query(default=None, description="Filter by facility_id"),
) -> List[NotificationResponseSchema]:
    """List simulated emergency response notifications."""
    return repository.list_notifications(incident_id=incident_id, facility_id=facility_id)


class IncidentNotificationTransitionRequest(BaseModel):
    stage: str = Field(..., description="Target lifecycle stage: draft, prepared, sent, delivered, acknowledged, response_initiated")
    message: Optional[str] = Field(None, description="Optional custom or regenerated notification message")
    event_details: Optional[str] = Field(None, description="Optional detail text for timeline")
    is_simulated: bool = Field(True, description="Whether this transition is simulated")


class IncidentNotificationStatusResponse(BaseModel):
    incident_id: str
    stage: str
    police_status: str
    message: Optional[str] = None
    police_station_name: str
    is_simulated: bool = True
    history: List[Dict[str, Any]] = Field(default_factory=list)


ALLOWED_TRANSITIONS = {
    "pending": ["prepared", "draft"],
    "draft": ["prepared"],
    "prepared": ["sent", "draft"],
    "sent": ["delivered", "prepared"],
    "delivered": ["acknowledged", "prepared"],
    "acknowledged": ["response_initiated", "delivered", "prepared"],
    "response_initiated": ["prepared", "draft"],
}


@router.get(
    "/incident/{incident_id}",
    response_model=IncidentNotificationStatusResponse,
    summary="Get incident notification lifecycle status",
    description="Retrieve current authoritative notification lifecycle state, message, and history for an incident.",
)
def get_incident_notification_status(incident_id: str) -> IncidentNotificationStatusResponse:
    from backend.database.database import SessionLocal
    from backend.database.repositories import IncidentRepository
    import json

    db = SessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, incident_id)
        if not inc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
        history = json.loads(getattr(inc, "notification_history_json", None) or "[]")
        return IncidentNotificationStatusResponse(
            incident_id=inc.id,
            stage=inc.notification_status or "prepared",
            police_status=inc.police_status or "Notification Prepared [SIMULATED]",
            message=getattr(inc, "notification_message", None),
            police_station_name=inc.police_station_name or "Shivajinagar Police Station",
            is_simulated=True,
            history=history,
        )
    finally:
        db.close()


@router.post(
    "/incident/{incident_id}/transition",
    response_model=IncidentNotificationStatusResponse,
    summary="Transition incident notification lifecycle stage",
    description="Execute an authoritative state transition for emergency notification lifecycle.",
)
def transition_incident_notification(
    incident_id: str,
    payload: IncidentNotificationTransitionRequest,
) -> IncidentNotificationStatusResponse:
    from backend.database.database import SessionLocal
    from backend.database.repositories import IncidentRepository
    import json

    target_stage = payload.stage.lower()
    if target_stage not in ("draft", "prepared", "sent", "delivered", "acknowledged", "response_initiated"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage '{payload.stage}'. Must be one of: draft, prepared, sent, delivered, acknowledged, response_initiated.",
        )

    db = SessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, incident_id)
        if not inc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")

        current_stage = (inc.notification_status or "draft").lower()
        allowed = ALLOWED_TRANSITIONS.get(current_stage, [])
        if target_stage != current_stage and target_stage not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from '{current_stage}' to '{target_stage}'. Allowed: {allowed}.",
            )

        title_map = {
            "prepared": f"Police coordination notification prepared [{incident_id}] [SIMULATED]",
            "sent": f"Police notification transmitted to {inc.police_station_name} [SIMULATED]",
            "delivered": f"Police notification delivered to {inc.police_station_name} terminal [SIMULATED]",
            "acknowledged": "Police desk officer acknowledges notification [SIMULATED]",
            "response_initiated": f"Police patrol response initiated [{incident_id}] [SIMULATED]",
        }
        event_title = title_map.get(target_stage)

        updated = IncidentRepository.update_notification_lifecycle(
            db=db,
            incident_id=incident_id,
            lifecycle_stage=target_stage,
            message=payload.message,
            event_title=event_title,
            event_details=payload.event_details,
            is_simulated=payload.is_simulated,
        )

        history = json.loads(getattr(updated, "notification_history_json", None) or "[]")
        return IncidentNotificationStatusResponse(
            incident_id=updated.id,
            stage=updated.notification_status,
            police_status=updated.police_status,
            message=getattr(updated, "notification_message", None),
            police_station_name=updated.police_station_name,
            is_simulated=payload.is_simulated,
            history=history,
        )
    finally:
        db.close()


@router.post(
    "/incident/{incident_id}/reset",
    response_model=IncidentNotificationStatusResponse,
    summary="Reset incident notification lifecycle demo",
    description="Resets simulated notification lifecycle back to prepared state.",
)
def reset_incident_notification(incident_id: str) -> IncidentNotificationStatusResponse:
    from backend.database.database import SessionLocal
    from backend.database.repositories import IncidentRepository
    import json

    db = SessionLocal()
    try:
        updated = IncidentRepository.reset_notification_lifecycle(db, incident_id, target_stage="prepared")
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
        history = json.loads(getattr(updated, "notification_history_json", None) or "[]")
        return IncidentNotificationStatusResponse(
            incident_id=updated.id,
            stage=updated.notification_status,
            police_status=updated.police_status,
            message=getattr(updated, "notification_message", None),
            police_station_name=updated.police_station_name,
            is_simulated=True,
            history=history,
        )
    finally:
        db.close()
