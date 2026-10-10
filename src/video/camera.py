"""Camera device abstraction and stream factory for AutoAlert."""

import logging
from typing import Dict, Any, Optional
from src.video.stream import VideoStream, FileVideoStream, WebcamStream, RTSPStream

logger = logging.getLogger("autoalert.video.camera")


class Camera:
    """Represents a monitored CCTV camera node connected to the AI/IoT Box."""

    def __init__(
        self,
        camera_id: str,
        name: str,
        source: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_desc: str = ""
    ):
        self.camera_id = camera_id
        self.name = name
        self.source = source
        self.latitude = latitude
        self.longitude = longitude
        self.location_desc = location_desc
        self.stream: Optional[VideoStream] = None

    def initialize_stream(self) -> bool:
        """Instantiate and open the appropriate stream based on the source specification."""
        src_str = str(self.source).strip()

        if src_str.isdigit():
            self.stream = WebcamStream(device_index=int(src_str))
        elif src_str.lower().startswith("rtsp://") or src_str.lower().startswith("http://"):
            self.stream = RTSPStream(rtsp_url=src_str)
        else:
            self.stream = FileVideoStream(file_path=src_str)

        success = self.stream.open()
        if success:
            logger.info(f"Initialized stream for camera [{self.camera_id}] ({self.name})")
        else:
            logger.error(f"Failed to open stream for camera [{self.camera_id}] from source '{self.source}'")
        return success

    def read_frame(self):
        """Read a single frame from the active stream."""
        if self.stream is None or not self.stream.is_opened:
            return False, None
        return self.stream.read()

    def get_info(self) -> Dict[str, Any]:
        """Return camera properties and stream metadata."""
        meta = self.stream.get_metadata() if self.stream else {}
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "source": self.source,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "description": self.location_desc,
            },
            "stream_metadata": meta,
        }

    def close(self) -> None:
        """Release underlying camera stream resources."""
        if self.stream:
            self.stream.release()
            self.stream = None
            logger.info(f"Closed camera [{self.camera_id}]")

    def __enter__(self):
        self.initialize_stream()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
