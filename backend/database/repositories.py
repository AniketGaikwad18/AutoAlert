"""Repository access layer decoupling database operations from HTTP routes."""

import uuid
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from backend.database.models import IncidentModel, CameraModel, FacilityModel, DeviceModel
from src.core.incident import IncidentPackage
from backend.schemas.camera import CameraSchema
from backend.schemas.facility import FacilitySchema
from backend.schemas.incident import (
    LocationSchema,
    PlateReadingSchema,
    IncidentPackageCreateSchema,
    IncidentPackageResponseSchema,
)



class IncidentRepository:
    """Database repository for incidents."""

    @staticmethod
    def create(
        db: Session,
        pkg: IncidentPackage,
        source_device: str = "Raspberry Pi AI Box",
        mode: str = "DEMO",
        ambulance_status: str = "Awaiting Dispatch",
        ambulance_unit: str = "108 Fast Response Unit #4",
        police_station_name: str = "Shivajinagar Central Police Headquarters",
        police_status: str = "Notification Pending",
        timeline_events: Optional[List[Dict[str, Any]]] = None
    ) -> IncidentModel:
        involved_tracks = getattr(pkg, "involved_track_ids", getattr(pkg, "involved_tracks", []))
        reasons = getattr(pkg, "reasons", [])
        signals = getattr(pkg, "signals", getattr(pkg, "reason_metadata", {}))

        loc_val = getattr(pkg, "location", None)
        if loc_val:
            loc_dict = loc_val.model_dump() if hasattr(loc_val, "model_dump") else dict(loc_val)
            loc_json = json.dumps(loc_dict)
        else:
            loc_json = None

        if hasattr(pkg, "evidence") and pkg.evidence:
            ev_dict = pkg.evidence.model_dump() if hasattr(pkg.evidence, "model_dump") else dict(pkg.evidence)
            ev_json = json.dumps(ev_dict)
        elif hasattr(pkg, "evidence_frames"):
            ev_json = json.dumps({"key_frames": getattr(pkg, "evidence_frames", []), "video_clip": getattr(pkg, "evidence_video_path", None)})
        else:
            ev_json = None

        plates_val = getattr(pkg, "plate_readings", [])
        plates_json = json.dumps([p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in plates_val])

        model = IncidentModel(
            id=getattr(pkg, "incident_id", getattr(pkg, "id", "")),
            incident_type=pkg.incident_type,
            camera_id=pkg.camera_id,
            timestamp=str(pkg.timestamp),
            confidence_score=float(pkg.confidence_score),
            verification_status=getattr(pkg, "verification_status", "verified"),
            notification_status=getattr(pkg, "notification_status", "pending"),
            involved_tracks_json=json.dumps(involved_tracks),
            reasons_json=json.dumps(reasons),
            signals_json=json.dumps(signals),
            location_json=loc_json,
            evidence_json=ev_json,
            plate_readings_json=plates_json,
            source_device=source_device,
            mode=mode,
            ambulance_status=ambulance_status,
            ambulance_unit=ambulance_unit,
            police_station_name=police_station_name,
            police_status=police_status,
            timeline_events_json=json.dumps(timeline_events or []),
        )
        persisted = db.merge(model)
        db.commit()
        db.refresh(persisted)
        return persisted

    @staticmethod
    def get_by_id(db: Session, incident_id: str) -> Optional[IncidentModel]:
        return db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()

    @staticmethod
    def get_latest(db: Session) -> Optional[IncidentModel]:
        return db.query(IncidentModel).order_by(IncidentModel.created_at.desc()).first()

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
    def update_response_state(
        db: Session,
        incident_id: str,
        ambulance_status: Optional[str] = None,
        ambulance_dispatched_at: Optional[str] = None,
        police_status: Optional[str] = None,
        police_notified_at: Optional[str] = None,
        timeline_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[IncidentModel]:
        model = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if model:
            if ambulance_status:
                model.ambulance_status = ambulance_status
            if ambulance_dispatched_at:
                model.ambulance_dispatched_at = ambulance_dispatched_at
            if police_status:
                model.police_status = police_status
            if police_notified_at:
                model.police_notified_at = police_notified_at
            if timeline_events is not None:
                model.timeline_events_json = json.dumps(timeline_events)
            db.commit()
            db.refresh(model)
        return model

    @staticmethod
    def update_status(db: Session, incident_id: str, notification_status: str) -> Optional[IncidentModel]:
        model = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if model:
            model.notification_status = notification_status
            db.commit()
            db.refresh(model)
        return model

    @staticmethod
    def update_notification_lifecycle(
        db: Session,
        incident_id: str,
        lifecycle_stage: str,
        message: Optional[str] = None,
        event_title: Optional[str] = None,
        event_details: Optional[str] = None,
        is_simulated: bool = True
    ) -> Optional[IncidentModel]:
        """Update authoritative notification lifecycle state, history log, and activity timeline."""
        model = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if not model:
            return None

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        model.notification_status = lifecycle_stage
        if message:
            model.notification_message = message

        stage_status_map = {
            "draft": "Draft [SIMULATED]" if is_simulated else "Draft",
            "prepared": "Notification Prepared [SIMULATED]" if is_simulated else "Notification Prepared",
            "sent": "Notification Sent [SIMULATED]" if is_simulated else "Notification Sent",
            "delivered": "Notification Delivered [SIMULATED]" if is_simulated else "Notification Delivered",
            "acknowledged": "Acknowledged [SIMULATED]" if is_simulated else "Acknowledged",
            "response_initiated": "Response Initiated [SIMULATED]" if is_simulated else "Response Initiated"
        }
        model.police_status = stage_status_map.get(lifecycle_stage, f"{lifecycle_stage.title()} [SIMULATED]")

        # Update history
        history = json.loads(getattr(model, "notification_history_json", None) or "[]")
        history.append({
            "stage": lifecycle_stage,
            "status": model.police_status,
            "event": event_title or f"Notification transitioned to {lifecycle_stage} [SIMULATED]",
            "timestamp": now_iso,
            "is_simulated": is_simulated,
            "details": event_details or ""
        })
        model.notification_history_json = json.dumps(history)

        # Update timeline if title given
        if event_title:
            timeline = json.loads(model.timeline_events_json or "[]")
            timeline.append({
                "step": len(timeline) + 1,
                "title": event_title,
                "timestamp": now_iso,
                "status": "COMPLETED" if lifecycle_stage in ("prepared", "acknowledged", "response_initiated") else ("DELIVERED" if lifecycle_stage == "delivered" else "SENT"),
                "details": event_details or f"Notification transitioned to {lifecycle_stage}."
            })
            model.timeline_events_json = json.dumps(timeline)

        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def reset_notification_lifecycle(
        db: Session,
        incident_id: str,
        target_stage: str = "prepared"
    ) -> Optional[IncidentModel]:
        """Reset simulated notification state back to specified stage without deleting incident."""
        model = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if not model:
            return None
        model.notification_status = target_stage
        model.police_status = "Notification Prepared [SIMULATED]" if target_stage == "prepared" else "Draft [SIMULATED]"
        timeline = json.loads(model.timeline_events_json or "[]")
        timeline = [
            e for e in timeline
            if not any(k in str(e.get("title", "")).lower() for k in ["acknowledges", "delivered to desk", "transmitted to", "response coordination initiated"])
        ]
        model.timeline_events_json = json.dumps(timeline)
        history = json.loads(getattr(model, "notification_history_json", None) or "[]")
        history.append({
            "stage": target_stage,
            "status": model.police_status,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "is_simulated": True,
            "details": "Demo notification reset"
        })
        model.notification_history_json = json.dumps(history)
        db.commit()
        db.refresh(model)
        return model


class DeviceRepository:
    """Database repository for IoT AI Box device telemetry & heartbeats."""

    @staticmethod
    def record_heartbeat(
        db: Session,
        device_id: str = "PI-AI-BOX-01",
        device_name: str = "Raspberry Pi 5 AI Box",
        ip_address: str = "192.168.1.105",
        telemetry: Optional[Dict[str, Any]] = None
    ) -> DeviceModel:
        now = datetime.utcnow()
        model = DeviceModel(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            last_heartbeat=now,
            is_connected=True,
            telemetry_json=json.dumps(telemetry or {})
        )
        persisted = db.merge(model)
        db.commit()
        db.refresh(persisted)
        return persisted

    @staticmethod
    def get_status(db: Session, device_id: str = "PI-AI-BOX-01") -> Dict[str, Any]:
        dev = db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        if not dev or not dev.last_heartbeat:
            return {
                "device_id": device_id,
                "device_name": dev.device_name if dev else "Raspberry Pi 5 AI Box",
                "is_connected": False,
                "status": "DISCONNECTED",
                "last_seen_sec_ago": None,
                "ip_address": dev.ip_address if dev else "N/A"
            }

        now = datetime.utcnow()
        diff_sec = (now - dev.last_heartbeat).total_seconds()
        # Connection valid within 20 seconds
        is_conn = diff_sec <= 20.0
        return {
            "device_id": dev.device_id,
            "device_name": dev.device_name,
            "is_connected": is_conn,
            "status": "CONNECTED" if is_conn else "DISCONNECTED",
            "last_seen_sec_ago": round(diff_sec, 1),
            "ip_address": dev.ip_address,
            "last_heartbeat": dev.last_heartbeat.isoformat()
        }


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
            is_active=cam_data.get("is_active", True),
            status=cam_data.get("status", "active"),
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
    """Seed camera and simulated facility tables if tables are empty."""
    # Seed cameras
    if db.query(CameraModel).count() == 0:
        CameraRepository.create(db, {
            "id": "CAM-MAIN-01",
            "name": "Main Junction CCTV",
            "source": "rtsp://localhost:8554/live/main",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "location_desc": "Shivajinagar Central Junction",
            "is_active": True,
            "status": "active",
        })
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
                    "merchant_name": c.get("merchant_name", "Highway Junction Superstore"),
                    "is_active": c.get("active", True),
                    "status": "active",
                })

    # Seed facilities
    if db.query(FacilityModel).count() == 0:
        FacilityRepository.create(db, {
            "id": "FAC-HOSPITAL-01",
            "name": "Sancheti Trauma Centre (Simulated)",
            "type": "hospital",
            "latitude": 18.5300,
            "longitude": 73.8500,
            "phone": "+91-20-28990001",
            "status": "active",
        })
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


