from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import os
import re
import json
import cv2
import numpy as np
import logging

logger = logging.getLogger("autoalert.evidence.recorder")


def sanitize_filename(name: str) -> str:
    """Sanitize incident ID or string for safe filesystem paths."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(name))


@dataclass
class EvidenceRecorderConfig:
    """Configuration for evidence generation and retention."""
    output_dir: str = "outputs/incidents"
    save_key_frames: bool = True
    save_video_clip: bool = True
    pre_event_buffer_seconds: float = 2.0
    post_event_buffer_seconds: float = 2.0
    fps: float = 30.0


@dataclass
class IncidentEvidenceReport:
    """Structured evidence report returned by record_evidence."""
    incident_id: str
    camera_id: str
    location: Any
    track_ids: List[int]
    timestamp: float
    evidence_files: Dict[str, Any]
    plate_readings: List[Any] = field(default_factory=list)


class EvidenceRecorder:
    """Persists key evidence frames, encoded video clips, and evidence manifests."""

    def __init__(
        self,
        base_output_dir: Optional[str] = None,
        config: Optional[EvidenceRecorderConfig] = None,
        save_video_clip: bool = True,
        fps: float = 30.0,
        **kwargs
    ):
        if config is not None:
            self.config = config
            self.base_output_dir = Path(config.output_dir)
            self.save_video_clip = getattr(config, "save_video_clip", save_video_clip)
            self.fps = getattr(config, "fps", fps)
        else:
            self.base_output_dir = Path(base_output_dir or "outputs/incidents")
            self.save_video_clip = save_video_clip
            self.fps = fps
            self.config = EvidenceRecorderConfig(
                output_dir=str(self.base_output_dir),
                save_video_clip=self.save_video_clip,
                fps=self.fps
            )
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

    def record_evidence(
        self,
        incident: Any,
        frame_buffer: Any,
        camera_id: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
        plate_readings: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> IncidentEvidenceReport:
        """Record evidence for an upstream VerifiedIncident."""
        inc_id = getattr(incident, "incident_id", str(incident))
        safe_id = sanitize_filename(inc_id)
        incident_dir = self.base_output_dir / safe_id
        incident_dir.mkdir(parents=True, exist_ok=True)

        cam_id = camera_id or getattr(incident, "camera_id", "CAM-MAIN-01")
        loc_data = location if location is not None else getattr(incident, "location", None)
        track_ids = getattr(incident, "track_ids", [])
        timestamp = float(getattr(incident, "timestamp", getattr(incident, "timestamp_sec", 0.0)))

        all_buffered = frame_buffer.get_all() if hasattr(frame_buffer, "get_all") else []
        saved_key_frames = []
        if all_buffered:
            step = max(1, len(all_buffered) // 3)
            selected = all_buffered[::step][:3] if len(all_buffered) > 3 else all_buffered
            for idx, item in enumerate(selected):
                f_num = item[0]
                f_img = item[2]
                filename = f"keyframe_{f_num}_{idx + 1}.jpg"
                file_path = incident_dir / filename
                cv2.imwrite(str(file_path), f_img)
                saved_key_frames.append(f"{safe_id}/{filename}")

        video_clip_path = None
        if self.save_video_clip and all_buffered:
            clip_name = f"clip_{safe_id}.mp4"
            clip_path = incident_dir / clip_name
            try:
                sample_img = all_buffered[0][2]
                h, w = sample_img.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(clip_path), fourcc, self.fps, (w, h))
                for item in all_buffered:
                    f_img = item[2]
                    if f_img.shape[:2] != (h, w):
                        f_img = cv2.resize(f_img, (w, h))
                    writer.write(f_img)
                writer.release()
                video_clip_path = f"{safe_id}/{clip_name}"
            except Exception as e:
                logger.error(f"Failed to encode video clip: {e}")
                video_clip_path = None

        evidence_files = {
            "key_frames": saved_key_frames,
            "video_clip": video_clip_path,
        }

        report_data = {
            "incident_id": inc_id,
            "camera_id": cam_id,
            "location": loc_data,
            "track_ids": track_ids,
            "timestamp": timestamp,
            "evidence_files": evidence_files,
            "plate_readings": plate_readings or [],
        }
        json_path = incident_dir / "incident_report.json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write incident_report.json: {e}")

        return IncidentEvidenceReport(
            incident_id=inc_id,
            camera_id=cam_id,
            location=loc_data,
            track_ids=track_ids,
            timestamp=timestamp,
            evidence_files=evidence_files,
            plate_readings=plate_readings or []
        )

