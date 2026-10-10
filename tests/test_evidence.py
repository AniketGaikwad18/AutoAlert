"""Stage 10 Evidence Recording Tests."""

from pathlib import Path
import numpy as np
import pytest

from src.evidence.frame_capture import FrameBuffer
from src.evidence.recorder import EvidenceRecorder, sanitize_filename
from src.evidence.incident_report import IncidentReport


def test_sanitize_filename():
    """Test filename sanitization removes special characters and path traversal tokens."""
    assert sanitize_filename("INC/01:A*") == "INC_01_A_"
    assert sanitize_filename("INC-2026-001") == "INC-2026-001"


def test_frame_buffer_ring_behavior():
    """Test FrameBuffer bounds to maximum capacity and time window slicing."""
    buf = FrameBuffer(capacity=5)
    sample_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    for i in range(8):
        buf.add(frame_number=i + 1, timestamp_sec=float(i), frame=sample_frame)

    assert len(buf) == 5
    # Oldest frames 0, 1, 2 should have been evicted; earliest should now be frame 4 (t=3.0)
    all_frames = buf.get_all()
    assert all_frames[0][0] == 4
    assert all_frames[-1][0] == 8

    # Window around t=5.0
    window = buf.get_frames_around(center_timestamp_sec=5.0, pre_seconds=1.0, post_seconds=1.0)
    timestamps = [item[1] for item in window]
    assert timestamps == [4.0, 5.0, 6.0]


def test_evidence_recorder_saves_frames_and_video(tmp_path):
    """Test EvidenceRecorder writes keyframe images, mp4 video clip and manifest."""
    recorder = EvidenceRecorder(base_output_dir=str(tmp_path / "incidents"))

    frame1 = np.zeros((120, 160, 3), dtype=np.uint8)
    frame2 = np.ones((120, 160, 3), dtype=np.uint8) * 200

    key_frames = [(10, 0.33, frame1), (25, 0.82, frame2)]
    video_sequence = [(i, i * 0.033, frame1) for i in range(10)]

    manifest = recorder.record_incident_evidence(
        incident_id="INC-TEST-001",
        key_frames=key_frames,
        video_sequence=video_sequence,
        fps=30.0,
        extra_meta={"camera_id": "CAM-01"}
    )

    inc_dir = Path(manifest["evidence_directory"])
    assert inc_dir.exists()
    assert manifest["num_keyframes"] == 2
    for kf_path in manifest["key_frames"]:
        assert Path(kf_path).exists()

    assert manifest["video_clip"] is not None
    assert Path(manifest["video_clip"]).exists()

    manifest_json_path = Path(manifest["manifest_path"])
    assert manifest_json_path.exists()


def test_incident_report_generation(tmp_path):
    """Test IncidentReport JSON export."""
    report = IncidentReport(
        incident_id="INC-0001",
        event_type="vehicle_collision",
        camera_id="CAM-01",
        timestamp_sec=14.5,
        confidence_score=0.88,
        verification_status="verified",
        reasons=["Abrupt deceleration", "Trajectory deflection"],
        evidence_manifest={"key_frames": ["frame1.jpg"]},
        location={"latitude": 18.5204, "longitude": 73.8567}
    )

    out_file = str(tmp_path / "incident_0001.json")
    report.save_json(out_file)
    assert Path(out_file).exists()
