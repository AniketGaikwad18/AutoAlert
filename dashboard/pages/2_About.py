"""
About AutoAlert - Non-Technical Visitor Guide.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="About AutoAlert AI", page_icon="ℹ️", layout="wide")

st.title("ℹ️ About AutoAlert AI")
st.markdown("### **\"AutoAlert AI adds an autonomous emergency response teammate to existing CCTV infrastructure.\"**")

st.divider()

st.markdown("### 🔄 How AutoAlert AI Works")

st.markdown(
    """
```
Existing CCTV Infrastructure
            ↓
      AutoAlert AI
            ↓
          Detect
            ↓
          Verify
            ↓
         Evidence
            ↓
          Locate
            ↓
Nearby Response Facilities
```
    """
)

st.divider()

st.markdown("### 🌟 Key Value Highlights")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 1️⃣ Upgrades Legacy Cameras")
    st.write(
        "AutoAlert connects directly to existing traffic and commercial CCTV feeds. "
        "Cities and facilities do not need to replace their existing camera hardware."
    )

    st.markdown("#### 2️⃣ Multi-Frame AI Verification")
    st.write(
        "Unlike basic detectors that trigger false alarms on brief frame anomalies, "
        "AutoAlert confirms events across continuous temporal windows before generating verified incidents."
    )

with col2:
    st.markdown("#### 3️⃣ Zero-Telemetry Location Binding")
    st.write(
        "CCTV video feeds do not require GPS telemetry. AutoAlert binds events to registered "
        "camera infrastructure to accurately locate incidents."
    )

    st.markdown("#### 4️⃣ Automated Facility Routing")
    st.write(
        "Automatically identifies the closest ambulance stations, police precincts, and hospitals "
        "to accelerate emergency response times."
    )

st.divider()

st.info(
    "💡 **Exhibition Prototype Note**: "
    "All dispatches and emergency facility contacts shown in the dashboard represent simulated prototype workflows."
)
