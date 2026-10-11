"""
AutoAlert AI — Camera Fleet & Sensor Inventory (Page 2).

Manage registered CCTV infrastructure, inspect RTSP stream binding, and view geospatial coordinates.
"""

from __future__ import annotations

import streamlit as st
from dashboard.api_client import DashboardAPIClient

st.set_page_config(
    page_title="Cameras Fleet — AutoAlert AI",
    page_icon="📹",
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
    .pill-green {
        background-color: #ecfdf5 !important;
        color: #047857 !important;
        border: 1px solid #a7f3d0 !important;
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
            <h2 style="color: #38BDF8; margin: 0; font-size: 1.6rem;">📹 REGISTERED CCTV CAMERA FLEET</h2>
            <span class="demo-mode-badge">⚡ DEMO MODE</span>
        </div>
        <div style="color: #94A3B8; font-size: 0.9rem; margin-top: 0.2rem;">
            Autonomous edge vision nodes, merchant perimeter binding, and geospatial coordinates
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

client = DashboardAPIClient()
cameras = client.list_cameras()

st.markdown(f"**Active Registered Camera Nodes ({len(cameras)} total)**")

c_cols = st.columns(min(3, max(1, len(cameras))))
for idx, cam in enumerate(cameras):
    col = c_cols[idx % len(c_cols)]
    with col:
        cid = cam.get("camera_id")
        name = cam.get("name")
        loc = cam.get("location") or {}
        loc_name = loc.get("name", "Perimeter Area")
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        status_txt = "ACTIVE" if cam.get("enabled", True) else "DISABLED"

        st.markdown(
            f"""
            <div class="op-card" style="min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.8rem; font-weight: 800; color: #38BDF8;">NODE {cid}</span>
                        <span class="pill-green">{status_txt}</span>
                    </div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #FFFFFF; margin: 0.3rem 0;">{name}</div>
                    <div style="color: #94A3B8; font-size: 0.88rem;">📍 {loc_name}</div>
                </div>
                <div>
                    <div style="height: 1px; background-color: #2E3E56; margin: 0.5rem 0;"></div>
                    <div style="font-size: 0.82rem; color: #94A3B8;">
                        <b>GPS:</b> <span style="color: #38BDF8;">{lat:.4f}° N, {lon:.4f}° E</span><br>
                        <b>Resolution:</b> {cam.get('resolution', '1920x1080')} @ {cam.get('fps', 30.0)} FPS<br>
                        <b>Merchant:</b> {cam.get('merchant_name', 'Store Operations')}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# Camera map
map_points = []
for c in cameras:
    loc = c.get("location") or {}
    if loc.get("latitude") and loc.get("longitude"):
        map_points.append({"lat": float(loc["latitude"]), "lon": float(loc["longitude"])})

if map_points:
    st.markdown("### 🗺️ CCTV Geospatial Network Distribution")
    st.map(map_points, zoom=13)
