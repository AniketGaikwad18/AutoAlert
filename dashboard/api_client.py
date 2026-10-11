"""
Dashboard API client for AutoAlert Operations Command Center (Phases 15–17).

Connects frontend to FastAPI endpoints for:
  - System Health & Diagnostics
  - Camera Registry Management
  - Video Analysis Pipeline
  - Incident Feed & Audit Logs
  - Haversine Facility Matching
  - OpenStreetMap / OSRM 2-Leg Emergency Routing
  - Modular Simulated Notification Dispatches & Timelines
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Any, Optional
import requests

from backend.repository import repository
from backend.schemas.incident import IncidentPackageResponseSchema
from backend.schemas.camera import CameraSchema
from backend.schemas.facility import FacilitySchema

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


class DashboardAPIClient:
    """Robust API Client for communicating with AutoAlert FastAPI backend."""

    def __init__(self, base_url: str = DEFAULT_BACKEND_URL, timeout_sec: float = 3.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def check_health(self) -> Dict[str, Any]:
        """Check if FastAPI backend is online and operational."""
        try:
            res = requests.get(f"{self.base_url}/api/v1/health", timeout=self.timeout_sec)
            if res.status_code == 200:
                data = res.json()
                data["online"] = True
                return data
        except Exception:
            pass
        return {"online": False, "status": "offline", "is_prototype": True}

    def list_cameras(self) -> List[Dict[str, Any]]:
        """Fetch list of active registered CCTV cameras."""
        try:
            res = requests.get(f"{self.base_url}/api/v1/cameras", timeout=self.timeout_sec)
            if res.status_code == 200:
                cams = res.json()
                for c in cams:
                    if "camera_id" not in c and "id" in c:
                        c["camera_id"] = c["id"]
                return cams
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        cameras = repository.list_cameras()
        return [c.model_dump() for c in cameras]

    def get_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single registered camera by ID."""
        try:
            res = requests.get(f"{self.base_url}/api/v1/cameras/{camera_id}", timeout=self.timeout_sec)
            if res.status_code == 200:
                cam = res.json()
                if "camera_id" not in cam and "id" in cam:
                    cam["camera_id"] = cam["id"]
                return cam
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        cam = repository.get_camera(camera_id)
        return cam.model_dump() if cam else None

    def list_facilities(self, facility_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch registered emergency response facilities."""
        try:
            params = {}
            if facility_type:
                params["type"] = facility_type
            res = requests.get(f"{self.base_url}/api/v1/facilities", params=params, timeout=self.timeout_sec)
            if res.status_code == 200:
                facs = res.json()
                for f in facs:
                    if "facility_id" not in f and "id" in f:
                        f["facility_id"] = f["id"]
                    if "is_simulated" not in f:
                        f["is_simulated"] = True
                return facs
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        facilities = repository.list_facilities(facility_type=facility_type)
        return [f.model_dump() for f in facilities]

    def list_incidents(
        self, incident_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch incident feed from backend API."""
        try:
            params = {}
            if incident_type:
                params["incident_type"] = incident_type
            params["limit"] = limit
            res = requests.get(
                f"{self.base_url}/api/v1/incidents", params=params, timeout=self.timeout_sec
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        incidents = repository.list_incidents(incident_type=incident_type, limit=limit)
        return [inc.model_dump() for inc in incidents]

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single incident package details by ID."""
        try:
            res = requests.get(
                f"{self.base_url}/api/v1/incidents/{incident_id}", timeout=self.timeout_sec
            )
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 404:
                return None
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        inc = repository.get_incident(incident_id)
        return inc.model_dump() if inc else None

    def get_incident_timeline(self, incident_id: str) -> List[Dict[str, Any]]:
        """Fetch chronological notification timeline for an incident."""
        try:
            res = requests.get(
                f"{self.base_url}/api/v1/incidents/{incident_id}/timeline",
                timeout=self.timeout_sec,
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend API timeline request failed (%s), falling back to service", e)

        from src.dispatch.notification_service import notification_service
        records = notification_service.get_incident_timeline(incident_id)
        if not records:
            records = notification_service.create_incident_timeline(incident_id)
        return [r.to_dict() for r in records]

    def get_incident_route(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Fetch calculated 2-leg emergency route for an incident."""
        try:
            res = requests.get(
                f"{self.base_url}/api/v1/facilities/route",
                params={"incident_id": incident_id},
                timeout=self.timeout_sec,
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend route API request failed (%s)", e)

        # Fallback via route_engine
        inc = repository.get_incident(incident_id)
        if not inc or not inc.location or not inc.location.latitude:
            return None

        from src.dispatch.routing import route_engine
        from src.location.facility_registry import facility_registry
        amb = facility_registry.match_nearest_ambulance(inc.location.latitude, inc.location.longitude)
        hosp = facility_registry.match_nearest_hospital(inc.location.latitude, inc.location.longitude)
        if amb and hosp:
            all_facs = [f.model_dump() for f in repository.list_facilities()]
            route = route_engine.plan_emergency_route(
                ambulance_lat=amb["latitude"],
                ambulance_lon=amb["longitude"],
                incident_lat=inc.location.latitude,
                incident_lon=inc.location.longitude,
                hospital_lat=hosp["latitude"],
                hospital_lon=hosp["longitude"],
                ambulance_id=amb["facility_id"],
                ambulance_name=amb["name"],
                hospital_id=hosp["facility_id"],
                hospital_name=hosp["name"],
                all_facilities=all_facs,
            )
            return route.to_dict()
        return None

    def match_facilities(
        self,
        incident_id: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        facility_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Match nearest emergency facilities using Haversine distance."""
        try:
            payload = {
                "incident_id": incident_id,
                "latitude": latitude,
                "longitude": longitude,
                "facility_type": facility_type,
                "limit": limit,
            }
            res = requests.post(f"{self.base_url}/api/v1/notifications/match", json=payload, timeout=self.timeout_sec)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to in-memory matcher", e)

        from src.dispatch.matching import FacilityMatcher
        all_facs = [f.model_dump() for f in repository.list_facilities()]
        if incident_id and (latitude is None or longitude is None):
            inc = repository.get_incident(incident_id)
            if inc and inc.location:
                latitude = inc.location.latitude
                longitude = inc.location.longitude

        return FacilityMatcher.match_facilities(
            incident_lat=latitude,
            incident_lon=longitude,
            facilities=all_facs,
            facility_type=facility_type,
            limit=limit,
        )

    def dispatch_notification(
        self,
        incident_id: str,
        recipient_type: str,
        recipient_name: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Trigger simulated notification dispatch to a recipient (ambulance/police/hospital/merchant)."""
        try:
            payload = {
                "incident_id": incident_id,
                "recipient_type": recipient_type,
                "recipient_name": recipient_name,
                "message": message,
                "details": details or {},
            }
            res = requests.post(f"{self.base_url}/api/v1/notifications/dispatch", json=payload, timeout=self.timeout_sec)
            if res.status_code in (200, 201):
                return res.json()
        except Exception as e:
            logger.debug("Backend notification dispatch failed (%s), falling back to local service", e)

        from src.dispatch.notification_service import notification_service
        rec_type = recipient_type.lower()
        if rec_type == "ambulance":
            rec = notification_service.notify_ambulance(incident_id, recipient=recipient_name or "Ambulance EMS", message=message, details=details)
        elif rec_type == "police":
            rec = notification_service.notify_police(incident_id, recipient=recipient_name or "Police Station", message=message, details=details)
        elif rec_type == "hospital":
            rec = notification_service.notify_hospital(incident_id, recipient=recipient_name or "Trauma Hospital", message=message, details=details)
        else:
            rec = notification_service.notify_merchant(incident_id, recipient=recipient_name or "Merchant Operations", message=message, details=details)
        return rec.to_dict()

    def trigger_notification(
        self, incident_id: str, facility_id: str, message: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Trigger a simulated emergency response notification to a facility."""
        try:
            payload = {"incident_id": incident_id, "facility_id": facility_id, "message": message}
            res = requests.post(f"{self.base_url}/api/v1/notifications", json=payload, timeout=self.timeout_sec)
            if res.status_code == 201:
                return res.json()
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        # Fallback via notification_service and repository
        facilities = repository.list_facilities()
        target_fac = next((f for f in facilities if f.facility_id == facility_id), None)
        if not target_fac:
            return None

        from src.dispatch.notification import SimulatedNotification
        from backend.schemas.notification import NotificationResponseSchema
        sim = SimulatedNotification(
            incident_id=incident_id,
            facility_id=facility_id,
            facility_type=target_fac.type,
            facility_name=target_fac.name,
            status="notified",
            message=message or f"SIMULATED DISPATCH: Incident {incident_id}",
        )
        sim.history.append({"previous_status": "pending", "new_status": "notified", "timestamp": sim.created_at, "reason": "Simulated dispatch triggered"})
        schema = NotificationResponseSchema(
            notification_id=sim.notification_id,
            incident_id=sim.incident_id,
            facility_id=sim.facility_id,
            facility_type=sim.facility_type,
            facility_name=sim.facility_name,
            status=sim.status,
            distance_km=sim.distance_km,
            message=sim.message,
            is_simulated=True,
            created_at=sim.created_at,
            updated_at=sim.updated_at,
            history=sim.history,
        )
        saved = repository.add_notification(schema)
        return saved.model_dump()

    def update_notification_status(
        self, notification_id: str, status: str, reason: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Update status of a simulated notification dispatch."""
        try:
            payload = {"status": status, "reason": reason}
            res = requests.patch(
                f"{self.base_url}/api/v1/notifications/{notification_id}/status",
                json=payload,
                timeout=self.timeout_sec,
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        updated = repository.update_notification_status(notification_id, status, reason)
        return updated.model_dump() if updated else None

    def list_notifications(
        self, incident_id: Optional[str] = None, facility_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve simulated notification logs."""
        try:
            params = {}
            if incident_id:
                params["incident_id"] = incident_id
            if facility_id:
                params["facility_id"] = facility_id
            res = requests.get(f"{self.base_url}/api/v1/notifications", params=params, timeout=self.timeout_sec)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend API request failed (%s), falling back to repository", e)

        notifs = repository.list_notifications(incident_id=incident_id, facility_id=facility_id)
        return [n.model_dump() for n in notifs]

    def calculate_route(
        self,
        incident_lat: float,
        incident_lon: float,
        ambulance_lat: Optional[float] = None,
        ambulance_lon: Optional[float] = None,
        hospital_lat: Optional[float] = None,
        hospital_lon: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Calculate 2-leg emergency route via direct coordinates."""
        try:
            payload = {
                "incident_latitude": incident_lat,
                "incident_longitude": incident_lon,
                "ambulance_latitude": ambulance_lat,
                "ambulance_longitude": ambulance_lon,
                "hospital_latitude": hospital_lat,
                "hospital_longitude": hospital_lon,
            }
            res = requests.post(f"{self.base_url}/api/v1/dispatch/route", json=payload, timeout=self.timeout_sec)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend route direct calculation failed (%s), falling back to route_engine", e)

        from src.location.facility_registry import facility_registry
        from src.dispatch.routing import route_engine
        amb = facility_registry.match_nearest_ambulance(incident_lat, incident_lon)
        hosp = facility_registry.match_nearest_hospital(incident_lat, incident_lon)
        all_facs = [f.model_dump() for f in repository.list_facilities()]
        route = route_engine.plan_emergency_route(
            ambulance_lat=ambulance_lat or (amb["latitude"] if amb else incident_lat - 0.01),
            ambulance_lon=ambulance_lon or (amb["longitude"] if amb else incident_lon - 0.01),
            incident_lat=incident_lat,
            incident_lon=incident_lon,
            hospital_lat=hospital_lat or (hosp["latitude"] if hosp else incident_lat + 0.02),
            hospital_lon=hospital_lon or (hosp["longitude"] if hosp else incident_lon + 0.02),
            ambulance_id=amb.get("facility_id", "EMS-01") if amb else "EMS-01",
            ambulance_name=amb.get("name", "EMS Station") if amb else "EMS Station",
            hospital_id=hosp.get("facility_id", "HOSP-01") if hosp else "HOSP-01",
            hospital_name=hosp.get("name", "Trauma Hospital") if hosp else "Trauma Hospital",
            all_facilities=all_facs,
        )
        return route.to_dict()

    def analyze_video(
        self,
        camera_id: str,
        video_path: Optional[str] = None,
        demo_mode: bool = True,
    ) -> Dict[str, Any]:
        """Trigger video analysis on backend or local service."""
        try:
            files = None
            if video_path and os.path.exists(video_path):
                files = {"video": (os.path.basename(video_path), open(video_path, "rb"), "video/mp4")}
            data = {"camera_id": camera_id, "demo_mode": str(demo_mode).lower()}
            res = requests.post(
                f"{self.base_url}/api/v1/analyze",
                data=data,
                files=files,
                timeout=120.0,
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend analyze API request failed (%s), running via local pipeline", e)

        from src.simulation.controller import CCTVSimulationService
        service = CCTVSimulationService()
        result = service.run_simulation(
            camera_id=camera_id,
            video_path=video_path,
            force_demo_incident=demo_mode,
        )
        return {
            "success": result.success,
            "verified": result.verified,
            "camera_id": camera_id,
            "camera_name": result.camera.name if result.camera else None,
            "location": result.location.to_dict() if result.location else None,
            "incident": result.incident.to_dict() if result.incident else None,
            "evidence_frames": result.evidence_frames,
            "evidence_video_path": result.evidence_video_path,
            "plate_readings": result.plate_readings,
            "nearby_facilities": result.nearby_facilities,
            "emergency_route": result.emergency_route.to_dict() if result.emergency_route else None,
            "notification_timeline": result.notification_timeline,
            "simulated_notification": result.simulated_notification,
            "total_frames_analyzed": result.total_frames_analyzed,
            "nearest_ambulance": result.nearest_ambulance,
            "nearest_hospital": result.nearest_hospital,
            "nearest_police": result.nearest_police,
            "stations_along_route": result.stations_along_route,
            "route_distance_km": result.route_distance_km,
            "estimated_travel_time_min": result.estimated_travel_time_min,
        }

    def list_demo_scenarios(self) -> List[Dict[str, Any]]:
        """List available exhibition demonstration scenarios."""
        try:
            res = requests.get(f"{self.base_url}/api/v1/demo/scenarios", timeout=self.timeout_sec)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend demo scenarios failed (%s), falling back to demo_manager", e)

        from src.demo.demo_engine import demo_manager
        return demo_manager.list_scenarios()

    def get_camera1_demo_info(self) -> Dict[str, Any]:
        """Fetch Camera 1 demonstration metadata and assets."""
        try:
            res = requests.get(f"{self.base_url}/api/v1/demo/camera1", timeout=self.timeout_sec)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend Camera 1 info failed (%s), falling back to demo_manager", e)

        from src.demo.demo_engine import demo_manager
        sc = demo_manager.get_scenario("collision_junction")
        return {
            "camera_id": sc.camera_id if sc else "CAM-001",
            "camera_name": sc.camera_name if sc else "Camera 1 — Main Highway Junction",
            "location_name": sc.location_name if sc else "Main Highway Junction, Pune",
            "latitude": sc.latitude if sc else 18.5204,
            "longitude": sc.longitude if sc else 73.8567,
            "video_filename": sc.video_filename if sc else "demo_junction_collision.mp4",
            "merchant_name": sc.merchant_name if sc else "Highway Junction Superstore",
            "is_registered": True,
            "status": "ONLINE (DEMO READY)",
            "demo_mode": True,
        }

    def execute_demo_scenario(self, scenario_id: str = "collision_junction") -> Dict[str, Any]:
        """Execute complete live demonstration scenario end-to-end."""
        try:
            payload = {"scenario_id": scenario_id}
            res = requests.post(f"{self.base_url}/api/v1/demo/execute", json=payload, timeout=60.0)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend demo execute failed (%s), running via local demo_manager", e)

        from src.demo.demo_engine import demo_manager
        res_obj = demo_manager.execute_demo_flow(scenario_id=scenario_id)
        sc = demo_manager.get_scenario(scenario_id)
        return {
            "scenario_id": scenario_id,
            "scenario_name": sc.name if sc else scenario_id,
            "demo_mode": True,
            "execution_success": res_obj.success,
            "workflow_completed": True,
            "incident": res_obj.incident.to_dict() if res_obj.incident else None,
            "location": res_obj.location.to_dict() if res_obj.location else None,
            "nearest_facilities": res_obj.nearest_facilities,
            "emergency_route": res_obj.emergency_route.to_dict() if res_obj.emergency_route else None,
            "notifications": [n.to_dict() for n in res_obj.notifications],
            "summary": res_obj.summary.to_dict() if res_obj.summary else None,
            "stages_executed": [s.to_dict() for s in res_obj.stages_executed],
            "execution_duration_sec": res_obj.execution_duration_sec,
            "error_message": res_obj.error_message,
        }

    def analyze_corridor(
        self,
        route_coordinates: List[Tuple[float, float]],
        corridor_width_meters: float = 400.0,
        incident_latitude: float = 18.5204,
        incident_longitude: float = 73.8567,
    ) -> Dict[str, Any]:
        """Identify mapped police stations and traffic signals along emergency route corridor."""
        try:
            payload = {
                "route_coordinates": [[float(c[0]), float(c[1])] for c in route_coordinates],
                "corridor_width_meters": corridor_width_meters,
                "incident_latitude": incident_latitude,
                "incident_longitude": incident_longitude,
            }
            res = requests.post(
                f"{self.base_url}/api/v1/dispatch/corridor-analysis",
                json=payload,
                timeout=self.timeout_sec,
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug("Backend corridor analysis failed (%s), running via local corridor_analyzer", e)

        from src.dispatch.corridor_analysis import corridor_analyzer
        coords = [(float(c[0]), float(c[1])) for c in route_coordinates]
        res_obj = corridor_analyzer.analyze_corridor(
            route_coords=coords,
            corridor_width_meters=corridor_width_meters,
            incident_lat=incident_latitude,
            incident_lon=incident_longitude,
        )
        return res_obj.to_dict()

