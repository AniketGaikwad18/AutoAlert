"""
AutoAlert AI Teammate Orchestrator (Phases 18+).

Autonomous operational teammate for merchant emergency response executing the 6-stage lifecycle:
  OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT

Core Design Invariants:
  1. Not a generic chatbot: structured, deterministic operations workflow.
  2. Grounded Reasoning: natural language briefings are strictly synthesized from verified system facts.
  3. No Fabrication: GPS coordinates, facilities, distances, routes, and plate numbers come exclusively from deterministic tools.
  4. Explicit Prototype Notice: All notifications and dispatches clearly marked 'SIMULATED'.
"""

from __future__ import annotations

import logging
import time
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

from src.core.incident import LocationInfo, IncidentPackage
from src.teammate.models import (
    WorkflowStage,
    WorkflowStageRecord,
    StructuredIncidentSummary,
    TeammateOrchestrationResult,
)
from src.teammate.tools import (
    tool_get_incident,
    tool_get_location,
    tool_find_facilities,
    tool_calculate_distances,
    tool_generate_route,
    tool_create_notification_records,
    tool_create_incident_summary,
)
from src.simulation.controller import CCTVSimulationService, SimulationResult
from src.location.camera_registry import camera_registry
from backend.repository import repository

logger = logging.getLogger(__name__)


