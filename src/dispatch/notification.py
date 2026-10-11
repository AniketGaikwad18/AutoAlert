"""
Simulated notification lifecycle and state transition management (Stage 17).

Manages state transitions for simulated emergency dispatches:
pending -> notified -> acknowledged -> responding (or rejected/expired).
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Allowed notification status values
VALID_NOTIFICATION_STATUSES = {
    "pending",
    "notified",
    "acknowledged",
    "responding",
    "rejected",
    "expired",
}

# Allowed status transitions
ALLOWED_TRANSITIONS = {
    "pending": {"notified", "rejected", "expired"},
    "notified": {"acknowledged", "rejected", "expired"},
    "acknowledged": {"responding", "rejected", "expired"},
    "responding": {"completed", "rejected", "expired"},
}


@dataclass
class SimulatedNotificationLogEntry:
    """Entry in status transition history log."""
    previous_status: str
    new_status: str
    timestamp: str
    reason: str


@dataclass
class SimulatedNotification:
    """Dataclass representing a simulated emergency dispatch notification."""
    incident_id: str
    facility_id: str
    facility_type: str
    facility_name: str
    notification_id: str = field(default_factory=lambda: f"NOTIF-{uuid.uuid4().hex[:8].upper()}")
    status: str = "pending"
    distance_km: Optional[float] = None
    message: str = ""
    is_simulated: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    history: List[Dict[str, Any]] = field(default_factory=list)

    def transition_to(self, new_status: str, reason: str = "") -> bool:
        """
        Transition notification to a new status if valid.

        Args:
            new_status: Target status string.
            reason: Explanation or note for status change.

        Returns:
            True if transition succeeded; False otherwise.
        """
        new_status_lower = new_status.lower()
        if new_status_lower not in VALID_NOTIFICATION_STATUSES:
            logger.error("Invalid status '%s' requested for notification %s", new_status, self.notification_id)
            return False

        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status_lower not in allowed and new_status_lower != self.status:
            logger.warning(
                "Invalid status transition from '%s' to '%s' for notification %s",
                self.status,
                new_status,
                self.notification_id,
            )

        old_status = self.status
        self.status = new_status_lower
        self.updated_at = datetime.now(timezone.utc).isoformat()

        entry = {
            "previous_status": old_status,
            "new_status": self.status,
            "timestamp": self.updated_at,
            "reason": reason or f"Transitioned from {old_status} to {self.status}",
        }
        self.history.append(entry)
        logger.info(
            "Simulated Notification %s (%s -> %s): %s",
            self.notification_id,
            old_status,
            self.status,
            reason,
        )
        return True
