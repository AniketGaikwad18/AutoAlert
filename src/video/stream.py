"""Video stream abstractions for AutoAlert.

Provides unified interface for reading from local video files, webcams,
and RTSP streams.
"""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import cv2
import numpy as np

logger = logging.getLogger("autoalert.video.stream")


class VideoStream(ABC):
    """Abstract base class for all video stream inputs."""

    @abstractmethod
    def open(self) -> bool:
        """Open the video stream source."""
        pass

    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read the next frame from the stream."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release underlying system resources."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return stream metadata (fps, dimensions, frame count, etc.)."""
        pass

    @property
    @abstractmethod
    def is_opened(self) -> bool:
        """Return True if stream is currently open."""
        pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class FileVideoStream(VideoStream):
    """Video stream handler for local video files (e.g., MP4, AVI, MKV)."""

    def __init__(self, file_path: str):
        self.file_path = str(file_path)
        self.cap: Optional[cv2.VideoCapture] = None
        self._frame_index = 0
        self._fps: float = 0.0
        self._width: int = 0
        self._height: int = 0
        self._frame_count: int = 0

    def open(self) -> bool:
        path = Path(self.file_path)
        if not path.exists():
            logger.error(f"Video file does not exist: {self.file_path}")
            return False

        self.cap = cv2.VideoCapture(self.file_path)
        if not self.cap.isOpened():
            logger.error(f"Failed to open video source: {self.file_path}")
            self.cap = None
            return False

        self._fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self._width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self._height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self._frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._frame_index = 0
        logger.info(
            f"Opened file stream '{self.file_path}': "
            f"{self._width}x{self._height} @ {self._fps:.1f}fps ({self._frame_count} frames)"
        )
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.cap.isOpened():
            return False, None

        ret, frame = self.cap.read()
        if ret and frame is not None:
            self._frame_index += 1
            return True, frame
        return False, None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info(f"Released video source: {self.file_path}")

    @property
    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_type": "file",
            "source_path": self.file_path,
            "fps": self._fps,
            "width": self._width,
            "height": self._height,
            "frame_count": self._frame_count,
            "current_frame_index": self._frame_index,
            "is_opened": self.is_opened,
        }


class WebcamStream(VideoStream):
    """Video stream handler for local USB/built-in webcams."""

    def __init__(self, device_index: int = 0):
        self.device_index = int(device_index)
        self.cap: Optional[cv2.VideoCapture] = None
        self._frame_index = 0

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            logger.error(f"Cannot access webcam device {self.device_index}")
            self.cap = None
            return False
        self._frame_index = 0
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        if ret:
            self._frame_index += 1
        return ret, frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    @property
    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def get_metadata(self) -> Dict[str, Any]:
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0) if self.cap else 0.0
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) if self.cap else 0
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) if self.cap else 0
        return {
            "source_type": "webcam",
            "device_index": self.device_index,
            "fps": fps,
            "width": width,
            "height": height,
            "current_frame_index": self._frame_index,
            "is_opened": self.is_opened,
        }


class RTSPStream(VideoStream):
    """Extensible RTSP stream handler for future CCTV box deployment."""

    def __init__(self, rtsp_url: str, reconnect_timeout_sec: float = 5.0):
        self.rtsp_url = str(rtsp_url)
        self.reconnect_timeout_sec = reconnect_timeout_sec
        self.cap: Optional[cv2.VideoCapture] = None
        self._frame_index = 0

    def open(self) -> bool:
        # Extensible RTSP opening logic
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            logger.warning(f"RTSP stream unavailable or connection failed: {self.rtsp_url}")
            self.cap = None
            return False
        self._frame_index = 0
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        if ret:
            self._frame_index += 1
        return ret, frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    @property
    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_type": "rtsp",
            "rtsp_url": self.rtsp_url,
            "current_frame_index": self._frame_index,
            "is_opened": self.is_opened,
        }
