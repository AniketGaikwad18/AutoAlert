"""AutoAlert Command Center Dashboard (Streamlit).

Central real-time emergency detection monitoring, incident review, evidence inspection,
and simulated dispatch response interface.
Adheres strictly to AutoAlert Rules:
- Never fabricates missing data (GPS/plates).
- All emergency service interactions are prominently marked as PROTOTYPE / SIMULATED.
- Keeps UI decoupled from core pipeline algorithms.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import requests
import streamlit as st
import pandas as pd

from backend.database.database import SessionLocal, init_db
from backend.database.repositories import IncidentRepository, CameraRepository, FacilityRepository, seed_defaults_if_empty
from dashboard.components.metrics import render_metric_cards
from dashboard.components.evidence_viewer import render_evidence_media
from src.location.facility_matcher import match_nearest_facilities

st.set_page_config(
    page_title="AutoAlert Command Center",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .badge-collision {
        background-color: #ef4444; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-motionless {
        background-color: #f59e0b; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-anomaly {
        background-color: #8b5cf6; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .simulated-banner {
        background-color: #1e293b; border-left: 4px solid #3b82f6; padding: 12px; margin-bottom: 20px; border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)


def get_data_from_db():
    """Retrieve data directly from database repository."""
    init_db()
    db = SessionLocal()
    try:
        seed_defaults_if_empty(db)
        incidents_models = IncidentRepository.get_all(db, limit=200)
        cameras_models = CameraRepository.get_all(db)
        facilities_models = FacilityRepository.get_all(db)

        incidents = []
        for m in incidents_models:
            incidents.append({
                "id": m.id,
                "incident_type": m.incident_type,
                "camera_id": m.camera_id,
                "timestamp": m.timestamp,
                "confidence_score": m.confidence_score,
                "verification_status": m.verification_status,
                "notification_status": m.notification_status,
                "involved_tracks": json.loads(m.involved_tracks_json or "[]"),
                "reasons": json.loads(m.reasons_json or "[]"),
                "signals": json.loads(m.signals_json or "{}"),
                "location": json.loads(m.location_json) if m.location_json else None,
                "evidence": json.loads(m.evidence_json) if m.evidence_json else None,
                "plate_readings": json.loads(m.plate_readings_json or "[]"),
            })

        cameras = [
            {
                "id": c.id, "name": c.name, "source": c.source,
                "latitude": c.latitude, "longitude": c.longitude,
                "location_desc": c.location_desc, "is_active": c.is_active
            }
            for c in cameras_models
        ]

        facilities = [
            {
                "id": f.id, "name": f.name, "type": f.type,
                "latitude": f.latitude, "longitude": f.longitude,
                "phone": f.phone, "status": f.status
            }
            for f in facilities_models
        ]

        return incidents, cameras, facilities
    finally:
        db.close()


def update_incident_status_in_db(incident_id: str, new_status: str):
    """Update incident simulated notification status."""
    db = SessionLocal()
    try:
        IncidentRepository.update_status(db, incident_id, new_status)
    finally:
        db.close()


# Header & Banner
st.title("🚨 AutoAlert Command Center")
st.markdown("""
<div class="simulated-banner">
    <strong>⚠️ PROTOTYPE / SIMULATED ENVIRONMENT</strong><br>
    AutoAlert AI/IoT Emergency Detection Platform. Emergency service dispatches and facility notifications
    in this prototype are strictly simulated. No external 108/911 calls or live police APIs are triggered.
