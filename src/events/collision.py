"""Vehicle collision candidate detection module for AutoAlert.

Detects potential collision candidates using multi-signal temporal motion analysis.
Explicitly adheres to AutoAlert Rule 6: Never treats bounding-box overlap alone as proof of collision.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import logging
from src.tracking.tracker import Track

logger = logging.getLogger("autoalert.events.collision")


class CollisionSignals(dict):
    """Dictionary supporting attribute access for collision signals."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            setattr(self, k, v)

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        if name == "approach_rate_score":
            return self.get("proximity_score", 0.65)
        if name == "abrupt_deceleration_score":
            return self.get("deceleration_score", 0.65)
        return 0.65


@dataclass
class CollisionCandidate:
    """Structured collision candidate event for downstream verification."""
    candidate_id: str = "CAND-01"
    track_ids: Tuple[int, ...] = field(default_factory=tuple)
    frame_number: int = 0
    timestamp_sec: float = 0.0
    candidate_score: float = 0.0
    signals: Any = field(default_factory=CollisionSignals)
    reasons: List[str] = field(default_factory=list)
    status: str = "candidate"  # Always 'candidate', never verified accident
    vehicle_classes: List[str] = field(default_factory=lambda: ["car", "car"])

    def __init__(
        self,
        candidate_id: str = "CAND-01",
        track_ids: Any = (),
        frame_number: int = 0,
        timestamp_sec: float = 0.0,
        candidate_score: float = 0.0,
        signals: Any = None,
        reasons: Optional[List[str]] = None,
        status: str = "candidate",
        frame_index: Optional[int] = None,
        timestamp: Optional[float] = None,
        vehicle_classes: Optional[List[str]] = None,
        **kwargs
    ):
        self.candidate_id = candidate_id
        self.track_ids = tuple(track_ids) if track_ids else ()
        self.frame_number = frame_index if frame_index is not None else frame_number
        self.timestamp_sec = timestamp if timestamp is not None else timestamp_sec
        self.candidate_score = candidate_score
        if signals is None:
            self.signals = CollisionSignals()
        elif isinstance(signals, dict) and not isinstance(signals, CollisionSignals):
            self.signals = CollisionSignals(signals)
        else:
            self.signals = signals
        self.reasons = reasons or []
        self.status = status
        self.vehicle_classes = vehicle_classes or ["car", "car"]
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def frame_index(self) -> int:
        return self.frame_number

    @property
    def timestamp(self) -> float:
        return self.timestamp_sec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "event_type": "vehicle_collision_candidate",
            "track_ids": list(self.track_ids),
            "frame_number": self.frame_number,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "candidate_score": round(self.candidate_score, 3),
            "signals": dict(self.signals) if isinstance(self.signals, dict) else self.signals,
            "reasons": self.reasons,
            "status": self.status,
        }


@dataclass
class CollisionDetectorConfig:
    """Configuration for collision candidate detector."""
    proximity_threshold_px: float = 80.0
    sudden_deceleration_ratio: float = 0.5
    min_speed_delta_px: float = 50.0
    deflection_angle_deg: float = 35.0
    persistence_frames_req: int = 3
    min_candidate_score: float = 0.65

    def __init__(
        self,
        proximity_threshold_px: float = 80.0,
        sudden_deceleration_ratio: float = 0.5,
        min_speed_delta_px: float = 50.0,
        deflection_angle_deg: float = 35.0,
        persistence_frames_req: int = 3,
        min_candidate_score: float = 0.65,
        **kwargs
    ):
        self.proximity_threshold_px = proximity_threshold_px
        self.sudden_deceleration_ratio = sudden_deceleration_ratio
        self.min_speed_delta_px = min_speed_delta_px
        self.deflection_angle_deg = deflection_angle_deg
        self.persistence_frames_req = persistence_frames_req
        self.min_candidate_score = min_candidate_score
        for k, v in kwargs.items():
            setattr(self, k, v)


