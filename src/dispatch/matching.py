"""
Facility matching engine using Haversine distance calculation (Stage 17).

Provides mathematical distance calculations between incident GPS coordinates and
emergency response facilities (hospitals, police stations, EMS stations).
"""

from __future__ import annotations

import math
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Earth's mean radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on the Earth
    in kilometers using the Haversine formula.

    Formula:
      a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
      c = 2 * atan2(√a, √(1-a))
      d = R * c

    Args:
        lat1: Latitude of point 1 in decimal degrees.
        lon1: Longitude of point 1 in decimal degrees.
        lat2: Latitude of point 2 in decimal degrees.
        lon2: Longitude of point 2 in decimal degrees.

    Returns:
        Distance in kilometers rounded to 3 decimal places.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = EARTH_RADIUS_KM * c
    return round(distance, 3)


class FacilityMatcher:
    """Matches emergency response facilities to incident locations."""

    @staticmethod
    def match_facilities(
        incident_lat: Optional[float],
        incident_lon: Optional[float],
        facilities: List[Dict[str, Any]],
        facility_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rank facilities by Haversine distance from incident GPS coordinates.

        If valid GPS coordinates are provided, facilities are sorted by distance_km.
        If coordinates are missing/None, facilities are returned with distance_km = None.

        Args:
            incident_lat: Latitude of incident (or None if missing).
            incident_lon: Longitude of incident (or None if missing).
            facilities: List of facility dictionary records.
            facility_type: Optional filter e.g. 'hospital', 'police', 'ambulance'.
            limit: Max facilities to return.

        Returns:
            List of facility records augmented with 'distance_km'.
        """
        filtered = facilities
        if facility_type:
            target_type = facility_type.lower()
            filtered = [f for f in facilities if f.get("type", "").lower() == target_type]

        results = []
        has_coords = (
            incident_lat is not None
            and incident_lon is not None
            and -90.0 <= incident_lat <= 90.0
            and -180.0 <= incident_lon <= 180.0
        )

        for fac in filtered:
            fac_copy = dict(fac)
            fac_lat = fac.get("latitude")
            fac_lon = fac.get("longitude")

            if has_coords and fac_lat is not None and fac_lon is not None:
                try:
                    dist = haversine_distance(
                        float(incident_lat), float(incident_lon), float(fac_lat), float(fac_lon)
                    )
                    fac_copy["distance_km"] = dist
                except (ValueError, TypeError):
                    fac_copy["distance_km"] = None
            else:
                fac_copy["distance_km"] = None

            results.append(fac_copy)

        if has_coords:
            # Sort facilities with valid distance first
            results.sort(
                key=lambda x: (x["distance_km"] is None, x["distance_km"] if x["distance_km"] is not None else float("inf"))
            )

        return results[:limit]
