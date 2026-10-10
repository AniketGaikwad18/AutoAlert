"""Metric overview cards component for AutoAlert Command Center."""

import streamlit as st
from typing import List, Dict, Any


def render_metric_cards(incidents: List[Dict[str, Any]], cameras: List[Dict[str, Any]]) -> None:
    """Render top summary KPIs."""
    total_incidents = len(incidents)
    pending_count = sum(1 for inc in incidents if inc.get("notification_status") == "pending")
    active_cams = sum(1 for c in cameras if c.get("is_active", True))
    collisions = sum(1 for inc in incidents if "collision" in inc.get("incident_type", ""))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(label="Total Verified Incidents", value=total_incidents)
    with c2:
        st.metric(label="Pending Dispatch", value=pending_count, delta=f"{pending_count} awaiting" if pending_count else "Clear")
    with c3:
        st.metric(label="Monitored Cameras", value=active_cams)
    with c4:
        st.metric(label="Vehicle Collisions", value=collisions)