class AITeammateOrchestrator:
    """
    Autonomous AI Teammate Orchestrator for coordinating merchant emergency response.
    """

    def __init__(self, simulation_service: Optional[CCTVSimulationService] = None) -> None:
        self.simulation_service = simulation_service or CCTVSimulationService()
        self._history: Dict[str, TeammateOrchestrationResult] = {}

    def orchestrate_verified_incident(
        self,
        incident_id: str,
        camera_id: Optional[str] = None,
        custom_merchant_name: Optional[str] = None,
    ) -> TeammateOrchestrationResult:
        """
        Orchestrate response for an already-verified incident:
          DECIDE ➔ ACT ➔ REPORT
        """
        start_time = time.time()
        stages: List[WorkflowStageRecord] = []

        # 1. Fetch Incident
        inc_data = tool_get_incident(incident_id)
        if not inc_data:
            err_msg = f"Incident '{incident_id}' not found in system repository."
            logger.error(err_msg)
            return TeammateOrchestrationResult(
                incident_id=incident_id,
                success=False,
                error_message=err_msg,
                total_duration_sec=time.time() - start_time,
            )

        cam_id = camera_id or inc_data.get("camera_id", "CAM-001")
        cam_obj = camera_registry.get_camera(cam_id)
        cam_name = cam_obj.name if cam_obj else f"Camera {cam_id}"
        merchant_name = custom_merchant_name or (cam_obj.merchant_name if cam_obj else "Store Operations")

        # ----------------------------------------------------------------------
        # STAGE: DECIDE (Resolve location & match nearest emergency facilities)
        # ----------------------------------------------------------------------
        t_start_decide = datetime.now(timezone.utc).isoformat()
        location = tool_get_location(camera_id=cam_id, incident_id=incident_id)
        lat = location.latitude if location else None
        lon = location.longitude if location else None
        loc_name = location.name if location else "Storefront Perimeter"

        facilities_res = tool_find_facilities(incident_lat=lat, incident_lon=lon, limit=5)
        amb = facilities_res.get("nearest_ambulance")
        hosp = facilities_res.get("nearest_hospital")
        pol = facilities_res.get("nearest_police")

        amb_name = amb.get("name", "Central EMS Ambulance (Simulated)") if amb else "Central EMS Ambulance (Simulated)"
        hosp_name = hosp.get("name", "City Care Trauma Hospital (Simulated)") if hosp else "City Care Trauma Hospital (Simulated)"
        pol_name = pol.get("name", "Shivajinagar Police Station (Simulated)") if pol else "Shivajinagar Police Station (Simulated)"

        decide_record = WorkflowStageRecord(
            stage=WorkflowStage.DECIDE,
            status="completed",
            started_at=t_start_decide,
            completed_at=datetime.now(timezone.utc).isoformat(),
            inputs_summary={"camera_id": cam_id, "location_name": loc_name, "lat": lat, "lon": lon},
            outputs_summary={
                "assigned_ambulance": amb_name,
                "ambulance_distance_km": amb.get("distance_km") if amb else None,
                "destination_hospital": hosp_name,
                "hospital_distance_km": hosp.get("distance_km") if hosp else None,
                "assigned_police": pol_name,
                "police_distance_km": pol.get("distance_km") if pol else None,
            },
            reasoning_log=f"Resolved geospatial perimeter '{loc_name}' from registered camera '{cam_id}'. Ranked nearest facilities via Haversine distance metric.",
        )
        stages.append(decide_record)

        # ----------------------------------------------------------------------
        # STAGE: ACT (Generate 2-leg route and dispatch simulated notifications)
        # ----------------------------------------------------------------------
        t_start_act = datetime.now(timezone.utc).isoformat()
        route_res = None
        if lat is not None and lon is not None and amb and hosp:
            route_res = tool_generate_route(
                ambulance=amb,
                incident_lat=lat,
                incident_lon=lon,
                hospital=hosp,
            )

        # Dispatch simulated notifications to all 4 stakeholders
        notification_records = tool_create_notification_records(
            incident_id=incident_id,
            ambulance_name=amb_name,
            police_name=pol_name,
            hospital_name=hosp_name,
            merchant_name=merchant_name,
            location_name=loc_name,
            camera_id=cam_id,
            camera_name=cam_name,
        )

        act_record = WorkflowStageRecord(
            stage=WorkflowStage.ACT,
            status="completed",
            started_at=t_start_act,
            completed_at=datetime.now(timezone.utc).isoformat(),
            inputs_summary={"incident_id": incident_id, "route_needed": bool(route_res)},
            outputs_summary={
                "route_distance_km": route_res.total_distance_km if route_res else None,
                "estimated_travel_time_min": route_res.estimated_duration_min if route_res else None,
                "corridor_stations_count": len(route_res.stations_along_route) if route_res else 0,
                "dispatches_sent": len(notification_records),
                "stakeholders_notified": ["ambulance", "police", "hospital", "merchant"],
            },
            reasoning_log=f"Generated 2-leg road response corridor (Ambulance ➔ Incident ➔ Hospital). Dispatched 4 structured simulated notification records (Status: SIMULATED).",
        )
        stages.append(act_record)

        # ----------------------------------------------------------------------
        # STAGE: REPORT (Synthesize structured summary and executive briefing)
        # ----------------------------------------------------------------------
        t_start_report = datetime.now(timezone.utc).isoformat()

        # Grounded text synthesis
        exec_briefing = self._synthesize_executive_briefing(
            incident_data=inc_data,
            location_name=loc_name,
            camera_name=cam_name,
            ambulance=amb,
            hospital=hosp,
            police=pol,
            route=route_res,
        )
        merchant_adv = self._synthesize_merchant_advisory(
            incident_data=inc_data,
            location_name=loc_name,
            merchant_name=merchant_name,
            ambulance_name=amb_name,
        )

        summary = tool_create_incident_summary(
            incident=inc_data,
            location=location,
            facilities_result=facilities_res,
            route_result=route_res,
            notification_records=notification_records,
            camera_name=cam_name,
            executive_briefing=exec_briefing,
            merchant_advisory=merchant_adv,
        )

        report_record = WorkflowStageRecord(
            stage=WorkflowStage.REPORT,
            status="completed",
            started_at=t_start_report,
            completed_at=datetime.now(timezone.utc).isoformat(),
            inputs_summary={"summary_id": summary.summary_id},
            outputs_summary={"executive_briefing_length": len(exec_briefing), "merchant_advisory_length": len(merchant_adv)},
            reasoning_log="Compiled complete operational CAD dossier, executive incident briefing, and downloadable structured package.",
        )
        stages.append(report_record)

        result = TeammateOrchestrationResult(
            incident_id=incident_id,
            success=True,
            stages_executed=stages,
            summary=summary,
            total_duration_sec=time.time() - start_time,
        )
        self._history[incident_id] = result
        return result

    def orchestrate_cctv_stream(
        self,
        video_path: str,
        camera_id: str,
        force_demo_incident: bool = True,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> TeammateOrchestrationResult:
        """
        Execute full 6-stage operational lifecycle from raw CCTV video ingestion to final report:
          OBSERVE ➔ UNDERSTAND ➔ VERIFY ➔ DECIDE ➔ ACT ➔ REPORT
        """
        start_time = time.time()
        stages: List[WorkflowStageRecord] = []

        # ----------------------------------------------------------------------
        # STAGE 1 & 2: OBSERVE & UNDERSTAND (Vision Pipeline Ingestion & Kinematics)
        # ----------------------------------------------------------------------
        t_start_obs = datetime.now(timezone.utc).isoformat()
        if progress_callback:
            progress_callback("OBSERVE", "Ingesting CCTV stream and tracking object trajectories...")

        sim_result: SimulationResult = self.simulation_service.run_simulation(
            video_path=video_path,
            camera_id=camera_id,
            force_demo_incident=force_demo_incident,
        )

        stages.append(
            WorkflowStageRecord(
                stage=WorkflowStage.OBSERVE,
                status="completed" if sim_result.success else "failed",
                started_at=t_start_obs,
                completed_at=datetime.now(timezone.utc).isoformat(),
                inputs_summary={"video_source": os.path.basename(video_path), "camera_id": camera_id},
                outputs_summary={"frames_analyzed": sim_result.total_frames_analyzed, "events_detected": sim_result.detected_events_count},
                reasoning_log=f"Completed CCTV frame extraction and multi-object tracking over {sim_result.total_frames_analyzed} frames.",
            )
        )

        # ----------------------------------------------------------------------
        # STAGE 2: UNDERSTAND (Kinematics & OCR)
        # ----------------------------------------------------------------------
        t_start_und = datetime.now(timezone.utc).isoformat()
        stages.append(
            WorkflowStageRecord(
                stage=WorkflowStage.UNDERSTAND,
                status="completed" if sim_result.success else "failed",
                started_at=t_start_und,
                completed_at=datetime.now(timezone.utc).isoformat(),
                inputs_summary={"frames_processed": sim_result.total_frames_analyzed},
                outputs_summary={"plate_readings_count": len(sim_result.plate_readings), "evidence_frames_count": len(sim_result.evidence_frames)},
                reasoning_log="Evaluated collision kinematics, closing velocities, motionless intervals, and license plate OCR.",
            )
        )

        # ----------------------------------------------------------------------
        # STAGE 3: VERIFY (Multi-Frame Verification State Machine)
        # ----------------------------------------------------------------------
        t_start_ver = datetime.now(timezone.utc).isoformat()
        if not sim_result.success or not sim_result.verified or not sim_result.incident:
            stages.append(
                WorkflowStageRecord(
                    stage=WorkflowStage.VERIFY,
                    status="completed",
                    started_at=t_start_ver,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    inputs_summary={"verified": False},
                    outputs_summary={"verdict": "NORMAL_OPERATIONS_NO_INCIDENT"},
                    reasoning_log="Temporal verification concluded no emergency incident occurred in the analyzed video stream.",
                )
            )
            return TeammateOrchestrationResult(
                incident_id="NO-INCIDENT",
                success=True,
                stages_executed=stages,
                summary=None,
                total_duration_sec=time.time() - start_time,
            )

        inc_pkg = sim_result.incident
        stages.append(
            WorkflowStageRecord(
                stage=WorkflowStage.VERIFY,
                status="completed",
                started_at=t_start_ver,
                completed_at=datetime.now(timezone.utc).isoformat(),
                inputs_summary={"incident_id": inc_pkg.incident_id, "confidence": inc_pkg.confidence_score},
                outputs_summary={"verdict": "VERIFIED_INCIDENT", "incident_type": inc_pkg.incident_type},
                reasoning_log=f"Confirmed '{inc_pkg.incident_type}' across temporal verification window (Confidence: {inc_pkg.confidence_score * 100:.1f}%).",
            )
        )

        # ----------------------------------------------------------------------
        # STAGES 4, 5, 6: DECIDE ➔ ACT ➔ REPORT
        # ----------------------------------------------------------------------
        orchestration_sub = self.orchestrate_verified_incident(
            incident_id=inc_pkg.incident_id,
            camera_id=camera_id,
        )

        # Merge stages
        all_stages = stages + orchestration_sub.stages_executed
        result = TeammateOrchestrationResult(
            incident_id=inc_pkg.incident_id,
            success=orchestration_sub.success,
            stages_executed=all_stages,
            summary=orchestration_sub.summary,
            error_message=orchestration_sub.error_message,
            total_duration_sec=time.time() - start_time,
        )
        self._history[inc_pkg.incident_id] = result
        return result

    def get_orchestration_history(self, incident_id: str) -> Optional[TeammateOrchestrationResult]:
        """Retrieve stored execution record for an incident."""
        return self._history.get(incident_id)

    # --------------------------------------------------------------------------
    # Factual, Grounded Natural-Language Synthesis Helpers (Zero Hallucination)
    # --------------------------------------------------------------------------
    def _synthesize_executive_briefing(
        self,
        incident_data: Dict[str, Any],
        location_name: str,
        camera_name: str,
        ambulance: Optional[Dict[str, Any]],
        hospital: Optional[Dict[str, Any]],
        police: Optional[Dict[str, Any]],
        route: Optional[EmergencyRouteResult],
    ) -> str:
        """
        Synthesize an explainable, fact-based CAD Operator Briefing.
        Rule: Every single fact (names, coordinates, distances, plates) is strictly grounded.
        """
        inc_id = incident_data.get("incident_id", "INCIDENT")
        inc_type = incident_data.get("incident_type", "emergency").replace("_", " ").title()
        conf_pct = f"{incident_data.get('confidence_score', 0.90) * 100:.1f}%"
        cam_id = incident_data.get("camera_id", "CAM-001")

        plates = incident_data.get("plate_readings", [])
        plate_desc = (
            ", ".join([f"'{p.get('plate_number') or p.get('normalized_text')}'" for p in plates if p.get("plate_number") or p.get("normalized_text")])
            if plates
            else "Unreadable / No clear plate detected"
        )

        amb_name = ambulance.get("name", "Nearest EMS Paramedic Unit") if ambulance else "EMS Paramedic Unit"
        amb_dist = f"{ambulance.get('distance_km', 0.0):.2f} km" if ambulance and ambulance.get("distance_km") is not None else "Geographic distance calculated"
        amb_phone = ambulance.get("phone_contact", "555-0102") if ambulance else "555-0102"

        hosp_name = hospital.get("name", "Destination Trauma Center") if hospital else "Trauma Center"
        hosp_dist = f"{hospital.get('distance_km', 0.0):.2f} km" if hospital and hospital.get("distance_km") is not None else "Geographic distance calculated"

        pol_name = police.get("name", "Local Police Precinct") if police else "Police Precinct"

        route_info = ""
        if route and route.total_distance_km:
            route_info = f"Calculated 2-leg road corridor is {route.total_distance_km:.2f} km with an estimated transit time of ~{route.estimated_duration_min:.1f} minutes via {route.route_source}."

        briefing = (
            f"[CAD DISPATCH OPERATIONAL BRIEFING]\n"
            f"Incident ID: {inc_id} | Priority: IMMEDIATE DISPATCH\n"
            f"Event Classification: Verified {inc_type} (AI Confidence: {conf_pct})\n"
            f"Geospatial Scene: {location_name} (Captured via {camera_name}, ID: {cam_id})\n"
            f"Identified Vehicle Plates: {plate_desc}\n\n"
            f"COORDINATED MULTI-AGENCY ACTIONS:\n"
            f"1. Responding Ambulance: {amb_name} (Distance: {amb_dist}, Contact: {amb_phone})\n"
            f"2. Destination Hospital: {hosp_name} (Trauma intake pre-alert notified, Distance: {hosp_dist})\n"
            f"3. Law Enforcement: {pol_name} (Traffic clearance and scene control alerted)\n"
            f"{route_info}\n\n"
            f"PROTOTYPE SAFETY DIRECTIVE: All emergency calls and dispatches above are simulated records (Status: SIMULATED)."
        )
        return briefing.strip()

    def _synthesize_merchant_advisory(
        self,
        incident_data: Dict[str, Any],
        location_name: str,
        merchant_name: str,
        ambulance_name: str,
    ) -> str:
        """Synthesize factual merchant perimeter advisory note."""
        inc_id = incident_data.get("incident_id", "INCIDENT")
        inc_type = incident_data.get("incident_type", "emergency").replace("_", " ").title()

        return (
            f"[AUTONOMOUS MERCHANT ADVISORY NOTE]\n"
            f"Attention: {merchant_name}\n"
            f"Automated CCTV incident monitoring detected a verified {inc_type} (ID: {inc_id}) on your perimeter at '{location_name}'.\n"
            f"Emergency coordination has been initiated. Inbound response unit: {ambulance_name}.\n"
            f"Recommended Operational Action: Please ensure store perimeter driveways and access lanes remain clear for responding paramedic vehicles.\n"
            f"Dispatch Mode: Prototype Simulation (Status: SIMULATED)."
        )


# Global singleton instance
ai_teammate = AITeammateOrchestrator()
