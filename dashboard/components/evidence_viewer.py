"""Evidence media rendering component for AutoAlert Command Center."""

from pathlib import Path
from typing import Dict, Any, Optional
import streamlit as st
from PIL import Image


def render_evidence_media(evidence: Optional[Dict[str, Any]]) -> None:
    """Render key evidence frames and short video playback if files exist."""
    if not evidence:
        st.info("No recorded visual evidence available for this incident.")
        return

    key_frames = evidence.get("key_frames", [])
    video_clip = evidence.get("video_clip")

    if key_frames:
        st.subheader("Key Evidence Frames")
        cols = st.columns(min(3, len(key_frames)))
        for idx, kf_path in enumerate(key_frames):
            p = Path(kf_path)
            col_target = cols[idx % len(cols)]
            with col_target:
                if p.exists():
                    try:
                        img = Image.open(str(p))
                        st.image(img, caption=f"Frame: {p.name}", use_container_width=True)
                    except Exception as e:
                        st.caption(f"Error loading image: {e}")
                else:
                    st.caption(f"File not found on disk: {p.name}")

    if video_clip:
        p_clip = Path(video_clip)
        if p_clip.exists():
            st.subheader("Incident Evidence Clip")
            st.video(str(p_clip))
        else:
            st.caption(f"Video clip specified but file missing: {video_clip}")
