"""OpenCV frame processing layer for AutoAlert.

Standardizes raw video frames into structured ProcessedFrame objects with
frame numbering, derived timestamps, dimensional normalization, and validation.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Callable, Any
import numpy as np
import cv2
import logging

logger = logging.getLogger("autoalert.video.frame_processor")


@dataclass
class ProcessedFrame:
    """Represents a standardized frame payload passed through the vision pipeline."""
    frame: np.ndarray
    raw_frame: np.ndarray
    frame_number: int
    timestamp_sec: float
    original_shape: Tuple[int, int, int]
    processed_shape: Tuple[int, int, int]
    source_fps: float
    is_valid: bool = True

    @property
    def width(self) -> int:
        return self.frame.shape[1]

    @property
    def height(self) -> int:
        return self.frame.shape[0]

    @property
    def image(self) -> np.ndarray:
        return self.frame

    @property
    def timestamp(self) -> float:
        return self.timestamp_sec


class FrameProcessor:
    """Preprocesses raw frames from video streams into standardized pipeline inputs."""

    def __init__(
        self,
        metadata_or_width: Any = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        source_fps: float = 30.0,
        preprocessing_hook: Optional[Callable[[np.ndarray], np.ndarray]] = None
    ):
        if isinstance(metadata_or_width, dict):
            source_fps = float(metadata_or_width.get("fps", source_fps))
        elif isinstance(metadata_or_width, (int, float)):
            target_width = int(metadata_or_width)
        self.target_width = target_width
        self.target_height = target_height
        self.source_fps = float(source_fps if source_fps > 0 else 30.0)
        self.preprocessing_hook = preprocessing_hook
        self._frame_counter = 0

    def reset_counter(self) -> None:
        """Reset frame numbering counter."""
        self._frame_counter = 0

    def validate_frame(self, frame: Optional[np.ndarray]) -> bool:
        """Validate that frame is a non-empty, valid 3D or 2D image matrix."""
        if frame is None:
            return False
        if not isinstance(frame, np.ndarray):
            return False
        if frame.size == 0:
            return False
        if len(frame.shape) not in (2, 3):
            return False
        return True

    def process(
        self,
        raw_frame: Optional[np.ndarray],
        frame_number: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> Optional[ProcessedFrame]:
        """Validate, resize and augment raw frame into a ProcessedFrame."""
        if not self.validate_frame(raw_frame):
            logger.warning("Invalid or empty frame received during processing.")
            return None

        if frame_number is not None:
            self._frame_counter = frame_number
        else:
            self._frame_counter += 1

        curr_frame_num = self._frame_counter

        # Derive timestamp if not explicitly supplied
        if timestamp_sec is not None:
            derived_timestamp = float(timestamp_sec)
        elif frame_number is not None:
            derived_timestamp = curr_frame_num / self.source_fps
        else:
            derived_timestamp = (curr_frame_num - 1) / self.source_fps

        orig_shape = raw_frame.shape
        if len(orig_shape) == 2:
            orig_shape = (orig_shape[0], orig_shape[1], 1)

        # Configurable resizing
        processed = raw_frame
        if self.target_width and self.target_height:
            if (raw_frame.shape[1], raw_frame.shape[0]) != (self.target_width, self.target_height):
                processed = cv2.resize(
                    raw_frame,
                    (self.target_width, self.target_height),
                    interpolation=cv2.INTER_LINEAR
                )

        # Optional preprocessing hook
        if self.preprocessing_hook is not None:
            try:
                processed = self.preprocessing_hook(processed)
            except Exception as e:
                logger.error(f"Error executing custom preprocessing hook: {e}")

        proc_shape = processed.shape
        if len(proc_shape) == 2:
            proc_shape = (proc_shape[0], proc_shape[1], 1)

        return ProcessedFrame(
            frame=processed,
            raw_frame=raw_frame,
            frame_number=curr_frame_num,
            timestamp_sec=derived_timestamp,
            original_shape=orig_shape,
            processed_shape=proc_shape,
            source_fps=self.source_fps,
            is_valid=True
        )
