"""Stage 3 Frame Processing Unit Tests."""

import numpy as np
import pytest
from src.video.frame_processor import FrameProcessor, ProcessedFrame


def test_frame_processor_standard():
    """Test standard frame ingestion, timestamp calculation and metadata."""
    processor = FrameProcessor(source_fps=30.0)
    raw = np.zeros((480, 640, 3), dtype=np.uint8)

    pf1 = processor.process(raw)
    assert pf1 is not None
    assert pf1.frame_number == 1
    assert pf1.timestamp_sec == 0.0
    assert pf1.width == 640
    assert pf1.height == 480
    assert pf1.source_fps == 30.0
    assert pf1.is_valid is True

    pf2 = processor.process(raw)
    assert pf2 is not None
    assert pf2.frame_number == 2
    assert pytest.approx(pf2.timestamp_sec, 0.001) == 1.0 / 30.0


def test_frame_processor_resizing():
    """Test configurable frame resizing."""
    processor = FrameProcessor(target_width=320, target_height=240, source_fps=25.0)
    raw = np.zeros((1080, 1920, 3), dtype=np.uint8)

    pf = processor.process(raw)
    assert pf is not None
    assert pf.width == 320
    assert pf.height == 240
    assert pf.original_shape == (1080, 1920, 3)
    assert pf.processed_shape == (240, 320, 3)


def test_frame_processor_validation_empty_frames():
    """Test frame validation rejects None, empty arrays, or invalid shapes."""
    processor = FrameProcessor()

    assert processor.process(None) is None
    assert processor.process(np.array([])) is None
    assert processor.process(np.zeros((0, 0, 3), dtype=np.uint8)) is None
    assert processor.process("not an array") is None  # type: ignore


def test_frame_processor_custom_hook():
    """Test optional custom preprocessing hook."""
    def invert_hook(frame: np.ndarray) -> np.ndarray:
        return 255 - frame

    processor = FrameProcessor(preprocessing_hook=invert_hook)
    raw = np.zeros((100, 100, 3), dtype=np.uint8)
    pf = processor.process(raw)
    assert pf is not None
    assert pf.frame[0, 0, 0] == 255
