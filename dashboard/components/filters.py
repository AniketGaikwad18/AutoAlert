"""
Sidebar and top-bar filter components for the AutoAlert Command Center Dashboard.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import streamlit as st


def render_incident_filters(
    available_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Render incident sidebar filter controls and return active filter state."""
    st.sidebar.markdown("### 🔍 Incident Filters")

    types_options = ["All Types"] + (
        available_types
        if available_types
        else [
            "vehicle_collision",
            "prolonged_person_motionlessness",
            "red_liquid_visual_anomaly",
        ]
    )
    selected_type = st.sidebar.selectbox("Filter by Incident Type", types_options)

    status_options = [
        "All Statuses",
        "verified",
        "candidate",
        "verifying",
        "rejected",
        "expired",
    ]
    selected_status = st.sidebar.selectbox("Filter by Verification Status", status_options)

    search_query = st.sidebar.text_input("Search (Incident ID / Camera)", "")

    return {
        "incident_type": None if selected_type == "All Types" else selected_type,
        "verification_status": None if selected_status == "All Statuses" else selected_status,
        "search_query": search_query.strip(),
    }
