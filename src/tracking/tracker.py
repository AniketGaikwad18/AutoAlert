"""Multi-object tracking module for AutoAlert.

Associates structured detections across frames to provide persistent track IDs,
motion trajectory history, and velocity metrics without coupling to event logic.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import logging
from src.detection.detector import BoundingBox, Detection

logger = logging.getLogger("autoalert.tracking")


@dataclass
class TrajectoryPoint:
    """Historical spatio-temporal coordinate point for a tracked object."""
    frame_number: int = 0
    timestamp_sec: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    bbox: Optional[BoundingBox] = None
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    speed: float = 0.0
    confidence: float = 1.0

    def __init__(self, *args, **kwargs):
        names = ["frame_number", "timestamp_sec", "center_x", "center_y", "bbox", "velocity_x", "velocity_y", "speed", "confidence"]
        for i, a in enumerate(args):
            kwargs[names[i]] = a
        if "frame_index" in kwargs and "frame_number" not in kwargs:
            kwargs["frame_number"] = kwargs.pop("frame_index")
        if "timestamp" in kwargs and "timestamp_sec" not in kwargs:
            kwargs["timestamp_sec"] = kwargs.pop("timestamp")
        b = kwargs.get("bbox")
        if isinstance(b, (tuple, list)):
            kwargs["bbox"] = BoundingBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        for k, v in kwargs.items():
            setattr(self, k, v)
        if getattr(self, "bbox", None) is not None:
            if not getattr(self, "center_x", None) and not getattr(self, "center_y", None):
                self.center_x, self.center_y = self.bbox.center

    @property
    def timestamp(self) -> float:
        return getattr(self, "timestamp_sec", 0.0)

    @property
    def frame_index(self) -> int:
        return getattr(self, "frame_number", 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "center": (round(self.center_x, 2), round(self.center_y, 2)),
            "speed": round(self.speed, 2),
        }


@dataclass
class Track:
    """Persistent track state across consecutive video frames."""
    track_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    history: List[TrajectoryPoint] = field(default_factory=list)
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    is_confirmed: bool = False

    def __post_init__(self):
        if isinstance(self.bbox, (tuple, list)):
            self.bbox = BoundingBox(float(self.bbox[0]), float(self.bbox[1]), float(self.bbox[2]), float(self.bbox[3]))

    @property
    def snapshots(self) -> List[TrajectoryPoint]:
        return self.history

    @property
    def center(self) -> Tuple[float, float]:
        return self.bbox.center

    def update(
        self,
        detection: Detection,
        frame_number: int,
        timestamp_sec: float,
        max_history: int = 60
    ) -> None:
        """Update track state with a newly matched detection."""
        new_center = detection.bbox.center
        vx, vy, spd = 0.0, 0.0, 0.0

        if self.history:
            prev = self.history[-1]
            dt = max(0.0001, timestamp_sec - prev.timestamp_sec)
            vx = (new_center[0] - prev.center_x) / dt
            vy = (new_center[1] - prev.center_y) / dt
            spd = float(np.hypot(vx, vy))

        point = TrajectoryPoint(
            frame_number=frame_number,
            timestamp_sec=timestamp_sec,
            center_x=new_center[0],
            center_y=new_center[1],
            bbox=detection.bbox,
            velocity_x=vx,
            velocity_y=vy,
            speed=spd,
        )

        self.history.append(point)
        if len(self.history) > max_history:
            self.history.pop(0)

        self.bbox = detection.bbox
        self.confidence = detection.confidence
        self.class_name = detection.class_name
        self.hits += 1
        self.time_since_update = 0

    def mark_missed(self) -> None:
        """Increment age and update counters when track is unobserved in frame."""
        self.time_since_update += 1

    def get_trajectory_centers(self) -> List[Tuple[float, float]]:
        """Return list of (x, y) coordinates from trajectory history."""
        return [(p.center_x, p.center_y) for p in self.history]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "age": self.age,
            "hits": self.hits,
            "is_confirmed": self.is_confirmed,
            "history_points": len(self.history),
        }


class MultiObjectTracker:
    """IoU and spatial distance association tracker maintaining temporal track states."""

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.25,
        max_history: int = 60
    ):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.max_history = max_history

        self.tracks: List[Track] = []
        self._next_track_id = 1

    def update(
        self,
        detections: List[Detection],
        frame_number: int = 0,
        timestamp_sec: float = 0.0,
        **kwargs
    ) -> List[Track]:
        """Update tracker with detections from current frame and return active tracks."""
        if "frame_index" in kwargs:
            frame_number = kwargs["frame_index"]
        if "timestamp" in kwargs:
            timestamp_sec = kwargs["timestamp"]
        # Increment track ages
        for track in self.tracks:
            track.age += 1

        matched_tracks, matched_dets, unmatched_tracks, unmatched_dets = self._associate(detections)

        # Update matched tracks
        for t_idx, d_idx in zip(matched_tracks, matched_dets):
            track = self.tracks[t_idx]
            det = detections[d_idx]
            track.update(det, frame_number, timestamp_sec, self.max_history)
            if track.hits >= self.min_hits:
                track.is_confirmed = True

        # Mark unmatched tracks as missed
        for t_idx in unmatched_tracks:
            self.tracks[t_idx].mark_missed()

        # Create new tracks for unmatched detections
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            new_track = Track(
                track_id=self._next_track_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
            )
            self._next_track_id += 1
            new_track.update(det, frame_number, timestamp_sec, self.max_history)
            if self.min_hits <= 1:
                new_track.is_confirmed = True
            self.tracks.append(new_track)

        # Prune dead tracks
        self.tracks = [
            t for t in self.tracks
            if t.time_since_update <= self.max_age
        ]

        # Return confirmed tracks (or all active if min_hits is 1)
        return [t for t in self.tracks if t.is_confirmed]

    def _associate(
        self,
        detections: List[Detection]
    ) -> Tuple[List[int], List[int], List[int], List[int]]:
        """Greedy IoU and centroid association matching detections with existing tracks."""
        if not self.tracks or not detections:
            return [], [], list(range(len(self.tracks))), list(range(len(detections)))

        iou_matrix = np.zeros((len(self.tracks), len(detections)), dtype=np.float32)

        # Greedy assignment based on IoU or centroid proximity
        for t_idx, track in enumerate(self.tracks):
            for d_idx, det in enumerate(detections):
                if track.class_name == det.class_name:
                    iou = track.bbox.iou(det.bbox)
                    # If boxes overlap
                    if iou > 0.0:
                        iou_matrix[t_idx, d_idx] = iou
                    else:
                        # Centroid distance fallback (normalized score)
                        dist = float(np.hypot(track.center[0] - det.bbox.center[0], track.center[1] - det.bbox.center[1]))
                        if dist <= 120.0:
                            # Map distance [0, 120] to score [0.24, 0.01]
                            iou_matrix[t_idx, d_idx] = max(0.01, 0.24 * (1.0 - dist / 120.0))
                        else:
                            iou_matrix[t_idx, d_idx] = -1.0
                else:
                    iou_matrix[t_idx, d_idx] = -1.0

        matched_tracks: List[int] = []
        matched_dets: List[int] = []

        used_tracks = set()
        used_dets = set()

        while True:
            max_iou = -1.0
            best_t = -1
            best_d = -1

            for t_idx in range(len(self.tracks)):
                if t_idx in used_tracks:
                    continue
                for d_idx in range(len(detections)):
                    if d_idx in used_dets:
                        continue
                    val = iou_matrix[t_idx, d_idx]
                    if val > max_iou and val > 0.0:
                        max_iou = val
                        best_t = t_idx
                        best_d = d_idx

            if best_t != -1 and best_d != -1:
                used_tracks.add(best_t)
                used_dets.add(best_d)
                matched_tracks.append(best_t)
                matched_dets.append(best_d)
            else:
                break

        unmatched_tracks = [t for t in range(len(self.tracks)) if t not in used_tracks]
        unmatched_dets = [d for d in range(len(detections)) if d not in used_dets]

        return matched_tracks, matched_dets, unmatched_tracks, unmatched_dets


# Public aliases for Stage 15-20 simulation and tests
TrackedObject = Track
TrackSnapshot = TrajectoryPoint

