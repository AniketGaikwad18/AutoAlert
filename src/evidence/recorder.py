"""Evidence recorder for saving verified incident imagery and video clips."""

import os
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np
import logging

logger = logging.getLogger("autoalert.evidence.recorder")


def sanitize_filename(name: str) -> str:
    """Sanitize incident ID or string for safe filesystem paths."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(name))


class EvidenceRecorder:
    """Persists key evidence frames, encoded video clips, and evidence manifests."""

    def __init__(self, base_output_dir: str = "outputs/incidents"):
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

    def record_incident_evidence(
        self,
        incident_id: str,
        key_frames: List[Tuple[int, float, np.ndarray]],
        video_sequence: Optional[List[Tuple[int, float, np.ndarray]]] = None,
        fps: float = 30.0,
        extra_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save incident frames, video clip (if available), and JSON metadata manifest."""
        safe_id = sanitize_filename(incident_id)
        incident_dir = self.base_output_dir / safe_id
        incident_dir.mkdir(parents=True, exist_ok=True)

        saved_frame_paths: List[str] = []
        video_clip_path: Optional[str] = None

        # 1. Save key evidence frames
        for idx, (frame_num, t_sec, frame_img) in enumerate(key_frames):
            frame_filename = f"keyframe_{frame_num}_{idx + 1}.jpg"
            target_path = incident_dir / frame_filename
            try:
                cv2.imwrite(str(target_path), frame_img)
                saved_frame_paths.append(str(target_path.as_posix()))
            except Exception as e:
                logger.error(f"Failed to write evidence frame {target_path}: {e}")

        # 2. Encode short video clip if buffered sequence is provided
        if video_sequence and len(video_sequence) > 1:
            clip_filename = f"clip_{safe_id}.mp4"
            clip_path = incident_dir / clip_filename
            try:
                first_frame = video_sequence[0][2]
                h, w = first_frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(clip_path), fourcc, max(1.0, fps), (w, h))

                for _, _, f_img in video_sequence:
                    if f_img.shape[:2] != (h, w):
                        f_img = cv2.resize(f_img, (w, h))
                    writer.write(f_img)
                writer.release()
                video_clip_path = str(clip_path.as_posix())
                logger.info(f"Recorded evidence video clip at {video_clip_path} ({len(video_sequence)} frames)")
            except Exception as e:
                logger.error(f"Failed to encode evidence video clip: {e}")
                video_clip_path = None

        # 3. Create metadata manifest
        manifest = {
            "incident_id": incident_id,
            "evidence_directory": str(incident_dir.as_posix()),
            "key_frames": saved_frame_paths,
            "video_clip": video_clip_path,
            "num_keyframes": len(saved_frame_paths),
            "video_frames_count": len(video_sequence) if video_sequence else 0,
            "extra_metadata": extra_meta or {},
        }

        manifest_path = incident_dir / "evidence_manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            manifest["manifest_path"] = str(manifest_path.as_posix())
        except Exception as e:
            logger.error(f"Failed to write evidence manifest: {e}")

        return manifest
