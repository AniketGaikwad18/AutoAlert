"""
Demo Video Generator for AutoAlert AI Emergency Detection Platform.

Generates deterministic synthetic CCTV clips for exhibition demonstrations and testing.
"""

from __future__ import annotations

import os
import cv2
import numpy as np


def generate_sample_collision_video(target_path: str, num_frames: int = 40, fps: float = 15.0) -> str:
    """Generate a clean synthetic collision clip with license plate."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(target_path, fourcc, fps, (width, height))

    for idx in range(num_frames):
        img = np.full((height, width, 3), (25, 30, 38), dtype=np.uint8)

        # Road lanes
        cv2.rectangle(img, (0, 210), (640, 410), (45, 50, 60), -1)
        cv2.line(img, (0, 310), (640, 310), (160, 160, 160), 2)
        for dash_x in range(0, 640, 40):
            cv2.line(img, (dash_x, 310), (dash_x + 20, 310), (240, 240, 240), 2)

        # Converging vehicles
        if idx < 22:
            x1 = int(40 + idx * 10)
            x2 = int(520 - idx * 10)
        else:
            x1 = 260
            x2 = 295

        # Vehicle 1 (Red Car)
        cv2.rectangle(img, (x1, 260), (x1 + 65, 320), (30, 30, 220), -1)
        cv2.rectangle(img, (x1 + 10, 270), (x1 + 55, 310), (20, 20, 30), -1)
        # License plate on vehicle 1
        cv2.rectangle(img, (x1 + 5, 308), (x1 + 45, 318), (240, 240, 240), -1)
        cv2.putText(img, "MH12AB1234", (x1 + 6, 316), cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 0, 0), 1)

        # Vehicle 2 (Blue Truck)
        cv2.rectangle(img, (x2, 250), (x2 + 80, 325), (200, 70, 20), -1)
        cv2.rectangle(img, (x2 + 15, 260), (x2 + 65, 315), (25, 25, 35), -1)

        cv2.putText(
            img,
            f"AUTOALERT CCTV FEED | Frame {idx:02d}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 255),
            2,
        )
        out.write(img)

    out.release()
    return target_path
