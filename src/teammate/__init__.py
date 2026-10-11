"""
AutoAlert AI Teammate Module.

Exports:
  - WorkflowStage
  - WorkflowStageRecord
  - StructuredIncidentSummary
  - TeammateOrchestrationResult
  - AITeammateOrchestrator
  - ai_teammate (singleton)
  - Tool functions (tool_get_incident, tool_get_location, etc.)
"""

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
from src.teammate.orchestrator import (
    AITeammateOrchestrator,
    ai_teammate,
)

__all__ = [
    "WorkflowStage",
    "WorkflowStageRecord",
    "StructuredIncidentSummary",
    "TeammateOrchestrationResult",
    "AITeammateOrchestrator",
    "ai_teammate",
    "tool_get_incident",
    "tool_get_location",
    "tool_find_facilities",
    "tool_calculate_distances",
    "tool_generate_route",
    "tool_create_notification_records",
    "tool_create_incident_summary",
]
