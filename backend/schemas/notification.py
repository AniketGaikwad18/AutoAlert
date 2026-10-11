"""
Pydantic schemas for Simulated Emergency Facility Notifications (Stage 17).
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MatchFacilitiesRequestSchema(BaseModel):
    """Request payload for matching nearest emergency response facilities."""
    incident_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    facility_type: Optional[str] = Field(default=None, description="Filter by facility type e.g. hospital, police, ambulance")
    limit: int = Field(default=5, ge=1, le=20)


class FacilityMatchResultSchema(BaseModel):
    """Schema representing a facility matched to an incident with distance."""
    facility_id: str
    name: str
    type: str
    phone_contact: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = Field(default=None, description="Haversine distance in km")
    available: bool = True
    is_simulated: bool = True


class NotificationCreateSchema(BaseModel):
    """Request schema to trigger a simulated dispatch notification."""
    incident_id: str = Field(min_length=1)
    facility_id: str = Field(min_length=1)
    message: Optional[str] = Field(default="", description="Optional dispatch message text")


class NotificationStatusUpdateSchema(BaseModel):
    """Request schema for updating simulated notification status."""
    status: str = Field(description="Target status: pending, notified, acknowledged, responding, rejected, expired")
    reason: Optional[str] = Field(default="", description="Audit reason or note for status transition")


class NotificationResponseSchema(BaseModel):
    """Response payload schema representing a simulated notification dispatch."""
    notification_id: str
    incident_id: str
    facility_id: str
    facility_type: str
    facility_name: str
    status: str
    distance_km: Optional[float] = None
    message: Optional[str] = None
    is_simulated: bool = True
    created_at: str
    updated_at: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
