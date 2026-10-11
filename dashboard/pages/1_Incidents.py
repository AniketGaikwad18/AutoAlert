"""
AutoAlert AI — Incident Archive & Audit Center (Page 1).

Filter, search, inspect, and export verified emergency detection packages.
"""

from __future__ import annotations

import json
import streamlit as st
from dashboard.api_client import DashboardAPIClient

st.set_page_config(
    page_title="Incidents Feed — AutoAlert AI",
    page_icon="🚨",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f8fafc !important;
        color: #0f172a !important;
    }
    .header-card {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 1rem 1.4rem !important;
        margin-bottom: 1.25rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    .op-card {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 1.25rem 1.4rem !important;
        margin-bottom: 1.1rem !important;
        color: #0f172a !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    .demo-mode-badge {
        background-color: #eff6ff !important;
        color: #1d4ed8 !important;
        border: 1.5px solid #bfdbfe !important;
        padding: 4px 12px !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        display: inline-block !important;
    }
    .pill-simulated {
        background-color: #fef2f2 !important;
        color: #b91c1c !important;
        border: 1px solid #fecaca !important;
        padding: 2px 7px !important;
        border-radius: 4px !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        display: inline-block !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 1rem;">
            <span class="demo-mode-badge">⚡ DEMO MODE ACTIVE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="header-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 style="color: #EF4444; margin: 0; font-size: 1.6rem;">📋 INCIDENT ARCHIVE & AUDIT CENTER</h2>
            <span class="demo-mode-badge">⚡ DEMO MODE</span>
        </div>
        <div style="color: #94A3B8; font-size: 0.9rem; margin-top: 0.2rem;">
            Real-time verified emergency detection packages, temporal verification audit logs, and evidence records
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

client = DashboardAPIClient()

# Filters Row
f_c1, f_c2, f_c3 = st.columns([2, 2, 3])
with f_c1:
    type_filter = st.selectbox(
        "Filter by Incident Type:",
        options=["All Types", "traffic_collision", "prolonged_motionlessness", "visual_anomaly"],
    )
with f_c2:
    status_filter = st.selectbox(
        "Filter by Status:",
        options=["All Statuses", "verified", "candidate", "rejected"],
    )
with f_c3:
    search_query = st.text_input("Search (Incident ID, Camera ID, Plate):", placeholder="e.g. INC- or CAM-")

inc_type_arg = None if type_filter == "All Types" else type_filter
incidents = client.list_incidents(incident_type=inc_type_arg)

if status_filter != "All Statuses":
    incidents = [i for i in incidents if i.get("verification_status") == status_filter]

if search_query:
    q = search_query.lower()
    filtered = []
    for inc in incidents:
        matched = (
            q in inc.get("incident_id", "").lower()
            or q in inc.get("camera_id", "").lower()
            or any(q in (p.get("plate_number") or "").lower() for p in inc.get("plate_readings", []))
        )
        if matched:
            filtered.append(inc)
    incidents = filtered

st.markdown(f"**Found {len(incidents)} matching incident package(s)**")

if not incidents:
    st.info("No incident records match the active filter criteria.")
else:
    table_rows = []
    for inc in incidents:
        plates = inc.get("plate_readings", [])
        plate_str = ", ".join([p.get("plate_number") or p.get("normalized_text") or "unreadable" for p in plates]) if plates else "None / N/A"
        loc = inc.get("location")
        loc_str = loc.get("name") if isinstance(loc, dict) else (loc.name if loc else "Perimeter")
        table_rows.append(
            {
                "Incident ID": inc.get("incident_id"),
                "Type": inc.get("incident_type", "").replace("_", " ").title(),
                "Camera ID": inc.get("camera_id"),
                "Location": loc_str,
                "Confidence": f"{inc.get('confidence_score', 0.0) * 100:.1f}%",
                "Status": inc.get("verification_status", "").upper(),
                "Plate Text": plate_str,
                "Timestamp": inc.get("created_at") or inc.get("timestamp"),
            }
        )
    st.dataframe(table_rows, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🔍 Inspect Incident Package Details")

    selected_inc_id = st.selectbox("Select Incident Package ID to Inspect:", options=[i["incident_id"] for i in incidents])
    if selected_inc_id:
        target_inc = client.get_incident(selected_inc_id)
        if target_inc:
            st.markdown('<div class="op-card">', unsafe_allow_html=True)
            st.markdown(f"<h3 style='color: #38BDF8; margin: 0 0 0.5rem 0;'>Package Details: <code>{selected_inc_id}</code></h3>", unsafe_allow_html=True)

            d_c1, d_c2, d_c3 = st.columns(3)
            with d_c1:
                st.metric("Classification", target_inc.get("incident_type", "").replace("_", " ").title())
            with d_c2:
                st.metric("Verification Status", target_inc.get("verification_status", "").upper())
            with d_c3:
                st.metric("Confidence", f"{target_inc.get('confidence_score', 0.0)*100:.1f}%")

            # Notification Timeline for this incident
            timeline = client.get_incident_timeline(selected_inc_id)
            if timeline:
                st.markdown("#### ⏱️ Chronological Notification Timeline")
                for t in timeline:
                    st.markdown(
                        f"""
                        <div style="background-color: #111827; border: 1px solid #1F2937; border-left: 4px solid #3B82F6; border-radius: 6px; padding: 0.65rem 1rem; margin-bottom: 0.45rem;">
                            <b>{t.get('recipient')}</b> ({t.get('timestamp')}) — <span class="pill-simulated">{t.get('status')}</span><br>
                            <span style="color: #94A3B8; font-size: 0.88rem;">{t.get('message')}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # JSON export
            st.download_button(
                label="💾 Download Incident Package (JSON)",
                data=json.dumps(target_inc, indent=2),
                file_name=f"incident_{selected_inc_id}.json",
                mime="application/json",
            )
            st.markdown('</div>', unsafe_allow_html=True)
