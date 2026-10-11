"""
Emergency Facility Registry and Dispatch Matcher (Phases 11–13).

Manages simulated emergency facilities (hospitals, ambulance depots, police stations),
performs Haversine distance calculations, and resolves nearest emergency units for incident locations.

Architectural Directives:
1. All facility listings and dispatches are simulated prototype data.
2. Does NOT use paid Google Maps APIs (uses Haversine and OpenStreetMap/OSRM).
3. Provides deterministic nearest-facility selection for ambulance, hospital, and police units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from typing import Dict, List, Optional, Any
import yaml

from backend.schemas.facility import FacilitySchema
from src.dispatch.matching import FacilityMatcher, haversine_distance

logger = logging.getLogger(__name__)

DEFAULT_FACILITIES_PATH = os.path.join("config", "facilities.yaml")


@dataclass
class IncidentDispatchPlan:
    """Structured response container for emergency unit matching and nearby services."""
    incident_lat: Optional[float]
    incident_lon: Optional[float]
    nearest_ambulance: Optional[Dict[str, Any]]
    nearest_hospital: Optional[Dict[str, Any]]
    nearest_police: Optional[Dict[str, Any]]
    nearby_facilities: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert dispatch plan to plain dictionary."""
        return {
            "incident_lat": self.incident_lat,
            "incident_lon": self.incident_lon,
            "nearest_ambulance": self.nearest_ambulance,
            "nearest_hospital": self.nearest_hospital,
            "nearest_police": self.nearest_police,
            "nearby_facilities": self.nearby_facilities,
            "summary": self.summary,
        }


class FacilityRegistry:
    """Central registry for managing emergency facilities and computing spatial proximity."""

    def __init__(self, config_path: str = DEFAULT_FACILITIES_PATH) -> None:
        self.config_path = config_path
        self._facilities: Dict[str, FacilitySchema] = {}
        self.reload()

    def reload(self) -> None:
        """Reload facilities from YAML configuration file, falling back to database repository."""
        self._facilities.clear()

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    fac_list = data.get("facilities", [])
                    for fac_dict in fac_list:
                        schema = FacilitySchema(**fac_dict)
                        self._facilities[schema.facility_id] = schema
                logger.info("Loaded %d facility(ies) from '%s'", len(self._facilities), self.config_path)
                return
            except Exception as e:
                logger.warning("Could not parse facility configuration file '%s': %s", self.config_path, e)

        # Fallback: Load from backend database repository if available
        try:
            from backend.repository import repository
            db_facs = repository.list_facilities()
            for fac in db_facs:
                self._facilities[fac.facility_id] = fac
            logger.info("Loaded %d facility(ies) from database repository fallback", len(self._facilities))
        except Exception as e:
            logger.warning("Could not load facilities from database repository: %s", e)

    def register_facility(self, facility: FacilitySchema) -> FacilitySchema:
        """Register or update a facility in the in-memory registry."""
        self._facilities[facility.facility_id] = facility
        return facility

    def get_facility(self, facility_id: str) -> Optional[FacilitySchema]:
        """Look up a facility by unique identifier."""
        return self._facilities.get(facility_id)

    def list_facilities(
        self,
        facility_type: Optional[str] = None,
        available_only: bool = False,
    ) -> List[FacilitySchema]:
        """List registered facilities with optional type and availability filtering."""
        facilities = list(self._facilities.values())
        if facility_type:
            target_type = facility_type.lower()
            facilities = [f for f in facilities if f.type.lower() == target_type]
        if available_only:
            facilities = [f for f in facilities if f.available and getattr(f, "enabled", True)]
        return facilities

    def match_nearest(
        self,
        incident_lat: Optional[float],
        incident_lon: Optional[float],
        facility_type: Optional[str] = None,
        limit: int = 5,
        available_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Rank facilities by Haversine distance from incident GPS coordinates."""
        fac_list = [f.model_dump() for f in self.list_facilities(facility_type=facility_type, available_only=available_only)]
        return FacilityMatcher.match_facilities(
            incident_lat=incident_lat,
            incident_lon=incident_lon,
            facilities=fac_list,
            facility_type=facility_type,
            limit=limit,
        )

    def match_nearest_ambulance(
        self, incident_lat: Optional[float], incident_lon: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """Match the single closest available ambulance/EMS depot."""
        matched = self.match_nearest(incident_lat, incident_lon, facility_type="ambulance", limit=1)
        return matched[0] if matched else None

    def match_nearest_hospital(
        self, incident_lat: Optional[float], incident_lon: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """Match the single closest available trauma center / hospital."""
        matched = self.match_nearest(incident_lat, incident_lon, facility_type="hospital", limit=1)
        return matched[0] if matched else None

    def match_nearest_police(
        self, incident_lat: Optional[float], incident_lon: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """Match the single closest police / traffic station."""
        matched = self.match_nearest(incident_lat, incident_lon, facility_type="police", limit=1)
        return matched[0] if matched else None

    def plan_emergency_dispatch(
        self,
        incident_lat: Optional[float],
        incident_lon: Optional[float],
    ) -> IncidentDispatchPlan:
        """
        Create structured emergency dispatch plan for an incident location:
          - Nearest available Ambulance (Paramedic response)
          - Destination Hospital (Trauma intake)
          - Nearby Police Station (Traffic/investigation response)
          - Grouped nearest facilities
        """
        amb = self.match_nearest_ambulance(incident_lat, incident_lon)
        hosp = self.match_nearest_hospital(incident_lat, incident_lon)
        pol = self.match_nearest_police(incident_lat, incident_lon)

        all_amb = self.match_nearest(incident_lat, incident_lon, facility_type="ambulance", limit=5)
        all_hosp = self.match_nearest(incident_lat, incident_lon, facility_type="hospital", limit=5)
        all_pol = self.match_nearest(incident_lat, incident_lon, facility_type="police", limit=5)

        summary_parts = []
        if amb:
            dist_str = f" ({amb.get('distance_km')} km)" if amb.get("distance_km") is not None else ""
            summary_parts.append(f"Ambulance: {amb.get('name')}{dist_str}")
        if hosp:
            dist_str = f" ({hosp.get('distance_km')} km)" if hosp.get("distance_km") is not None else ""
            summary_parts.append(f"Hospital: {hosp.get('name')}{dist_str}")
        if pol:
            dist_str = f" ({pol.get('distance_km')} km)" if pol.get("distance_km") is not None else ""
            summary_parts.append(f"Police: {pol.get('name')}{dist_str}")

        summary = " | ".join(summary_parts) if summary_parts else "No matching facilities found."

        return IncidentDispatchPlan(
            incident_lat=incident_lat,
            incident_lon=incident_lon,
            nearest_ambulance=amb,
            nearest_hospital=hosp,
            nearest_police=pol,
            nearby_facilities={
                "ambulance": all_amb,
                "hospital": all_hosp,
                "police": all_pol,
            },
            summary=summary,
        )


# Global singleton instance
facility_registry = FacilityRegistry()
