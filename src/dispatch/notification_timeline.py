"""
AutoAlert Transparent Notification Timeline Generator (Stage 22 Enhancement).

Produces an explainable chronological audit trail for simulated emergency dispatches:
  1. Incident Verified (Camera & Location)
  2. Nearest Ambulance/EMS Station Notified (Dispatch request)
  3. Stations Along Route Notified (Corridor clearance & intersection control)
  4. Destination Hospital Notified (Trauma bay preparation)
  5. Ambulance Unit Assigned
  6. Ambulance En Route to Scene
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any


@dataclass
class TimelineEvent:
    """Represents a single transparent notification event in the response lifecycle."""
    step_number: int
    timestamp_str: str
    recipient_name: str
    recipient_type: str  # 'ambulance', 'police', 'traffic_control', 'hospital', 'system'
    status: str          # 'verified', 'notified', 'assigned', 'en_route', 'standby', 'preparing'
    reason: str
    facility_id: Optional[str] = None
    is_simulated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NotificationTimelineGenerator:
    """Generates the transparent simulated notification timeline for verified incidents."""

    @staticmethod
    def generate_timeline(
        incident_type: str,
        camera_id: str,
        camera_name: str,
        location_name: str,
        ambulance_station: Optional[Dict[str, Any]],
        hospital: Optional[Dict[str, Any]],
        stations_along_route: Optional[List[Dict[str, Any]]] = None,
        base_time: Optional[datetime] = None,
    ) -> List[TimelineEvent]:
        """
        Build the chronological sequence of simulated notification events.

        Args:
            incident_type: Name of detected event e.g. 'vehicle_collision'.
            camera_id: Identifier of source camera.
            camera_name: Human readable camera name.
            location_name: Registered camera location.
            ambulance_station: Responding ambulance/EMS facility dict.
            hospital: Destination hospital facility dict.
            stations_along_route: List of facilities identified along response corridor.
            base_time: Base timestamp (defaults to current UTC time).

        Returns:
            List of TimelineEvent objects in chronological order.
        """
        now = base_time or datetime.now(timezone.utc)
        events: List[TimelineEvent] = []
        step = 1

        # Step 1: Incident Verified
        t1 = now.strftime("%H:%M:%S UTC")
        events.append(
            TimelineEvent(
                step_number=step,
                timestamp_str=t1,
                recipient_name=f"AutoAlert Command Center ({camera_name})",
                recipient_type="system",
                status="verified",
                reason=f"{incident_type.replace('_', ' ').title()} verified at {location_name} via {camera_id}.",
            )
        )
        step += 1

        # Step 2: Nearest Ambulance Notified
        if ambulance_station:
            amb_name = ambulance_station.get("name", "Nearest EMS Station")
            t2 = (now + timedelta(seconds=12)).strftime("%H:%M:%S UTC")
            events.append(
                TimelineEvent(
                    step_number=step,
                    timestamp_str=t2,
                    recipient_name=amb_name,
                    recipient_type="ambulance",
                    facility_id=ambulance_station.get("facility_id"),
                    status="notified",
                    reason="Nearest available emergency paramedic unit to incident coordinates.",
                )
            )
            step += 1

        # Step 3: Stations Along Route Notified (Police, Traffic Control)
        if stations_along_route:
            for fac in stations_along_route:
                f_type = str(fac.get("type", "")).lower()
                f_name = fac.get("name", "Corridor Response Point")
                f_id = fac.get("facility_id")

                # Avoid duplicate if hospital or ambulance
                if ambulance_station and f_id == ambulance_station.get("facility_id"):
                    continue
                if hospital and f_id == hospital.get("facility_id"):
                    continue

                dist_to_route = fac.get("distance_to_route_km", 0.0)
                role = fac.get("station_role", "Corridor response point")
                t3 = (now + timedelta(seconds=25)).strftime("%H:%M:%S UTC")
                events.append(
                    TimelineEvent(
                        step_number=step,
                        timestamp_str=t3,
                        recipient_name=f_name,
                        recipient_type=f_type if f_type in ("police", "traffic_control") else "police",
                        facility_id=f_id,
                        status="notified",
                        reason=f"{role} ({dist_to_route} km from ambulance transit corridor).",
                    )
                )
                step += 1

        # Step 4: Destination Hospital Notified
        if hospital:
            hosp_name = hospital.get("name", "Destination Hospital")
            t4 = (now + timedelta(seconds=40)).strftime("%H:%M:%S UTC")
            events.append(
                TimelineEvent(
                    step_number=step,
                    timestamp_str=t4,
                    recipient_name=hosp_name,
                    recipient_type="hospital",
                    facility_id=hospital.get("facility_id"),
                    status="preparing",
                    reason="Emergency trauma bay alerted for incoming patient admission from scene.",
                )
            )
            step += 1

        # Step 5: Ambulance Assigned / Response Started
        if ambulance_station:
            amb_name = ambulance_station.get("name", "EMS Unit")
            t5 = (now + timedelta(seconds=55)).strftime("%H:%M:%S UTC")
            events.append(
                TimelineEvent(
                    step_number=step,
                    timestamp_str=t5,
                    recipient_name=f"{amb_name} (Unit Dispatched)",
                    recipient_type="ambulance",
                    facility_id=ambulance_station.get("facility_id"),
                    status="assigned",
                    reason="Paramedic crew assigned and dispatch acknowledged.",
                )
            )
            step += 1

            # Step 6: Ambulance En Route
            t6 = (now + timedelta(seconds=75)).strftime("%H:%M:%S UTC")
            events.append(
                TimelineEvent(
                    step_number=step,
                    timestamp_str=t6,
                    recipient_name=f"{amb_name} (In Transit)",
                    recipient_type="ambulance",
                    facility_id=ambulance_station.get("facility_id"),
                    status="en_route",
                    reason="Ambulance en route along designated emergency corridor.",
                )
            )

        return events