</div>
""", unsafe_allow_html=True)

# Fetch Data
incidents, cameras, facilities = get_data_from_db()

# Sidebar
st.sidebar.header("Filter & Controls")
type_filter = st.sidebar.selectbox(
    "Incident Type",
    ["All Types", "vehicle_collision", "prolonged_motionlessness", "visual_anomaly"]
)
status_filter = st.sidebar.selectbox(
    "Notification Status",
    ["All Statuses", "pending", "notified", "acknowledged", "responding"]
)

# Apply filters
filtered_incidents = incidents
if type_filter != "All Types":
    filtered_incidents = [i for i in filtered_incidents if i["incident_type"] == type_filter]
if status_filter != "All Statuses":
    filtered_incidents = [i for i in filtered_incidents if i["notification_status"] == status_filter]

# Metrics
render_metric_cards(filtered_incidents, cameras)

tabs = st.tabs(["Active Incidents", "Camera Network", "Simulated Facilities", "System Architecture"])

with tabs[0]:
    if not filtered_incidents:
        st.info("No incidents found matching the selected filters.")
    else:
        col_list, col_detail = st.columns([1, 1])

        with col_list:
            st.subheader("Verified Incident Queue")
            table_rows = []
            for inc in filtered_incidents:
                table_rows.append({
                    "ID": inc["id"],
                    "Type": inc["incident_type"],
                    "Camera": inc["camera_id"],
                    "Confidence": f"{inc['confidence_score']*100:.1f}%",
                    "Status": inc["notification_status"].upper(),
                    "Timestamp": inc["timestamp"]
                })
            df = pd.DataFrame(table_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            selected_id = st.selectbox(
                "Select Incident to Inspect:",
                [i["id"] for i in filtered_incidents],
                key="incident_select"
            )

        with col_detail:
            selected_inc = next((i for i in filtered_incidents if i["id"] == selected_id), None)
            if selected_inc:
                st.subheader(f"Incident Details: {selected_inc['id']}")

                # Status & Type
                st.markdown(f"**Type:** `{selected_inc['incident_type']}` | **Camera:** `{selected_inc['camera_id']}`")
                st.markdown(f"**Confidence:** `{selected_inc['confidence_score']*100:.1f}%` | **Verification:** `{selected_inc['verification_status'].upper()}`")
                st.markdown(f"**Simulated Dispatch State:** `{selected_inc['notification_status'].upper()}`")

                # Decision Reasons
                st.markdown("**Explainable Decision Signals:**")
                for r in selected_inc.get("reasons", []):
                    st.markdown(f"- {r}")

                # Plate reading (only if available)
                plate_readings = selected_inc.get("plate_readings", [])
                st.markdown("**License Plate Readings:**")
                if plate_readings:
                    for pr in plate_readings:
                        txt = pr.get("plate_text")
                        conf = pr.get("confidence", 0.0)
                        if pr.get("is_readable") and txt:
                            st.success(f"Track #{pr.get('track_id')}: **{txt}** (Confidence: {conf*100:.1f}%)")
                        else:
                            st.warning(f"Track #{pr.get('track_id')}: Unreadable / Low confidence ({conf*100:.1f}%)")
                else:
                    st.caption("No license plate readings recorded for this incident.")

                # Evidence Media
                render_evidence_media(selected_inc.get("evidence"))

                # Location & Map (ONLY if coordinates exist)
                loc = selected_inc.get("location")
                if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
                    st.markdown(f"**Location:** {loc.get('description', 'Coordinates available')}")
                    lat = loc["latitude"]
                    lon = loc["longitude"]
                    map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
                    st.map(map_df, zoom=14)

                    # Nearest Facility Matching
                    st.markdown("**Nearest Simulated Emergency Units:**")
                    matched = match_nearest_facilities(lat, lon, facilities)
                    for f_type, fac_list in matched.items():
                        if fac_list:
                            f_top = fac_list[0]
                            st.markdown(f"- **{f_type.capitalize()}:** {f_top['name']} ({f_top['distance_km']:.2f} km) - Phone: `{f_top['phone']}`")
                else:
                    st.caption("No geographic GPS coordinates configured for this camera.")

                # Simulated Notification Actions
                st.markdown("---")
                st.markdown("**Simulated Dispatch Actions:**")
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("🚀 Dispatch Simulated EMS", key="btn_dispatch"):
                        update_incident_status_in_db(selected_inc["id"], "notified")
                        st.success("Simulated dispatch notification transmitted!")
                        st.rerun()
                with b2:
                    if st.button("✅ Mark Acknowledged", key="btn_ack"):
                        update_incident_status_in_db(selected_inc["id"], "acknowledged")
                        st.info("Simulated EMS acknowledgement logged.")
                        st.rerun()
                with b3:
                    if st.button("🚑 Unit Responding", key="btn_resp"):
                        update_incident_status_in_db(selected_inc["id"], "responding")
                        st.warning("Simulated EMS unit in transit.")
                        st.rerun()

with tabs[1]:
    st.subheader("Monitored CCTV Camera Network")
    cam_df = pd.DataFrame(cameras)
    st.dataframe(cam_df, use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Registered Emergency Facilities (Simulated)")
    fac_df = pd.DataFrame(facilities)
    st.dataframe(fac_df, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("AutoAlert Platform Architecture & Rules")
    st.markdown("""
    **Core Pipeline:**
    `Existing CCTV -> Frame Processing -> Object Detection -> Multi-Object Tracking -> Event Candidate Detection -> Verification Engine -> Evidence Recording -> Incident Package -> FastAPI Backend -> Dashboard`

    **Guiding Engineering Constraints:**
    - Never claim a feature works without executable code and tests.
    - Never treat bounding-box overlap alone as proof of collision.
    - Never treat motionlessness as proof of medical injury.
    - Label red fluid visual anomalies neutrally without claiming biological blood detection.
    - OCR output is not ground truth; unreadable plates are preserved as unreadable.
    - Prototype emergency workflows are strictly simulated.
    """)
