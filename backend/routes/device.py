"""IoT device (Raspberry Pi AI Box) telemetry and heartbeat routes."""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import DeviceRepository

router = APIRouter(prefix="/api/device", tags=["device"])


class HeartbeatPayload(BaseModel):
    device_id: str = "PI-AI-BOX-01"
    device_name: str = "Raspberry Pi 5 AI Box"
    ip_address: str = "192.168.1.105"
    telemetry: Optional[Dict[str, Any]] = None


@router.post("/heartbeat")
def receive_heartbeat(payload: HeartbeatPayload, db: Session = Depends(get_db)):
    """Record heartbeat ping from field Raspberry Pi AI Box."""
    dev = DeviceRepository.record_heartbeat(
        db,
        device_id=payload.device_id,
        device_name=payload.device_name,
        ip_address=payload.ip_address,
        telemetry=payload.telemetry
    )
    return {
        "status": "ok",
        "device_id": dev.device_id,
        "is_connected": True,
        "last_heartbeat": dev.last_heartbeat.isoformat()
    }


@router.get("/status")
def get_device_status(device_id: str = "PI-AI-BOX-01", db: Session = Depends(get_db)):
    """Check connectivity status and freshness of Raspberry Pi AI Box."""
    return DeviceRepository.get_status(db, device_id=device_id)
