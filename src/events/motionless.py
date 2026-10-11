"""Prolonged person motionlessness candidate detection module for AutoAlert.

Monitors pedestrian trajectory history to identify prolonged absence of significant displacement.
Explicitly adheres to AutoAlert Rule 7: Detects motionlessness candidate, never asserts medical state or injury.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import logging
from src.tracking.tracker import Track

logger = logging.getLogger("autoalert.events.motionless")


@dataclass
class MotionlessCandidate:
    """Structured candidate event emitted when a person remains motionless beyond a threshold."""
    candidate_id: str
    track_id: int
    frame_number: int
    timestamp_sec: float
    motionless_duration_sec: float
    displacement_px: float
    movement_threshold_px: float
    reasons: List[str]
    status: str = "candidate"  # Always 'candidate', never medical diagnosis

    @property
    def frame_index(self) -> int:
        return self.frame_number

    @property
    def timestamp(self) -> float:
        return self.timestamp_sec

    @property
    def reason(self) -> str:
        return "prolonged_person_motionlessness"

    @property
    def candidate_score(self) -> float:
        return min(0.90, 0.50 + (self.motionless_duration_sec / 10.0) * 0.40)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "event_type": "prolonged_motionlessness_candidate",
            "track_id": self.track_id,
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "motionless_duration_sec": round(self.motionless_duration_sec, 2),
            "displacement_px": round(self.displacement_px, 2),
            "movement_threshold_px": self.movement_threshold_px,
            "reasons": self.reasons,
            "status": self.status,
        }


@dataclass
class MotionlessDetectorConfig:
    """Configuration for motionless candidate detector."""
    fps: float = 30.0
    movement_threshold_px: float = 12.0
    duration_seconds: float = 4.0
    min_frames: int = 10
    max_motion_threshold_px: Optional[float] = None
    min_duration_frames: Optional[int] = None

    def __init__(
        self,
        fps: float = 30.0,
        movement_threshold_px: float = 12.0,
        duration_seconds: float = 4.0,
        min_frames: int = 10,
        max_motion_threshold_px: Optional[float] = None,
        min_duration_frames: Optional[int] = None,
        **kwargs
    ):
        self.fps = fps
        self.movement_threshold_px = max_motion_threshold_px if max_motion_threshold_px is not None else movement_threshold_px
        self.max_motion_threshold_px = self.movement_threshold_px
        self.min_frames = min_duration_frames if min_duration_frames is not None else min_frames
        self.min_duration_frames = self.min_frames
        if min_duration_frames is not None and fps > 0:
            self.duration_seconds = min_duration_frames / fps
        else:
            self.duration_seconds = duration_seconds
        for k, v in kwargs.items():
            setattr(self, k, v)


class MotionlessPersonDetector:
    """Detects prolonged low movement in tracked persons across configurable temporal windows."""

    def __init__(
        self,
        movement_threshold_px: Any = 12.0,
        duration_seconds: float = 4.0,
        min_frames: int = 10,
        config: Optional[MotionlessDetectorConfig] = None,
    ):
        if isinstance(movement_threshold_px, MotionlessDetectorConfig):
            config = movement_threshold_px
            movement_threshold_px = 12.0

        if config is not None:
            self.movement_threshold_px = getattr(config, "movement_threshold_px", 12.0)
            self.duration_seconds = getattr(config, "duration_seconds", 4.0)
            self.min_frames = getattr(config, "min_frames", 10)
        else:
            self.movement_threshold_px = movement_threshold_px
            self.duration_seconds = duration_seconds
            self.min_frames = min_frames

        # track_id -> dict(start_time, anchor_pos, frame_count, emitted)
        self._motion_state: Dict[int, Dict[str, Any]] = {}
        self._candidate_counter = 0

    def detect_candidates(
        self,
        tracks: List[Any],
        frame_number: int = 0,
        timestamp_sec: float = 0.0,
        **kwargs
    ) -> List[MotionlessCandidate]:
        """Alias for evaluate matching controller and test signature."""
        fn = kwargs.get("frame_index", frame_number)
        ts = kwargs.get("timestamp", timestamp_sec)
        return self.evaluate(tracks, frame_number=fn, timestamp_sec=ts)

    def evaluate(
        self,
        tracks: List[Track],
        frame_number: int,
        timestamp_sec: float
    ) -> List[MotionlessCandidate]:
        """Evaluate person tracks for prolonged low displacement and emit candidates."""
        person_tracks = [t for t in tracks if t.class_name == "person"]
        active_track_ids = {t.track_id for t in person_tracks}

        candidates: List[MotionlessCandidate] = []

        # Remove disappeared tracks from motion tracking state
        dead_tracks = [tid for tid in self._motion_state if tid not in active_track_ids]
        for tid in dead_tracks:
            del self._motion_state[tid]

        for track in person_tracks:
            tid = track.track_id
            curr_pos = track.center

            # If track already contains history spanning min_frames, evaluate directly from history
            if len(track.history) >= self.min_frames:
                pts = [
                    ((p.bbox[0] + p.bbox[2]) / 2.0, (p.bbox[1] + p.bbox[3]) / 2.0)
                    if hasattr(p, "bbox") else (getattr(p, "center_x", 0.0), getattr(p, "center_y", 0.0))
                    for p in track.history[-self.min_frames:]
                ]
                anchor_x, anchor_y = pts[0]
                max_disp = max(float(np.hypot(x - anchor_x, y - anchor_y)) for x, y in pts)
                if max_disp <= self.movement_threshold_px:
                    elapsed = max(self.duration_seconds, len(track.history) * 0.1)
                    self._candidate_counter += 1
                    cand_id = f"CAND-MOT-{self._candidate_counter:04d}"
                    cand = MotionlessCandidate(
                        candidate_id=cand_id,
                        track_id=tid,
                        frame_number=frame_number,
                        timestamp_sec=timestamp_sec,
                        motionless_duration_sec=elapsed,
                        displacement_px=max_disp,
                        movement_threshold_px=self.movement_threshold_px,
                        reasons=[
                            f"Track {tid} displacement {max_disp:.1f}px <= {self.movement_threshold_px}px threshold",
                            f"Stationary duration {elapsed:.1f}s over {len(track.history)} frames"
                        ],
                        status="candidate"
                    )
                    candidates.append(cand)
                    continue

            if tid not in self._motion_state:
                # Initialize state
                self._motion_state[tid] = {
                    "start_time": timestamp_sec,
                    "anchor_x": curr_pos[0],
                    "anchor_y": curr_pos[1],
                    "frame_count": 1,
                    "emitted": False,
                }
                continue

            state = self._motion_state[tid]
            state["frame_count"] += 1

            # Calculate displacement from anchor position
            dx = curr_pos[0] - state["anchor_x"]
            dy = curr_pos[1] - state["anchor_y"]
            disp = float(np.hypot(dx, dy))

            if disp > self.movement_threshold_px:
                # Person resumed significant movement -> reset anchor
                state["start_time"] = timestamp_sec
                state["anchor_x"] = curr_pos[0]
                state["anchor_y"] = curr_pos[1]
                state["frame_count"] = 1
                state["emitted"] = False
                continue

            # Motion is below threshold; check duration
            elapsed = timestamp_sec - state["start_time"]
            if (
                elapsed >= self.duration_seconds
                and state["frame_count"] >= self.min_frames
                and not state["emitted"]
            ):
                self._candidate_counter += 1
                cand_id = f"CAND-MOT-{self._candidate_counter:04d}"
                state["emitted"] = True

                cand = MotionlessCandidate(
                    candidate_id=cand_id,
                    track_id=tid,
                    frame_number=frame_number,
                    timestamp_sec=timestamp_sec,
                    motionless_duration_sec=elapsed,
                    displacement_px=disp,
                    movement_threshold_px=self.movement_threshold_px,
                    reasons=[
                        f"Track {tid} displacement {disp:.1f}px <= {self.movement_threshold_px}px threshold",
                        f"Stationary duration {elapsed:.1f}s >= {self.duration_seconds}s threshold over {state['frame_count']} frames"
                    ],
                    status="candidate"
                )
                candidates.append(cand)

        return candidates


MotionlessCandidateDetector = MotionlessPersonDetector
