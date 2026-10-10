"""Stage 2 Video and CCTV Input Tests."""

import os
from pathlib import Path
import pytest
import numpy as np
import cv2

from src.video.stream import FileVideoStream, RTSPStream
from src.video.camera import Camera


@pytest.fixture(scope="session")
def synthetic_test_video(tmp_path_factory) -> str:
    """Create a temporary synthetic 15-frame video for deterministic video stream testing."""
    temp_dir = tmp_path_factory.mktemp("video_test")
    video_path = str(temp_dir / "synthetic_test.mp4")
    
    width, height, fps = 320, 240, 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    
    for i in range(15):
        # Create solid color frame with a moving square
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.rectangle(frame, (i * 10, 50), (i * 10 + 30, 80), (0, 255, 0), -1)
        out.write(frame)
    out.release()
    
    assert Path(video_path).exists()
    return video_path


def test_file_video_stream_success(synthetic_test_video):
    """Test successful opening, frame reading, metadata and release on local video."""
    stream = FileVideoStream(synthetic_test_video)
    assert stream.open() is True
    assert stream.is_opened is True

    metadata = stream.get_metadata()
    assert metadata["source_type"] == "file"
    assert metadata["width"] == 320
    assert metadata["height"] == 240
    assert metadata["frame_count"] == 15

    frames_read = 0
    while True:
        ret, frame = stream.read()
        if not ret:
            break
        frames_read += 1
        assert frame is not None
        assert frame.shape == (240, 320, 3)

    assert frames_read == 15
    stream.release()
    assert stream.is_opened is False


def test_file_video_stream_nonexistent_file():
    """Test graceful failure when opening non-existent video file."""
    stream = FileVideoStream("data/videos/non_existent_clip.mp4")
    assert stream.open() is False
    assert stream.is_opened is False
    ret, frame = stream.read()
    assert ret is False
    assert frame is None


def test_camera_integration(synthetic_test_video):
    """Test Camera class managing stream lifecycle and metadata."""
    cam = Camera(
        camera_id="CAM-TEST",
        name="Test Camera",
        source=synthetic_test_video,
        latitude=18.5204,
        longitude=73.8567,
        location_desc="Testing intersection"
    )

    with cam:
        assert cam.stream.is_opened is True
        info = cam.get_info()
        assert info["camera_id"] == "CAM-TEST"
        assert info["location"]["latitude"] == 18.5204
        ret, frame = cam.read_frame()
        assert ret is True
        assert frame is not None

    # After exiting context manager, stream should be released
    assert cam.stream is None


def test_rtsp_stream_clean_handling(monkeypatch):
    """Test RTSPStream returns cleanly on invalid stream without unhandled exceptions."""
    from unittest.mock import MagicMock
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args, **kwargs: mock_cap)

    rtsp = RTSPStream("rtsp://127.0.0.1:8554/non_existent_stream")
    opened = rtsp.open()
    assert opened is False
    assert rtsp.is_opened is False
    ret, frame = rtsp.read()
    assert ret is False
    assert frame is None
    rtsp.release()
