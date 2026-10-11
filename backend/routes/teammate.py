"""
FastAPI Endpoints for AutoAlert AI Teammate Orchestration Layer.

Exposes the 6-stage operational workflow:
  OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.teammate.orchestrator import ai_teammate, AITeammateOrchestrator
from backend.repository import repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teammate", tags=["AI Teammate Orchestrator"])


class OrchestrateIncidentRequest(BaseModel):
    incident_id: str = Field(..., description="Target verified incident ID to orchestrate")
    camera_id: Optional[str] = Field(None, description="Optional camera ID override")
    merchant_name: Optional[str] = Field(None, description="Optional merchant name override")


class TeammateBriefingRequest(BaseModel):
    incident_id: str = Field(..., description="Target incident ID")


@router.post(
    "/orchestrate",
    summary="Execute AI Teammate orchestration workflow",
    description="Runs the deterministic DECIDE ➔ ACT ➔ REPORT lifecycle on a verified incident package.",
)
def orchestrate_incident(req: OrchestrateIncidentRequest) -> Dict[str, Any]:
    """Execute AI Teammate orchestration on verified incident."""
    res = ai_teammate.orchestrate_verified_incident(
        incident_id=req.incident_id,
        camera_id=req.camera_id,
        custom_merchant_name=req.merchant_name,
    )
    if not res.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=res.error_message or "Orchestration failed.",
        )
    return res.to_dict()


@router.get(
    "/status/{incident_id}",
    summary="Get AI Teammate orchestration audit record",
    description="Retrieve the multi-stage execution audit trail and structured summary for an incident.",
)
def get_teammate_status(incident_id: str) -> Dict[str, Any]:
    """Retrieve stored orchestration record for an incident."""
    res = ai_teammate.get_orchestration_history(incident_id)
    if not res:
        # Generate on demand if incident exists in repository
        inc = repository.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No orchestration record or incident found for '{incident_id}'.",
            )
        res = ai_teammate.orchestrate_verified_incident(incident_id=incident_id)
    return res.to_dict()


@router.post(
    "/briefing",
    summary="Synthesize grounded CAD and Merchant briefings",
    description="Generates fact-based, non-hallucinatory operational briefings from structured incident data.",
)
def get_teammate_briefing(req: TeammateBriefingRequest) -> Dict[str, Any]:
    """Generate grounded executive operational briefing for an incident."""
    res = ai_teammate.orchestrate_verified_incident(incident_id=req.incident_id)
    if not res.success or not res.summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not generate briefing for incident '{req.incident_id}'.",
        )
    return {
        "incident_id": req.incident_id,
        "executive_briefing": res.summary.executive_briefing,
        "merchant_advisory": res.summary.merchant_advisory,
        "is_simulated": True,
    }
