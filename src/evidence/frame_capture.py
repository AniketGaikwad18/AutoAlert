from dataclasses import dataclass
from collections import deque
from typing import List, Tuple, Optional, Any
import numpy as np
import logging

logger = logging.getLogger("autoalert.evidence.frame_capture")


@dataclass
class BufferedFrame:
    """Standardized buffered frame wrapper."""
    frame_number: int
    timestamp_sec: float
    frame: np.ndarray

    @property
    def timestamp(self) -> float:
        return self.timestamp_sec

    @property
    def image(self) -> np.ndarray:
        return self.frame


class FrameBuffer:
    """Fixed-capacity ring buffer holding recent frames for pre/post-incident evidence."""

    def __init__(self, capacity: int = 150, max_buffer_size: Optional[int] = None):
        cap = max_buffer_size if max_buffer_size is not None else capacity
        self.capacity = max(1, cap)
        # Stores tuples of (frame_number, timestamp_sec, frame_ndarray)
        self._buffer: deque = deque(maxlen=self.capacity)

    def add(self, frame_number: int, timestamp_sec: float, frame: np.ndarray) -> None:
        """Add a frame snapshot to the ring buffer."""
        if frame is None or frame.size == 0:
            return
        # Store a copy to avoid in-place mutations
        self._buffer.append((frame_number, timestamp_sec, frame.copy()))

    def add_frame(
        self,
        frame_number: int,
        timestamp: float = 0.0,
        image: Optional[np.ndarray] = None,
        **kwargs
    ) -> None:
        """Alias for adding a frame with timestamp / image keyword args."""
        img = image if image is not None else kwargs.get("frame")
        t_sec = timestamp if timestamp != 0.0 else kwargs.get("timestamp_sec", 0.0)
        self.add(frame_number, t_sec, img)

    def get_frames(self) -> List[Tuple[int, float, np.ndarray]]:
        """Alias for get_all."""
        return self.get_all()

    def get_all(self) -> List[Tuple[int, float, np.ndarray]]:
        """Retrieve all currently buffered frames in chronological order."""
        return list(self._buffer)

    def get_recent(self, n: int) -> List[Tuple[int, float, np.ndarray]]:
        """Retrieve the latest n frames from the buffer."""
        frames = list(self._buffer)
        return frames[-n:] if n < len(frames) else frames

    def get_frames_around(
        self,
        center_timestamp_sec: float,
        pre_seconds: float = 2.0,
        post_seconds: float = 2.0
    ) -> List[Tuple[int, float, np.ndarray]]:
        """Slice buffered frames within a temporal window around an event timestamp."""
        min_t = center_timestamp_sec - pre_seconds
        max_t = center_timestamp_sec + post_seconds
        return [item for item in self._buffer if min_t <= item[1] <= max_t]

    def clear(self) -> None:
        """Empty the buffer."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
