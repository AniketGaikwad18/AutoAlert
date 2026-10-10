"""Camera registry route handlers for AutoAlert backend."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.repositories import CameraRepository
from backend.schemas.camera import CameraResponse, CameraCreate

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=List[CameraResponse])
def list_cameras(db: Session = Depends(get_db)):
    """Retrieve all configured camera nodes."""
    return CameraRepository.get_all(db)


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Retrieve camera metadata by ID."""
    cam = CameraRepository.get_by_id(db, camera_id)
    if not cam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found."
        )
    return cam


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def register_camera(camera: CameraCreate, db: Session = Depends(get_db)):
    """Register or update a camera configuration node."""
    return CameraRepository.create(db, camera.model_dump())
