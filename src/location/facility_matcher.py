"""Facility matching and simulated dispatch module for AutoAlert.

Computes great-circle distance using the Haversine formula to identify nearest
emergency service facilities (hospitals, ambulance units, police stations).
Explicitly adheres to AutoAlert Rules 12 & 13:
All notifications are strictly SIMULATED and labeled as prototypes.
Never claims live police/hospital integration without real authorized credentials.
"""

import math
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger("autoalert.location.matcher")


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth using Haversine formula.

    Formula:
      a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
      c = 2 * atan2(√a, √(1−a))
      d = R * c
    where R is the Earth's mean radius (6371.0 km).
    """
    R = 6371.0  # Earth radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c, 3)


def match_nearest_facilities(
    incident_lat: float,
    incident_lon: float,
    facility_records: List[Dict[str, Any]],
    max_results_per_type: int = 1
) -> Dict[str, List[Dict[str, Any]]]:
    """Find the closest facilities of each type (hospital, ambulance, police) to incident coordinates."""
    categorized: Dict[str, List[Dict[str, Any]]] = {
        "hospital": [],
        "ambulance": [],
        "police": [],
    }

    for fac in facility_records:
        fac_type = fac.get("type", "unknown")
        f_lat = fac.get("latitude")
        f_lon = fac.get("longitude")

        if f_lat is not None and f_lon is not None:
            dist = haversine_distance_km(incident_lat, incident_lon, f_lat, f_lon)
            fac_with_dist = dict(fac)
            fac_with_dist["distance_km"] = dist
            fac_with_dist["simulated_status"] = "pending"
            fac_with_dist["notice"] = "[PROTOTYPE / SIMULATED DISPATCH ONLY]"

            if fac_type in categorized:
                categorized[fac_type].append(fac_with_dist)

    # Sort each category by ascending distance
    result = {}
    for f_type, items in categorized.items():
        items.sort(key=lambda x: x["distance_km"])
        result[f_type] = items[:max_results_per_type]

    return result
