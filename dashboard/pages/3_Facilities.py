"""
AutoAlert AI — Emergency Facilities & Dispatch Registry (Page 3).

Explore registered emergency facilities (Hospitals, Ambulances, Police Stations) and test Haversine distance matching.
"""

from __future__ import annotations

import streamlit as st
from dashboard.api_client import DashboardAPIClient

st.set_page_config(
    page_title="Facilities Registry — AutoAlert AI",
    page_icon="🏥",
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
            <h2 style="color: #34D399; margin: 0; font-size: 1.6rem;">🏥 EMERGENCY FACILITIES REGISTRY</h2>
            <span class="demo-mode-badge">⚡ DEMO MODE</span>
        </div>
        <div style="color: #94A3B8; font-size: 0.9rem; margin-top: 0.2rem;">
            Registered hospitals, ambulance paramedic stations, and police precincts (Simulated Prototype)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

client = DashboardAPIClient()

f_filter = st.selectbox("Filter Facility Type:", options=["All Facilities", "hospital", "ambulance", "police"])
f_type_arg = None if f_filter == "All Facilities" else f_filter
facilities = client.list_facilities(facility_type=f_type_arg)

st.markdown(f"**Registered Facilities ({len(facilities)} total)**")

f_cols = st.columns(min(3, max(1, len(facilities))))
for idx, fac in enumerate(facilities):
    col = f_cols[idx % len(f_cols)]
    with col:
        ftype = fac.get("type", "hospital").lower()
        icon = "🏥" if ftype == "hospital" else ("🚑" if ftype == "ambulance" else "🚓")
        color = "#38BDF8" if ftype == "hospital" else ("#34D399" if ftype == "ambulance" else "#818CF8")

        st.markdown(
            f"""
            <div class="op-card" style="min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.8rem; font-weight: 800; color: {color};">{icon} {fac.get('type', '').upper()}</span>
                        <span class="pill-simulated">SIMULATED</span>
                    </div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #FFFFFF; margin: 0.3rem 0;">{fac.get('name')}</div>
                    <div style="color: #94A3B8; font-size: 0.85rem;">📞 Contact: <code>{fac.get('phone_contact', '555-0100')}</code></div>
                </div>
                <div>
                    <div style="height: 1px; background-color: #2E3E56; margin: 0.5rem 0;"></div>
                    <div style="font-size: 0.82rem; color: #94A3B8;">
                        <b>GPS:</b> {fac.get('latitude', 0):.4f}° N, {fac.get('longitude', 0):.4f}° E<br>
                        <b>Corridor Role:</b> {fac.get('station_role', 'Emergency Response Node')}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# Haversine Distance Test Calculator
st.markdown("### 📐 Interactive Haversine Facility Distance Calculator")
calc_c1, calc_c2, calc_c3 = st.columns(3)
with calc_c1:
    test_lat = st.number_input("Test Latitude (°N):", value=18.5204, format="%.4f")
with calc_c2:
    test_lon = st.number_input("Test Longitude (°E):", value=73.8567, format="%.4f")
with calc_c3:
    calc_type = st.selectbox("Rank Facility Type:", options=["hospital", "ambulance", "police"])

if st.button("Calculate Ranked Facilities", type="primary"):
    ranked = client.match_facilities(latitude=test_lat, longitude=test_lon, facility_type=calc_type, limit=5)
    st.markdown(f"**Top Ranked `{calc_type.upper()}` Facilities by Haversine Distance:**")
    st.table(
        [
            {
                "Rank": i + 1,
                "Facility Name": r.get("name"),
                "Type": r.get("type", "").upper(),
                "Haversine Distance (km)": f"{r.get('distance_km', 0):.3f} km",
                "Contact": r.get("phone_contact", "555-0100"),
            }
            for i, r in enumerate(ranked)
        ]
    )