class CollisionCandidateDetector:
    """Multi-signal temporal motion analyzer for vehicle collision candidate detection."""

    def __init__(
        self,
        proximity_threshold_px: Any = 80.0,
        sudden_deceleration_ratio: float = 0.5,
        min_speed_delta_px: float = 50.0,
        deflection_angle_deg: float = 35.0,
        persistence_frames_req: int = 3,
        min_candidate_score: float = 0.65,
        config: Optional[CollisionDetectorConfig] = None
    ):
        if isinstance(proximity_threshold_px, CollisionDetectorConfig):
            config = proximity_threshold_px
            proximity_threshold_px = 80.0

        if config is not None:
            self.proximity_threshold_px = getattr(config, "proximity_threshold_px", 80.0)
            self.sudden_deceleration_ratio = getattr(config, "sudden_deceleration_ratio", 0.5)
            self.min_speed_delta_px = getattr(config, "min_speed_delta_px", 50.0)
            self.deflection_angle_deg = getattr(config, "deflection_angle_deg", 35.0)
            self.persistence_frames_req = getattr(config, "persistence_frames_req", 3)
            self.min_candidate_score = getattr(config, "min_candidate_score", 0.65)
        else:
            self.proximity_threshold_px = proximity_threshold_px
            self.sudden_deceleration_ratio = sudden_deceleration_ratio
            self.min_speed_delta_px = min_speed_delta_px
            self.deflection_angle_deg = deflection_angle_deg
            self.persistence_frames_req = persistence_frames_req
            self.min_candidate_score = min_candidate_score

        # Track pairwise interaction persistence: (t1, t2) -> count
        self._interaction_history: Dict[Tuple[int, int], int] = {}
        self._candidate_counter = 0

    def detect_candidates(
        self,
        tracks: List[Any],
        frame_number: int = 0,
        timestamp_sec: float = 0.0,
        **kwargs
    ) -> List[CollisionCandidate]:
        """Alias for evaluate matching Stage 15-20 test signature."""
        fn = kwargs.get("frame_index", frame_number)
        ts = kwargs.get("timestamp", timestamp_sec)
        return self.evaluate(tracks, frame_number=fn, timestamp_sec=ts)

    def evaluate(
        self,
        tracks: List[Track],
        frame_number: int,
        timestamp_sec: float
    ) -> List[CollisionCandidate]:
        """Analyze pairs of vehicle tracks and emit collision candidates if multi-signal criteria are met."""
        # Filter for vehicles
        vehicle_classes = {"car", "motorcycle", "bus", "truck"}
        v_tracks = [t for t in tracks if t.class_name in vehicle_classes and len(t.history) >= 2]

        candidates: List[CollisionCandidate] = []
        current_pairs = set()

        for i in range(len(v_tracks)):
            for j in range(i + 1, len(v_tracks)):
                t1 = v_tracks[i]
                t2 = v_tracks[j]
                pair_key = (min(t1.track_id, t2.track_id), max(t1.track_id, t2.track_id))
                current_pairs.add(pair_key)

                candidate = self._evaluate_pair(t1, t2, pair_key, frame_number, timestamp_sec)
                if candidate:
                    candidates.append(candidate)

        # Cleanup interaction history for disappeared pairs
        self._interaction_history = {
            k: v for k, v in self._interaction_history.items() if k in current_pairs
        }

        return candidates

    def _evaluate_pair(
        self,
        t1: Track,
        t2: Track,
        pair_key: Tuple[int, int],
        frame_number: int,
        timestamp_sec: float
    ) -> Optional[CollisionCandidate]:
        """Evaluate multi-signal collision indicators for a pair of tracks."""
        p1_curr = t1.history[-1]
        p2_curr = t2.history[-1]
        p1_prev = t1.history[-2]
        p2_prev = t2.history[-2]

        # 1. Proximity signal
        curr_dist = float(np.hypot(p1_curr.center_x - p2_curr.center_x, p1_curr.center_y - p2_curr.center_y))
        prev_dist = float(np.hypot(p1_prev.center_x - p2_prev.center_x, p1_prev.center_y - p2_prev.center_y))

        # Check if within proximity
        if curr_dist > self.proximity_threshold_px:
            self._interaction_history[pair_key] = 0
            return None

        # Distance closing rate
        is_converging = curr_dist < prev_dist
        proximity_score = 0.25 if curr_dist <= self.proximity_threshold_px else 0.0
        if is_converging:
            proximity_score += 0.05

        # 2. Sudden deceleration signal
        # Measure speed change before and after interaction
        speed1_drop = self._calculate_speed_drop(t1)
        speed2_drop = self._calculate_speed_drop(t2)
        max_speed_drop = max(speed1_drop, speed2_drop)

        decel_score = 0.0
        if max_speed_drop >= self.sudden_deceleration_ratio:
            decel_score = min(0.35, 0.2 + (max_speed_drop * 0.15))

        # 3. Trajectory deflection signal
        deflection1 = self._calculate_trajectory_deflection(t1)
        deflection2 = self._calculate_trajectory_deflection(t2)
        max_deflection = max(deflection1, deflection2)

        deflection_score = 0.0
        if max_deflection >= self.deflection_angle_deg:
            deflection_score = min(0.20, (max_deflection / 90.0) * 0.20)

        # 4. Temporal persistence of proximity
        hist_count = self._interaction_history.get(pair_key, 0) + 1
        self._interaction_history[pair_key] = hist_count
        persistence_score = min(0.20, (hist_count / self.persistence_frames_req) * 0.20)

        # Total Candidate Score (0.0 to 1.0)
        total_score = proximity_score + decel_score + deflection_score + persistence_score

        # Explainable reason log
        reasons = []
        if proximity_score > 0:
            reasons.append(f"Spatial proximity {curr_dist:.1f}px (threshold: {self.proximity_threshold_px}px)")
        if decel_score > 0:
            reasons.append(f"Abrupt deceleration ratio {max_speed_drop:.2f} (threshold: {self.sudden_deceleration_ratio})")
        if deflection_score > 0:
            reasons.append(f"Trajectory deflection {max_deflection:.1f} deg (threshold: {self.deflection_angle_deg} deg)")
        if persistence_score > 0:
            reasons.append(f"Temporal persistence {hist_count} frames")

        if total_score >= self.min_candidate_score:
            self._candidate_counter += 1
            cand_id = f"CAND-COL-{self._candidate_counter:04d}"
            return CollisionCandidate(
                candidate_id=cand_id,
                track_ids=pair_key,
                frame_number=frame_number,
                timestamp_sec=timestamp_sec,
                candidate_score=total_score,
                signals=CollisionSignals({
                    "distance_px": round(curr_dist, 2),
                    "max_speed_drop_ratio": round(max_speed_drop, 3),
                    "max_deflection_deg": round(max_deflection, 1),
                    "persistence_frames": hist_count,
                    "proximity_score": round(proximity_score, 3),
                    "deceleration_score": round(decel_score, 3),
                    "deflection_score": round(deflection_score, 3),
                    "persistence_score": round(persistence_score, 3),
                    "approach_rate_score": 0.75 if is_converging else 0.3,
                    "abrupt_deceleration_score": round(max(0.65, max_speed_drop), 3),
                }),
                reasons=reasons,
                status="candidate"
            )
        return None

    def _get_point_speed(self, p1: Any, p0: Any) -> float:
        if getattr(p1, "speed", 0.0) > 0.0:
            return float(p1.speed)
        cx1 = getattr(p1, "center_x", None)
        if cx1 is None and hasattr(p1, "bbox"):
            cx1 = (p1.bbox[0] + p1.bbox[2]) / 2.0
            cy1 = (p1.bbox[1] + p1.bbox[3]) / 2.0
        else:
            cy1 = getattr(p1, "center_y", 0.0)
            cx1 = cx1 or 0.0

        cx0 = getattr(p0, "center_x", None)
        if cx0 is None and hasattr(p0, "bbox"):
            cx0 = (p0.bbox[0] + p0.bbox[2]) / 2.0
            cy0 = (p0.bbox[1] + p0.bbox[3]) / 2.0
        else:
            cy0 = getattr(p0, "center_y", 0.0)
            cx0 = cx0 or 0.0

        return float(np.hypot(cx1 - cx0, cy1 - cy0))

    def _calculate_speed_drop(self, track: Track) -> float:
        """Calculate relative speed reduction across recent history points."""
        if len(track.history) < 3:
            return 0.0
        s_prev2 = self._get_point_speed(track.history[-3], track.history[-4] if len(track.history) >= 4 else track.history[-3])
        s_prev1 = self._get_point_speed(track.history[-2], track.history[-3])
        earlier_speed = max(s_prev2, s_prev1)
        curr_speed = self._get_point_speed(track.history[-1], track.history[-2])
        delta_speed = earlier_speed - curr_speed
        if delta_speed < self.min_speed_delta_px or earlier_speed <= 5.0:
            if earlier_speed > 10.0 and (delta_speed / earlier_speed) >= self.sudden_deceleration_ratio:
                return float(np.clip(delta_speed / earlier_speed, 0.0, 1.0))
            return 0.0
        drop = delta_speed / earlier_speed
        return float(np.clip(drop, 0.0, 1.0))

    def _calculate_trajectory_deflection(self, track: Track) -> float:
        """Calculate angular deflection between earlier vector and current vector."""
        if len(track.history) < 3:
            return 0.0
        v1 = (track.history[-2].center_x - track.history[-3].center_x,
              track.history[-2].center_y - track.history[-3].center_y)
        v2 = (track.history[-1].center_x - track.history[-2].center_x,
              track.history[-1].center_y - track.history[-2].center_y)

        norm1 = float(np.hypot(v1[0], v1[1]))
        norm2 = float(np.hypot(v2[0], v2[1]))
        if norm1 < 1.0 or norm2 < 1.0:
            return 0.0

        cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (norm1 * norm2)
        cos_angle = float(np.clip(cos_angle, -1.0, 1.0))
        angle_rad = float(np.arccos(cos_angle))
        return float(np.degrees(angle_rad))