class SQLAlchemyRepository:
    """Unified repository abstraction used across Stage 15-20 tests, CLI, and dashboard fallback."""

    def __init__(self, session_factory=None):
        from backend.database.database import SessionLocal
        self.session_factory = session_factory or SessionLocal
        self.seed_default_data()

    def _get_session(self) -> Session:
        return self.session_factory()

    def seed_default_data(self) -> None:
        with self._get_session() as db:
            seed_defaults_if_empty(db)

    def reset(self) -> None:
        """Reset database tables and re-seed default test fixtures."""
        with self._get_session() as db:
            db.query(IncidentModel).delete()
            db.query(CameraModel).delete()
            db.query(FacilityModel).delete()
            db.commit()
            seed_defaults_if_empty(db)

    def add_camera(self, camera: Any) -> CameraSchema:
        cam_dict = camera.model_dump() if hasattr(camera, "model_dump") else dict(camera)
        cid = cam_dict.get("camera_id") or cam_dict.get("id")
        loc_desc = cam_dict.get("location_name") or cam_dict.get("location_desc") or cam_dict.get("location") or ""
        with self._get_session() as db:
            m = CameraRepository.create(db, {
                "id": cid,
                "name": cam_dict.get("name", cid),
                "source": cam_dict.get("stream_url") or cam_dict.get("source", ""),
                "latitude": cam_dict.get("latitude"),
                "longitude": cam_dict.get("longitude"),
                "location_desc": loc_desc,
                "merchant_name": cam_dict.get("merchant_name", "Highway Junction Superstore"),
                "is_active": cam_dict.get("enabled", cam_dict.get("is_active", True)),
            })
            return CameraSchema(
                camera_id=m.id,
                id=m.id,
                name=m.name,
                source=m.source,
                stream_url=m.source,
                latitude=m.latitude,
                longitude=m.longitude,
                location_name=m.location_desc,
                location_desc=m.location_desc,
                merchant_name=getattr(m, "merchant_name", "Highway Junction Superstore") or "Highway Junction Superstore",
                is_active=m.is_active,
                enabled=m.is_active,
                status=getattr(m, "status", "active") or "active",
            )

    def get_camera(self, camera_id: str) -> Optional[CameraSchema]:
        with self._get_session() as db:
            m = CameraRepository.get_by_id(db, camera_id)
            if not m:
                return None
            return CameraSchema(
                camera_id=m.id,
                id=m.id,
                name=m.name,
                source=m.source,
                stream_url=m.source,
                latitude=m.latitude,
                longitude=m.longitude,
                location_name=m.location_desc,
                location_desc=m.location_desc,
                merchant_name=getattr(m, "merchant_name", "Highway Junction Superstore") or "Highway Junction Superstore",
                is_active=m.is_active,
                enabled=m.is_active,
                status=getattr(m, "status", "active") or "active",
            )

    def list_cameras(self, enabled_only: bool = False) -> List[CameraSchema]:
        with self._get_session() as db:
            models = CameraRepository.get_all(db)
            res = []
            for m in models:
                if enabled_only and not m.is_active:
                    continue
                res.append(CameraSchema(
                    camera_id=m.id,
                    id=m.id,
                    name=m.name,
                    source=m.source,
                    stream_url=m.source,
                    latitude=m.latitude,
                    longitude=m.longitude,
                    location_name=m.location_desc,
                    location_desc=m.location_desc,
                    merchant_name=getattr(m, "merchant_name", "Highway Junction Superstore") or "Highway Junction Superstore",
                    is_active=m.is_active,
                    enabled=m.is_active,
                    status=getattr(m, "status", "active") or "active",
                ))
            return res

    def update_camera_status(self, camera_id: str, status: str) -> Optional[CameraSchema]:
        with self._get_session() as db:
            m = CameraRepository.get_by_id(db, camera_id)
            if not m:
                return None
            m.status = status
            m.is_active = (status.lower() in ["active", "enabled", "online"])
            db.commit()
            db.refresh(m)
            return CameraSchema(
                camera_id=m.id,
                id=m.id,
                name=m.name,
                source=m.source,
                latitude=m.latitude,
                longitude=m.longitude,
                location_name=m.location_desc,
                is_active=m.is_active,
                status=status,
            )


    def add_facility(self, facility: Any) -> FacilitySchema:
        fac_dict = facility.model_dump() if hasattr(facility, "model_dump") else dict(facility)
        fid = fac_dict.get("facility_id") or fac_dict.get("id")
        with self._get_session() as db:
            m = FacilityRepository.create(db, {
                "id": fid,
                "name": fac_dict.get("name", fid),
                "type": fac_dict.get("type", "hospital"),
                "latitude": fac_dict.get("latitude", 0.0),
                "longitude": fac_dict.get("longitude", 0.0),
                "phone": fac_dict.get("phone_contact") or fac_dict.get("phone", ""),
                "status": fac_dict.get("status", "active"),
            })
            return FacilitySchema(
                facility_id=m.id,
                id=m.id,
                name=m.name,
                type=m.type,
                latitude=m.latitude,
                longitude=m.longitude,
                phone_contact=m.phone,
                phone=m.phone,
                status=m.status,
                available=True,
                is_simulated=True,
            )

    def list_facilities(self, facility_type: Optional[str] = None) -> List[FacilitySchema]:
        with self._get_session() as db:
            models = FacilityRepository.get_all(db, facility_type=facility_type)
            res = []
            for m in models:
                res.append(FacilitySchema(
                    facility_id=m.id,
                    id=m.id,
                    name=m.name,
                    type=m.type,
                    latitude=m.latitude,
                    longitude=m.longitude,
                    phone_contact=m.phone,
                    phone=m.phone,
                    status=m.status,
                    available=True,
                    is_simulated=True,
                ))
            return res

    def get_facility(self, facility_id: str) -> Optional[FacilitySchema]:
        with self._get_session() as db:
            m = db.query(FacilityModel).filter(FacilityModel.id == facility_id).first()
            if not m:
                return None
            return FacilitySchema(
                facility_id=m.id,
                id=m.id,
                name=m.name,
                type=m.type,
                latitude=m.latitude,
                longitude=m.longitude,
                phone_contact=m.phone,
                phone=m.phone,
                status=m.status,
                available=True,
                is_simulated=True,
            )

    def add_incident(self, incident: Any) -> IncidentPackageResponseSchema:
        inc_data = incident.model_dump() if hasattr(incident, "model_dump") else dict(incident)
        inc_id = inc_data.get("incident_id") or inc_data.get("id")
        tracks = inc_data.get("involved_track_ids") or inc_data.get("involved_tracks") or []
        ev_frames = inc_data.get("evidence_frames") or []
        ev_vid = inc_data.get("evidence_video_path")
        evidence_dict = {"directory": "", "key_frames": ev_frames, "video_clip": ev_vid}
        location_data = inc_data.get("location")
        plates_data = inc_data.get("plate_readings") or []

        with self._get_session() as db:
            m = IncidentModel(
                id=inc_id,
                incident_type=inc_data.get("incident_type", "collision"),
                camera_id=inc_data.get("camera_id", "CAM-01"),
                timestamp=str(inc_data.get("timestamp", "")),
                confidence_score=float(inc_data.get("confidence_score", 1.0)),
                verification_status=inc_data.get("verification_status", "verified"),
                notification_status=inc_data.get("notification_status", "pending"),
                involved_tracks_json=json.dumps(tracks),
                reasons_json=json.dumps(inc_data.get("reasons", [])),
                signals_json=json.dumps(inc_data.get("signals") or inc_data.get("reason_metadata") or {}),
                location_json=json.dumps(location_data.model_dump() if hasattr(location_data, "model_dump") else location_data) if location_data else None,
                evidence_json=json.dumps(evidence_dict) if evidence_dict else None,
                plate_readings_json=json.dumps([p.model_dump() if hasattr(p, "model_dump") else p for p in plates_data]),
            )
            persisted = db.merge(m)
            db.commit()
            db.refresh(persisted)
            return self._model_to_response_schema(persisted)

    def get_incident(self, incident_id: str) -> Optional[IncidentPackageResponseSchema]:
        with self._get_session() as db:
            m = IncidentRepository.get_by_id(db, incident_id)
            if not m:
                return None
            return self._model_to_response_schema(m)

    def list_incidents(self, incident_type: Optional[str] = None, camera_id: Optional[str] = None, limit: int = 50) -> List[IncidentPackageResponseSchema]:
        with self._get_session() as db:
            models = IncidentRepository.get_all(db, incident_type=incident_type, camera_id=camera_id, limit=limit)
            return [self._model_to_response_schema(m) for m in models]

    def update_incident_status(self, incident_id: str, status: str) -> Optional[IncidentPackageResponseSchema]:
        with self._get_session() as db:
            m = IncidentRepository.update_status(db, incident_id, status)
            if not m:
                return None
            return self._model_to_response_schema(m)

    def _model_to_response_schema(self, m: IncidentModel) -> IncidentPackageResponseSchema:
        tracks = json.loads(m.involved_tracks_json or "[]")
        signals = json.loads(m.signals_json or "{}")
        reasons = json.loads(m.reasons_json or "[]")
        loc_data = json.loads(m.location_json) if m.location_json else None
        loc_schema = LocationSchema(**loc_data) if loc_data else None
        plates_data = json.loads(m.plate_readings_json or "[]")
        plate_schemas = [PlateReadingSchema(**p) for p in plates_data]
        ev_data = json.loads(m.evidence_json) if m.evidence_json else {}

        return IncidentPackageResponseSchema(
            incident_id=m.id,
            id=m.id,
            incident_type=m.incident_type,
            camera_id=m.camera_id,
            timestamp=m.timestamp,
            confidence_score=m.confidence_score,
            verification_status=m.verification_status,
            notification_status=m.notification_status,
            involved_track_ids=tracks,
            evidence_frames=ev_data.get("key_frames", []),
            evidence_video_path=ev_data.get("video_clip"),
            location=loc_schema,
            plate_readings=plate_schemas,
            reason_metadata=signals,
            reasons=reasons,
            signals=signals,
            source_device=getattr(m, "source_device", "Raspberry Pi AI Box"),
            mode=getattr(m, "mode", "DEMO"),
            ambulance_status=getattr(m, "ambulance_status", "Awaiting Dispatch"),
            police_status=getattr(m, "police_status", "Notification Pending"),
        )

    def add_notification(self, schema: Any) -> Any:
        if not hasattr(self, "_notifications"):
            self._notifications = {}
        notif_id = getattr(schema, "notification_id", str(uuid.uuid4()))
        self._notifications[notif_id] = schema
        return schema

    def get_notification(self, notification_id: str) -> Optional[Any]:
        if not hasattr(self, "_notifications"):
            self._notifications = {}
        return self._notifications.get(notification_id)

    def list_notifications(self, incident_id: Optional[str] = None, facility_id: Optional[str] = None) -> List[Any]:
        if not hasattr(self, "_notifications"):
            self._notifications = {}
        items = list(self._notifications.values())
        if incident_id:
            items = [n for n in items if getattr(n, "incident_id", None) == incident_id]
        if facility_id:
            items = [n for n in items if getattr(n, "facility_id", None) == facility_id]
        return items

    def update_notification_status(
        self,
        notification_id: str,
        status: Optional[str] = None,
        reason: str = "",
        new_status: Optional[str] = None,
        **kwargs
    ) -> Optional[Any]:
        target_status = new_status or status or "notified"
        if not hasattr(self, "_notifications"):
            self._notifications = {}
        notif = self._notifications.get(notification_id)
        if not notif:
            return None
        if hasattr(notif, "status"):
            prev_status = notif.status
            notif.status = target_status
            if hasattr(notif, "history") and isinstance(notif.history, list):
                notif.history.append({
                    "previous_status": prev_status,
                    "new_status": target_status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": reason
                })
        elif isinstance(notif, dict):
            notif["status"] = target_status
        return notif


