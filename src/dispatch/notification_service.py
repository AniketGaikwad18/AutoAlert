"""
AutoAlert Modular Notification Service (Phase 14).

Provides simulated emergency notification dispatches and chronological timeline generation:
  - notify_ambulance()
  - notify_police()
  - notify_hospital()
  - notify_merchant()

CRITICAL SAFETY & PROTOTYPE DIRECTIVE:
ALL notifications are strictly SIMULATED.
Status clearly indicates 'SIMULATED'.
No external 911/police/ambulance/SMS telecommunication is executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
import logging
import uuid
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class NotificationRecord:
    """Structured record for a simulated emergency notification dispatch."""
    notification_id: str
    incident_id: str
    recipient: str
    recipient_type: str  # 'ambulance', 'police', 'hospital', 'merchant', 'system'
    timestamp: str       # ISO 8601 UTC timestamp
    status: str = "SIMULATED"  # Status explicitly indicates SIMULATED
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    is_simulated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert notification record to plain dictionary."""
        return asdict(self)


class NotificationService:
    """Modular Notification Service for simulated emergency dispatches."""

    def __init__(self) -> None:
        # Memory storage: incident_id -> List[NotificationRecord]
        self._incident_records: Dict[str, List[NotificationRecord]] = {}
        # Global list of all records in chronological order
        self._all_records: List[NotificationRecord] = []

    def _generate_id(self, prefix: str = "NOTIF") -> str:
        """Generate unique notification identifier."""
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def _record_notification(
        self,
        incident_id: str,
        recipient: str,
        recipient_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        custom_timestamp: Optional[str] = None,
    ) -> NotificationRecord:
        """Internal helper to create, store, and log a simulated notification record."""
        now_iso = custom_timestamp or datetime.now(timezone.utc).isoformat()
        notif_id = self._generate_id(prefix=f"NOTIF-{recipient_type.upper()[:3]}")

        record = NotificationRecord(
            notification_id=notif_id,
            incident_id=incident_id,
            recipient=recipient,
            recipient_type=recipient_type.lower(),
            timestamp=now_iso,
            status="SIMULATED",
            message=message,
            details=details or {},
            is_simulated=True,
        )

        if incident_id not in self._incident_records:
            self._incident_records[incident_id] = []
        self._incident_records[incident_id].append(record)
        self._all_records.append(record)

        logger.info(
            "SIMULATED Notification [%s] to %s (%s): %s",
            record.notification_id,
            record.recipient,
            record.recipient_type,
            record.message,
        )
        return record

    def notify_ambulance(
        self,
        incident_id: str,
        recipient: str = "Central EMS Ambulance Station (Simulated)",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> NotificationRecord:
        """Send simulated dispatch notification to responding ambulance / paramedic unit."""
        msg = message or f"[SIMULATED AMBULANCE DISPATCH] Incident {incident_id} verified. Emergency paramedic dispatch requested."
        return self._record_notification(
            incident_id=incident_id,
            recipient=recipient,
            recipient_type="ambulance",
            message=msg,
            details=details,
            custom_timestamp=timestamp,
        )

    def notify_police(
        self,
        incident_id: str,
        recipient: str = "Local Police Precinct (Simulated)",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> NotificationRecord:
        """Send simulated dispatch notification to police / traffic control."""
        msg = message or f"[SIMULATED POLICE ALERT] Incident {incident_id} verified. Traffic clearance and scene control requested."
        return self._record_notification(
            incident_id=incident_id,
            recipient=recipient,
            recipient_type="police",
            message=msg,
            details=details,
            custom_timestamp=timestamp,
        )

    def notify_hospital(
        self,
        incident_id: str,
        recipient: str = "City Care Trauma Hospital (Simulated)",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> NotificationRecord:
        """Send simulated pre-arrival alert to destination hospital / trauma center."""
        msg = message or f"[SIMULATED HOSPITAL PRE-ALERT] Incident {incident_id} verified. Trauma bay standby requested for inbound patient."
        return self._record_notification(
            incident_id=incident_id,
            recipient=recipient,
            recipient_type="hospital",
            message=msg,
            details=details,
            custom_timestamp=timestamp,
        )

    def notify_merchant(
        self,
        incident_id: str,
        recipient: str = "Facility Merchant / Store Manager (Simulated)",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> NotificationRecord:
        """Send simulated incident notification to merchant / store manager."""
        msg = message or f"[SIMULATED MERCHANT ADVISORY] Incident {incident_id} verified on merchant CCTV perimeter. Response coordinated."
        return self._record_notification(
            incident_id=incident_id,
            recipient=recipient,
            recipient_type="merchant",
            message=msg,
            details=details,
            custom_timestamp=timestamp,
        )

    def create_incident_timeline(
        self,
        incident_id: str,
        camera_id: str = "CAM-001",
        camera_name: str = "Perimeter Junction Camera",
        location_name: str = "Storefront Perimeter",
        ambulance_name: str = "Central EMS Ambulance (Simulated)",
        police_name: str = "Shivajinagar Police Station (Simulated)",
        hospital_name: str = "City Care Trauma Hospital (Simulated)",
        merchant_name: str = "Store Operations Team (Simulated)",
        base_time: Optional[datetime] = None,
    ) -> List[NotificationRecord]:
        """
        Build a complete chronological notification timeline for an incident:
          1. System Verification Alert
          2. Ambulance Paramedic Unit Notified
          3. Police & Traffic Clearance Notified
          4. Hospital Trauma Bay Notified
          5. Merchant / Store Manager Notified
        """
        now = base_time or datetime.now(timezone.utc)
        timeline: List[NotificationRecord] = []

        # 1. System Alert
        t1 = (now).isoformat()
        sys_rec = self._record_notification(
            incident_id=incident_id,
            recipient=f"AutoAlert AI Command Center ({camera_name})",
            recipient_type="system",
            message=f"[SIMULATED SYSTEM EVENT] Verified emergency incident at {location_name} via {camera_id}.",
            details={"camera_id": camera_id, "location_name": location_name},
            custom_timestamp=t1,
        )
        timeline.append(sys_rec)

        # 2. Ambulance
        t2 = (now + timedelta(seconds=8)).isoformat()
        amb_rec = self.notify_ambulance(
            incident_id=incident_id,
            recipient=ambulance_name,
            message=f"[SIMULATED AMBULANCE DISPATCH] Dispatch request sent to {ambulance_name} for incident at {location_name}.",
            details={"location": location_name, "dispatch_priority": "High"},
            timestamp=t2,
        )
        timeline.append(amb_rec)

        # 3. Police
        t3 = (now + timedelta(seconds=16)).isoformat()
        pol_rec = self.notify_police(
            incident_id=incident_id,
            recipient=police_name,
            message=f"[SIMULATED POLICE DISPATCH] Traffic clearance and incident management alert sent to {police_name}.",
            details={"location": location_name},
            timestamp=t3,
        )
        timeline.append(pol_rec)

        # 4. Hospital
        t4 = (now + timedelta(seconds=24)).isoformat()
        hosp_rec = self.notify_hospital(
            incident_id=incident_id,
            recipient=hospital_name,
            message=f"[SIMULATED HOSPITAL PRE-ARRIVAL] Trauma intake notification sent to {hospital_name}.",
            details={"trauma_level": "Level 1 Standby"},
            timestamp=t4,
        )
        timeline.append(hosp_rec)

        # 5. Merchant
        t5 = (now + timedelta(seconds=32)).isoformat()
        merch_rec = self.notify_merchant(
            incident_id=incident_id,
            recipient=merchant_name,
            message=f"[SIMULATED MERCHANT NOTIFICATION] Automated perimeter incident advisory sent to {merchant_name}.",
            details={"perimeter_zone": location_name},
            timestamp=t5,
        )
        timeline.append(merch_rec)

        return timeline

    def get_incident_timeline(self, incident_id: str) -> List[NotificationRecord]:
        """Retrieve chronological notification timeline for a specific incident."""
        records = self._incident_records.get(incident_id, [])
        # Sort by timestamp
        return sorted(records, key=lambda r: r.timestamp)

    def list_all_notifications(
        self, incident_id: Optional[str] = None, recipient_type: Optional[str] = None
    ) -> List[NotificationRecord]:
        """List all notification records with optional filtering."""
        records = self._all_records
        if incident_id:
            records = [r for r in records if r.incident_id == incident_id]
        if recipient_type:
            target_type = recipient_type.lower()
            records = [r for r in records if r.recipient_type == target_type]
        return sorted(records, key=lambda r: r.timestamp)

    def clear(self) -> None:
        """Clear all stored notification records."""
        self._incident_records.clear()
        self._all_records.clear()
        logger.info("NotificationService cleared")


# Global singleton instance
notification_service = NotificationService()
