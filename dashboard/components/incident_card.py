"""
Structured incident card component for rendering detailed incident information in Streamlit.

Adheres strictly to AutoAlert Engineering rules:
- Never fabricates missing data (no fake maps, fake plates, or fake evidence).
- Displays license plate readings ONLY when available/readable.
- Renders map ONLY when valid GPS coordinates exist.
- Prominently marks simulated prototype emergency response data.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import streamlit as st


def format_timestamp(ts: Optional[float]) -> str:
    """Format Unix timestamp or return fallback text."""
    if ts is None:
        return "Unknown timestamp"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return f"{ts}s"


def render_verification_badge(status: str) -> None:
    """Render a colored status badge based on verification status."""
    st_status = status.lower()
    if st_status == "verified":
        st.success(f"STATUS: VERIFIED INCIDENT ({status.upper()})")
    elif st_status in ("candidate", "verifying"):
        st.warning(f"STATUS: CANDIDATE / {status.upper()}")
    elif st_status in ("rejected", "expired"):
        st.error(f"STATUS: {status.upper()}")
    else:
        st.info(f"STATUS: {status.upper()}")


def render_incident_card(
    incident: Dict[str, Any],
    simulated_facilities: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Render comprehensive structured incident details."""

    incident_id = incident.get("incident_id", "UNKNOWN_ID")
    incident_type = incident.get("incident_type", "unknown_type")
    camera_id = incident.get("camera_id", "N/A")
    timestamp = incident.get("timestamp")
    verification_status = incident.get("verification_status", "unknown")
    confidence_score = incident.get("confidence_score", 0.0)
    created_at = incident.get("created_at", "")
    involved_tracks = incident.get("involved_track_ids", [])
    evidence_frames = incident.get("evidence_frames", [])
    evidence_video_path = incident.get("evidence_video_path")
    location = incident.get("location")
    plate_readings = incident.get("plate_readings", [])
    reason_metadata = incident.get("reason_metadata", {})

    st.markdown(f"## 🚨 Incident Details: `{incident_id}`")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Incident Type", incident_type.replace("_", " ").title())
    with col2:
        st.metric("Source Camera", camera_id)
    with col3:
        st.metric("Confidence Score", f"{confidence_score * 100:.1f}%")

    render_verification_badge(verification_status)

    st.markdown(
        f"**Event Timestamp:** {format_timestamp(timestamp)} | **Ingested At:** `{created_at}`"
    )
    if involved_tracks:
        st.markdown(f"**Involved Object Track IDs:** `{involved_tracks}`")

    st.divider()

    # -- 1. Evidence Preview Section ----------------------------------------
    st.markdown("### 📷 Evidence Preview")
    frame_col, video_col = st.columns(2)

    with frame_col:
        st.markdown("#### Key Frame Evidence")
        valid_frames = [f for f in evidence_frames if os.path.exists(f)]
        if valid_frames:
            for i, frame_path in enumerate(valid_frames):
                st.image(frame_path, caption=f"Evidence Frame #{i+1} ({os.path.basename(frame_path)})")
        else:
            st.info("ℹ️ No key evidence frame images available on disk for this incident.")

    with video_col:
        st.markdown("#### Evidence Video Clip")
        if evidence_video_path and os.path.exists(evidence_video_path):
            st.video(evidence_video_path)
            st.caption(f"Clip path: `{evidence_video_path}`")
        else:
            st.info("ℹ️ No evidence video clip available on disk for this incident.")

    st.divider()

    # -- 2. License Plate Section -------------------------------------------
    st.markdown("### 🚘 Vehicle License Plate Readings")
    if plate_readings:
        for pr in plate_readings:
            plate_num = pr.get("plate_number") or pr.get("normalized_text") or pr.get("raw_text")
            conf = pr.get("confidence", 0.0)
            status_text = pr.get("status", "unverified")
            format_val = pr.get("format_validated", False)
            track_id = pr.get("track_id", "N/A")

            if plate_num:
                st.success(
                    f"**Plate:** `{plate_num}` | **Confidence:** {conf*100:.1f}% | "
                    f"**Track ID:** `{track_id}` | **Status:** `{status_text}` | "
                    f"**Indian Format Validated:** `{format_val}`"
                )
            else:
                st.warning(f"Plate reading associated with Track `{track_id}` was unreadable.")
    else:
        st.info("ℹ️ No license plate detected or readable for this incident.")

    st.divider()

    # -- 3. Location & Map Section ------------------------------------------
    st.markdown("### 📍 Location Information")
    has_valid_coords = False
    lat, lon = None, None

    if location and isinstance(location, dict):
        loc_name = location.get("name", "Unspecified Location")
        lat = location.get("latitude")
        lon = location.get("longitude")
        zone_id = location.get("zone_id", "N/A")

        st.markdown(f"**Location Name:** {loc_name} | **Zone ID:** `{zone_id}`")

        if lat is not None and lon is not None:
            try:
                lat_f, lon_f = float(lat), float(lon)
                if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0:
                    has_valid_coords = True
                    st.markdown(f"**GPS Coordinates:** Lat `{lat_f:.4f}`, Lon `{lon_f:.4f}`")
                    st.map([{"lat": lat_f, "lon": lon_f}], zoom=14)
            except (ValueError, TypeError):
                pass

    if not has_valid_coords:
        st.info("ℹ️ No valid GPS coordinates available for map rendering. (Displaying textual location metadata only)")

    st.divider()

    # -- 4. Simulated Emergency Response Facilities & Distance Matching ----
    st.markdown("### 🏥 Emergency Response Dispatch & Distance Matching (Simulated Prototype)")
    st.warning("⚠️ **SIMULATED DEMO NOTICE**: All facility listings, Haversine distance calculations, contacts, and response routing below are **simulated prototype data**. No real police, ambulance, hospital, or 911 calls are executed.")

    from dashboard.api_client import DashboardAPIClient
    api_client = DashboardAPIClient()

    # Match facilities ranked by Haversine distance
    matched_facs = api_client.match_facilities(
        incident_id=incident_id,
        latitude=lat if has_valid_coords else None,
        longitude=lon if has_valid_coords else None,
        limit=5,
    )

    if matched_facs:
        for fac in matched_facs:
            f_id = fac.get("facility_id")
            f_name = fac.get("name", "Unknown Facility")
            f_type = fac.get("type", "hospital").upper()
            f_phone = fac.get("phone_contact", "N/A")
            dist = fac.get("distance_km")
            dist_str = f"| **Haversine Distance:** `{dist:.3f} km`" if dist is not None else "| **Haversine Distance:** `GPS Unavailable`"

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(
                    f"**[{f_type}]** {f_name} | Contact: `{f_phone}` {dist_str}"
                )
            with col_b:
                btn_key = f"dispatch_{incident_id}_{f_id}"
                if st.button(f"⚡ Trigger Dispatch", key=btn_key):
                    res = api_client.trigger_notification(
                        incident_id=incident_id,
                        facility_id=f_id,
                        message=f"SIMULATED DISPATCH: Emergency alert for {incident_id}",
                    )
                    if res:
                        st.success(f"Simulated dispatch sent to `{f_id}` (Status: NOTIFIED)")
                        st.rerun()

    # Active / Past Simulated Notification Dispatch Logs for this Incident
    existing_notifs = api_client.list_notifications(incident_id=incident_id)
    if existing_notifs:
        st.markdown("#### 📋 Simulated Dispatch Log & Lifecycle Updates")
        for notif in existing_notifs:
            n_id = notif.get("notification_id")
            n_status = notif.get("status", "pending")
            f_name = notif.get("facility_name")
            f_type = notif.get("facility_type", "").upper()

            with st.expander(f"Dispatch `{n_id}` → {f_name} [{f_type}] | Current Status: {n_status.upper()}"):
                st.write(f"**Message:** {notif.get('message')}")
                st.write(f"**Created At:** {notif.get('created_at')} | **Updated At:** {notif.get('updated_at')}")

                # Status Transition Action Buttons
                action_col1, action_col2, action_col3 = st.columns(3)
                with action_col1:
                    if st.button("✅ Acknowledge Dispatch", key=f"ack_{n_id}"):
                        api_client.update_notification_status(n_id, "acknowledged", reason="Acknowledged by operator in Command Center")
                        st.rerun()
                with action_col2:
                    if st.button("🚨 Mark Responding", key=f"resp_{n_id}"):
                        api_client.update_notification_status(n_id, "responding", reason="Unit dispatched and responding to scene")
                        st.rerun()
                with action_col3:
                    if st.button("❌ Reject Dispatch", key=f"rej_{n_id}"):
                        api_client.update_notification_status(n_id, "rejected", reason="Rejected by operator")
                        st.rerun()

                st.markdown("**Status Transition Audit History:**")
                st.json(notif.get("history", []))

    if reason_metadata:
        with st.expander("🔍 Verification Reason & Diagnostic Signals"):
            st.json(reason_metadata)
