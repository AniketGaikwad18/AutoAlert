"""
Camera Registry and Location Resolution Engine (AutoAlert Demonstration Enhancement).

Architectural Invariant:
Recorded CCTV video files do NOT contain GPS telemetry.
The geographic location and zone identifiers are derived strictly from the
pre-configured Camera Registry.

Flow:
  Uploaded Video + Selected Camera ID -> Camera Registry -> Camera Location -> Incident Location
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional
import yaml

from backend.schemas.camera import CameraSchema
from src.core.incident import LocationInfo

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join("config", "cameras.yaml")


class CameraRegistry:
    """Central registry for managing registered CCTV cameras and resolving their geographic coordinates."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = config_path
        self._cameras: Dict[str, CameraSchema] = {}
        self.reload()

    def reload(self) -> None:
        """Reload cameras from the YAML configuration file, falling back to database repository."""
        self._cameras.clear()

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    cameras_list = data.get("cameras", [])
                    for cam_dict in cameras_list:
                        schema = CameraSchema(**cam_dict)
                        self._cameras[schema.camera_id] = schema
                logger.info("Loaded %d camera(s) from '%s'", len(self._cameras), self.config_path)
                return
            except Exception as e:
                logger.warning("Could not parse camera configuration file '%s': %s", self.config_path, e)

        # Fallback: Load from backend database repository if available
        try:
            from backend.repository import repository
            db_cameras = repository.list_cameras()
            for cam in db_cameras:
                self._cameras[cam.camera_id] = cam
            logger.info("Loaded %d camera(s) from database repository fallback", len(self._cameras))
        except Exception as e:
            logger.warning("Could not load cameras from database repository: %s", e)

    def register_camera(self, camera: CameraSchema) -> None:
        """Register or update a camera in the in-memory registry."""
        self._cameras[camera.camera_id] = camera

    def get_camera(self, camera_id: str) -> Optional[CameraSchema]:
        """Look up a camera by its unique identifier."""
        return self._cameras.get(camera_id)

    def list_cameras(self, enabled_only: bool = False) -> List[CameraSchema]:
        """List registered cameras, optionally filtering only enabled cameras."""
        cameras = list(self._cameras.values())
        if enabled_only:
            return [c for c in cameras if c.enabled and c.status.lower() == "active"]
        return cameras

    def get_camera_location(self, camera_id: str) -> Optional[LocationInfo]:
        """
        Resolve geographic coordinates and location metadata for a camera.

        Args:
            camera_id: Unique camera identifier (e.g. 'CAM-001').

        Returns:
            LocationInfo dataclass with location name, latitude, longitude, and zone_id,
            or None if the camera is not found in the registry.
        """
        cam = self.get_camera(camera_id)
        if not cam:
            logger.warning("Camera '%s' not found in CameraRegistry", camera_id)
            return None

        loc_name = cam.location_name or cam.location or f"Registered Location for {cam.name}"
        return LocationInfo(
            name=loc_name,
            latitude=cam.latitude,
            longitude=cam.longitude,
            zone_id=cam.zone_id,
        )


# Global singleton instance for easy import across dashboard and simulation controller
camera_registry = CameraRegistry()
