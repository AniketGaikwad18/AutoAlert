"""
AutoAlert Emergency Routing Engine (OpenStreetMap / OSRM Integration & Transparent Route Analysis).

Provides 2-Leg Ambulance Dispatch Route Calculation:
  Leg 1: Responding Ambulance/EMS Station -> Incident Location (Pickup)
  Leg 2: Incident Location -> Destination Hospital (Trauma Center)

Features:
  - Open-source road routing via OSRM (OpenStreetMap data) with high-fidelity local geometric fallback.
  - Transparent distinction between Geographic Distance, Road Route Distance, and Estimated Travel Time.
  - Proximity detection of Response Stations along/near the ambulance corridor.
  - Zero paid Google Maps API dependencies and no hard-coded API keys.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import requests

from src.dispatch.matching import haversine_distance

logger = logging.getLogger(__name__)

# Default OSRM Public Server URL
DEFAULT_OSRM_URL = "http://router.project-osrm.org"
OSRM_TIMEOUT_SEC = 2.5
NOMINAL_EMERGENCY_SPEED_KMH = 40.0  # Average nominal emergency transit speed for time estimation
ROAD_CURVATURE_FACTOR = 1.25  # Road network distance vs straight-line geometric distance factor


@dataclass
class RoutePoint:
    """Represents a geographic waypoint in decimal degrees."""
    latitude: float
    longitude: float
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteLeg:
    """Single transit leg of an emergency route."""
    origin_name: str
    destination_name: str
    distance_km: float
    duration_min: float
    coordinates: List[Tuple[float, float]]  # List of (latitude, longitude)
    source: str = "OpenStreetMap / OSRM"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_name": self.origin_name,
            "destination_name": self.destination_name,
            "distance_km": self.distance_km,
            "duration_min": self.duration_min,
            "coordinates": self.coordinates,
            "source": self.source,
        }


@dataclass
class EmergencyRouteResult:
    """Complete 2-leg emergency ambulance response route."""
    origin_station: Dict[str, Any]
    incident_location: Dict[str, Any]
    destination_hospital: Dict[str, Any]
    total_distance_km: float
    estimated_duration_min: float
    coordinates: List[Tuple[float, float]]
    legs: List[RouteLeg]
    stations_along_route: List[Dict[str, Any]]
    route_source: str
    is_real_road_network: bool
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_station": self.origin_station,
            "incident_location": self.incident_location,
            "destination_hospital": self.destination_hospital,
            "total_distance_km": self.total_distance_km,
            "estimated_duration_min": self.estimated_duration_min,
            "coordinates": self.coordinates,
            "legs": [leg.to_dict() for leg in self.legs],
            "stations_along_route": self.stations_along_route,
            "route_source": self.route_source,
            "is_real_road_network": self.is_real_road_network,
            "summary": self.summary,
        }


class RouteEngine:
    """Calculates road-network routing and identifies response stations along emergency corridors."""

    haversine = staticmethod(haversine_distance)

    def __init__(self, osrm_base_url: str = DEFAULT_OSRM_URL, timeout_sec: float = OSRM_TIMEOUT_SEC) -> None:
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def _query_osrm(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> Optional[Tuple[List[Tuple[float, float]], float, float]]:
        """Query OSRM public API for driving route between two points."""
        try:
            url = f"{self.osrm_base_url}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
            params = {"overview": "full", "geometries": "geojson", "steps": "false"}
            res = requests.get(url, params=params, timeout=self.timeout_sec)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    primary_route = data["routes"][0]
                    dist_meters = float(primary_route.get("distance", 0.0))
                    duration_sec = float(primary_route.get("duration", 0.0))
                    geojson_coords = primary_route.get("geometry", {}).get("coordinates", [])
                    # GeoJSON is [lon, lat], convert to [lat, lon]
                    coords = [(float(c[1]), float(c[0])) for c in geojson_coords]
                    dist_km = round(dist_meters / 1000.0, 2)
                    dur_min = round(duration_sec / 60.0, 1)
                    return coords, dist_km, dur_min
        except Exception as e:
            logger.debug("OSRM route query failed (%s), using geometric road fallback.", e)
        return None

    def _build_fallback_leg(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        origin_name: str,
        dest_name: str,
    ) -> RouteLeg:
        """Construct realistic multi-point geometric road fallback leg when offline."""
        straight_dist = haversine_distance(lat1, lon1, lat2, lon2)
        road_dist = round(max(0.1, straight_dist * ROAD_CURVATURE_FACTOR), 2)
        est_duration = round((road_dist / NOMINAL_EMERGENCY_SPEED_KMH) * 60.0, 1)

        # Generate realistic intermediate road waypoints with minor curvature
        num_segments = max(4, int(road_dist * 3))
        coords: List[Tuple[float, float]] = []
        for i in range(num_segments + 1):
            t = i / float(num_segments)
            # Base linear interpolation
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            # Add subtle orthogonal curvature (sinusoidal offset) to simulate road curve
            offset = math.sin(t * math.pi) * 0.0015
            coords.append((round(lat + offset, 6), round(lon - offset * 0.5, 6)))

        return RouteLeg(
            origin_name=origin_name,
            destination_name=dest_name,
            distance_km=road_dist,
            duration_min=est_duration,
            coordinates=coords,
            source="Demo Road Network (Fallback)",
        )

    def calculate_leg(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        origin_name: str,
        dest_name: str,
    ) -> RouteLeg:
        """Calculate single transit leg with OSRM, falling back to geometric road network."""
        osrm_res = self._query_osrm(lat1, lon1, lat2, lon2)
        if osrm_res:
            coords, dist_km, dur_min = osrm_res
            return RouteLeg(
                origin_name=origin_name,
                destination_name=dest_name,
                distance_km=dist_km,
                duration_min=dur_min,
                coordinates=coords,
                source="OpenStreetMap / OSRM Road Route",
            )
        return self._build_fallback_leg(lat1, lon1, lat2, lon2, origin_name, dest_name)

    def find_stations_along_route(
        self,
        route_coords: List[Tuple[float, float]],
        facilities: List[Dict[str, Any]],
        max_distance_km: float = 1.5,
    ) -> List[Dict[str, Any]]:
        """
        Identify emergency facilities and response points within proximity threshold of the route.

        Args:
            route_coords: List of (latitude, longitude) along the ambulance route.
            facilities: List of all registered facilities.
            max_distance_km: Proximity buffer in km to be considered along the corridor.

        Returns:
            List of facilities augmented with 'distance_to_route_km' and 'station_role'.
        """
        stations_along: List[Dict[str, Any]] = []
        if not route_coords:
            return stations_along

        for fac in facilities:
            fac_dict = fac.model_dump() if hasattr(fac, "model_dump") else (fac.dict() if hasattr(fac, "dict") else dict(fac))
            fac_lat = fac_dict.get("latitude")
            fac_lon = fac_dict.get("longitude")
            if fac_lat is None or fac_lon is None:
                continue

            try:
                f_lat = float(fac_lat)
                f_lon = float(fac_lon)
            except (ValueError, TypeError):
                continue

            # Calculate minimum distance from facility to any point on route
            min_dist = min(
                haversine_distance(f_lat, f_lon, r_lat, r_lon) for r_lat, r_lon in route_coords
            )

            if min_dist <= max_distance_km:
                fac_copy = dict(fac_dict)
                fac_copy["distance_to_route_km"] = round(min_dist, 2)

                # Assign realistic role along route
                f_type = str(fac_dict.get("type", "")).lower()
                if "police" in f_type:
                    fac_copy["station_role"] = "Traffic Clearing & Intersection Control"
                elif "hospital" in f_type:
                    fac_copy["station_role"] = "Destination Emergency Trauma Bay"
                elif "ambulance" in f_type or "ems" in f_type:
                    fac_copy["station_role"] = "Paramedic Unit Dispatch / Staging"
                else:
                    fac_copy["station_role"] = "Corridor Response Monitoring"

                stations_along.append(fac_copy)

        # Sort by distance to route
        stations_along.sort(key=lambda s: s.get("distance_to_route_km", float("inf")))
        return stations_along

    def calculate_emergency_route(
        self,
        origin_station: Dict[str, Any],
        incident_location: Dict[str, Any],
        destination_hospital: Dict[str, Any],
        all_facilities: Optional[List[Dict[str, Any]]] = None,
        max_proximity_km: float = 1.5,
    ) -> Optional[EmergencyRouteResult]:
        """
        Calculate the full 2-leg emergency route:
          Leg 1: Ambulance Station -> Incident Location (Pickup)
          Leg 2: Incident Location -> Destination Hospital (Trauma Center)

        Args:
            origin_station: Responding ambulance/EMS station dictionary.
            incident_location: Incident location dictionary (name, latitude, longitude).
            destination_hospital: Destination hospital dictionary.
            all_facilities: Optional list of all facilities to check for stations along route.
            max_proximity_km: Proximity threshold for stations near route.

        Returns:
            EmergencyRouteResult or None if coordinates are missing.
        """
        try:
            o_lat, o_lon = float(origin_station["latitude"]), float(origin_station["longitude"])
            i_lat, i_lon = float(incident_location["latitude"]), float(incident_location["longitude"])
            h_lat, h_lon = float(destination_hospital["latitude"]), float(destination_hospital["longitude"])
        except (KeyError, TypeError, ValueError) as err:
            logger.warning("Cannot calculate route due to missing coordinates: %s", err)
            return None

        o_name = origin_station.get("name", "Ambulance Station")
        i_name = incident_location.get("name", "Incident Location")
        h_name = destination_hospital.get("name", "Destination Hospital")

        # Leg 1: Ambulance -> Incident
        leg1 = self.calculate_leg(o_lat, o_lon, i_lat, i_lon, origin_name=o_name, dest_name=i_name)
        # Leg 2: Incident -> Hospital
        leg2 = self.calculate_leg(i_lat, i_lon, h_lat, h_lon, origin_name=i_name, dest_name=h_name)

        combined_coords = leg1.coordinates + leg2.coordinates[1:]
        total_dist_km = round(leg1.distance_km + leg2.distance_km, 2)
        total_dur_min = round(leg1.duration_min + leg2.duration_min, 1)

        is_real = (leg1.source.startswith("OpenStreetMap") and leg2.source.startswith("OpenStreetMap"))
        route_source = "OpenStreetMap / OSRM Road Route" if is_real else "Demo Road Network (Fallback)"

        # Find stations along route
        stations_along = (
            self.find_stations_along_route(combined_coords, all_facilities, max_distance_km=max_proximity_km)
            if all_facilities
            else []
        )

        summary_msg = (
            f"Ambulance Route: {o_name} -> {i_name} -> {h_name} "
            f"({total_dist_km} km, ~{total_dur_min} mins est.)"
        )

        return EmergencyRouteResult(
            origin_station=origin_station,
            incident_location=incident_location,
            destination_hospital=destination_hospital,
            total_distance_km=total_dist_km,
            estimated_duration_min=total_dur_min,
            coordinates=combined_coords,
            legs=[leg1, leg2],
            stations_along_route=stations_along,
            route_source=route_source,
            is_real_road_network=is_real,
            summary=summary_msg,
        )

    def plan_emergency_route(
        self,
        ambulance_lat: float,
        ambulance_lon: float,
        incident_lat: float,
        incident_lon: float,
        hospital_lat: float,
        hospital_lon: float,
        ambulance_id: str = "EMS-001",
        ambulance_name: str = "Ambulance Station",
        hospital_id: str = "HOSP-001",
        hospital_name: str = "Trauma Center",
        all_facilities: Optional[List[Dict[str, Any]]] = None,
    ) -> EmergencyRouteResult:
        """Convenience method for calculating route from flat arguments."""
        amb_dict = {"facility_id": ambulance_id, "name": ambulance_name, "latitude": ambulance_lat, "longitude": ambulance_lon}
        inc_dict = {"name": "Incident Location", "latitude": incident_lat, "longitude": incident_lon}
        hosp_dict = {"facility_id": hospital_id, "name": hospital_name, "latitude": hospital_lat, "longitude": hospital_lon}
        res = self.calculate_emergency_route(amb_dict, inc_dict, hosp_dict, all_facilities=all_facilities)
        if res is None:
            # Fallback
            leg1 = self._build_fallback_leg(ambulance_lat, ambulance_lon, incident_lat, incident_lon, ambulance_name, "Incident Location")
            leg2 = self._build_fallback_leg(incident_lat, incident_lon, hospital_lat, hospital_lon, "Incident Location", hospital_name)
            return EmergencyRouteResult(
                origin_station=amb_dict,
                incident_location=inc_dict,
                destination_hospital=hosp_dict,
                total_distance_km=round(leg1.distance_km + leg2.distance_km, 2),
                estimated_duration_min=round(leg1.duration_min + leg2.duration_min, 1),
                coordinates=leg1.coordinates + leg2.coordinates[1:],
                legs=[leg1, leg2],
                stations_along_route=[],
                route_source="Demo Road Network (Fallback)",
                is_real_road_network=False,
                summary=f"Ambulance Route (Fallback): {ambulance_name} -> Incident -> {hospital_name}",
            )
        return res


# Global singleton route engine
route_engine = RouteEngine()
