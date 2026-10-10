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


class MotionlessPersonDetector:
    """Detects prolonged low movement in tracked persons across configurable temporal windows."""

    def __init__(
        self,
        movement_threshold_px: float = 12.0,
        duration_seconds: float = 4.0,
        min_frames: int = 10,
    ):
        self.movement_threshold_px = movement_threshold_px
        self.duration_seconds = duration_seconds
        self.min_frames = min_frames

        # track_id -> dict(start_time, anchor_pos, frame_count, emitted)
        self._motion_state: Dict[int, Dict[str, Any]] = {}
        self._candidate_counter = 0

    def evaluate(
        self,
        tracks: List[Track],
        frame_number: int,
        timestamp_sec: float
    ) -> List[MotionlessCandidate]:
        """Evaluate person tracks for prolonged low displacement and emit candidates."""
        person_tracks = [t for t in tracks if t.class_name == "person" and t.is_confirmed]
        active_track_ids = {t.track_id for t in person_tracks}

        candidates: List[MotionlessCandidate] = []

        # Remove disappeared tracks from motion tracking state
        dead_tracks = [tid for tid in self._motion_state if tid not in active_track_ids]
        for tid in dead_tracks:
            del self._motion_state[tid]

        for track in person_tracks:
            tid = track.track_id
            curr_pos = track.center

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
