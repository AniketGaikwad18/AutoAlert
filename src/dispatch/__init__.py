"""
AutoAlert Dispatch, Notification, and Routing Package.
"""

from src.dispatch.matching import haversine_distance, FacilityMatcher
from src.dispatch.notification import SimulatedNotification, SimulatedNotificationLogEntry
from src.dispatch.notification_timeline import NotificationTimelineGenerator, TimelineEvent
from src.dispatch.notification_service import (
    NotificationRecord,
    NotificationService,
    notification_service,
)
from src.dispatch.routing import (
    RouteEngine,
    RouteLeg,
    RoutePoint,
    EmergencyRouteResult,
    route_engine,
)

__all__ = [
    "haversine_distance",
    "FacilityMatcher",
    "SimulatedNotification",
    "SimulatedNotificationLogEntry",
    "NotificationTimelineGenerator",
    "TimelineEvent",
    "NotificationRecord",
    "NotificationService",
    "notification_service",
    "RouteEngine",
    "RouteLeg",
    "RoutePoint",
    "EmergencyRouteResult",
    "route_engine",
]
