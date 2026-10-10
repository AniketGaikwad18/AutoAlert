"""Repository access layer decoupling database operations from HTTP routes."""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from sqlalchemy.orm import Session
from backend.database.models import IncidentModel, CameraModel, FacilityModel
from src.core.incident import IncidentPackage


class IncidentRepository:
    """Database repository for incidents."""

    @staticmethod
    def create(db: Session, pkg: IncidentPackage) -> IncidentModel:
        model = IncidentModel(
            id=pkg.incident_id,
            incident_type=pkg.incident_type,
            camera_id=pkg.camera_id,
            timestamp=pkg.timestamp,
            confidence_score=pkg.confidence_score,
            verification_status=pkg.verification_status,
            notification_status="pending",
            involved_tracks_json=json.dumps(pkg.involved_track_ids),
            reasons_json=json.dumps(pkg.reasons),
            signals_json=json.dumps(pkg.signals),
            location_json=json.dumps(pkg.location.model_dump()) if pkg.location else None,
            evidence_json=json.dumps(pkg.evidence.model_dump()) if pkg.evidence else None,
            plate_readings_json=json.dumps([p.model_dump() for p in pkg.plate_readings]),
        )
        persisted = db.merge(model)
        db.commit()
        db.refresh(persisted)
        return persisted

    @staticmethod
    def get_by_id(db: Session, incident_id: str) -> Optional[IncidentModel]:
        return db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()

    @staticmethod
    def get_all(
        db: Session,
        incident_type: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 100
    ) -> List[IncidentModel]:
        query = db.query(IncidentModel)
        if incident_type:
            query = query.filter(IncidentModel.incident_type == incident_type)
        if camera_id:
            query = query.filter(IncidentModel.camera_id == camera_id)
        return query.order_by(IncidentModel.created_at.desc()).limit(limit).all()

    @staticmethod
    def update_status(db: Session, incident_id: str, notification_status: str) -> Optional[IncidentModel]:
        model = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if model:
            model.notification_status = notification_status
            db.commit()
            db.refresh(model)
        return model


class CameraRepository:
    """Database repository for cameras."""

    @staticmethod
    def get_all(db: Session) -> List[CameraModel]:
        return db.query(CameraModel).all()

    @staticmethod
    def get_by_id(db: Session, camera_id: str) -> Optional[CameraModel]:
        return db.query(CameraModel).filter(CameraModel.id == camera_id).first()

    @staticmethod
    def create(db: Session, cam_data: Dict[str, Any]) -> CameraModel:
        model = CameraModel(
            id=cam_data["id"],
            name=cam_data["name"],
            source=cam_data["source"],
            latitude=cam_data.get("latitude"),
            longitude=cam_data.get("longitude"),
            location_desc=cam_data.get("location_desc", ""),
            is_active=cam_data.get("is_active", True)
        )
        persisted = db.merge(model)
        db.commit()
        db.refresh(persisted)
        return persisted


class FacilityRepository:
    """Database repository for emergency response facilities."""

    @staticmethod
    def get_all(db: Session, facility_type: Optional[str] = None) -> List[FacilityModel]:
        query = db.query(FacilityModel)
        if facility_type:
            query = query.filter(FacilityModel.type == facility_type)
        return query.all()

    @staticmethod
    def create(db: Session, fac_data: Dict[str, Any]) -> FacilityModel:
        model = FacilityModel(
            id=fac_data["id"],
            name=fac_data["name"],
            type=fac_data["type"],
            latitude=fac_data["latitude"],
            longitude=fac_data["longitude"],
            phone=fac_data.get("phone", ""),
            status=fac_data.get("status", "active"),
            extra_info_json=json.dumps(fac_data.get("extra", {}))
        )
        persisted = db.merge(model)
        db.commit()
        db.refresh(persisted)
        return persisted


def seed_defaults_if_empty(db: Session) -> None:
    """Seed camera and simulated facility tables from YAML configs if tables are empty."""
    # Seed cameras
    if db.query(CameraModel).count() == 0:
        cam_file = Path("config/cameras.yaml")
        if cam_file.exists():
            with open(cam_file, "r", encoding="utf-8") as f:
                c_data = yaml.safe_load(f) or {}
            for c in c_data.get("cameras", []):
                loc = c.get("location", {})
                CameraRepository.create(db, {
                    "id": c["id"],
                    "name": c["name"],
                    "source": c["source"],
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                    "location_desc": loc.get("description", ""),
                    "is_active": c.get("active", True),
                })

    # Seed facilities
    if db.query(FacilityModel).count() == 0:
        fac_file = Path("config/facilities.yaml")
        if fac_file.exists():
            with open(fac_file, "r", encoding="utf-8") as f:
                f_data = yaml.safe_load(f) or {}
            for fac in f_data.get("facilities", []):
                FacilityRepository.create(db, {
                    "id": fac["id"],
                    "name": fac["name"],
                    "type": fac["type"],
                    "latitude": fac["latitude"],
                    "longitude": fac["longitude"],
                    "phone": fac.get("phone", ""),
                    "status": fac.get("status", "active"),
                })
