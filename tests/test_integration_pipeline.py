"""Stage 18 End-to-End Pipeline Integration Test.

Validates complete pipeline flow:
Video Frame -> Frame Processor -> Object Detector -> Tracker ->
Candidate Generator -> Verifier -> Evidence Recorder -> Incident Package -> Backend Database.
"""

from pathlib import Path
import numpy as np
import pytest

from src.video.frame_processor import FrameProcessor
from src.detection.detector import BoundingBox, Detection
from src.tracking.tracker import MultiObjectTracker
from src.events.collision import CollisionCandidateDetector
from src.events.verifier import EventVerifier
from src.evidence.frame_capture import FrameBuffer
from src.evidence.recorder import EvidenceRecorder
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload
from backend.database.database import create_engine, sessionmaker, Base
from backend.database.repositories import IncidentRepository
from sqlalchemy.pool import StaticPool


def test_end_to_end_pipeline_simulation(tmp_path):
    """Simulate complete AutoAlert pipeline from frame ingestion to database persistence."""
    # 1. Video & Frame Processing
    processor = FrameProcessor(target_width=640, target_height=480, source_fps=30.0)
    raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    proc_frame = processor.process(raw_frame, frame_number=1, timestamp_sec=0.0)
    assert proc_frame is not None
    assert proc_frame.width == 640

    # 2. Frame Buffer
    buffer = FrameBuffer(capacity=30)
    buffer.add(proc_frame.frame_number, proc_frame.timestamp_sec, proc_frame.frame)

    # 3. Tracking & Candidate Detection
    tracker = MultiObjectTracker(min_hits=1)
    col_detector = CollisionCandidateDetector(min_candidate_score=0.50, min_speed_delta_px=30.0)
    verifier = EventVerifier(min_consecutive_hits=1, min_confidence_threshold=0.50)

    # Step through frames: approach, convergence, then sudden impact/deceleration
    positions_car1 = [
        (50, 80, 90, 120),    # t=0.0, speed init
        (100, 80, 140, 120),  # t=0.033, moving fast ~1500 px/s
        (140, 80, 180, 120),  # t=0.066, moving fast
        (142, 80, 182, 120),  # t=0.100, sudden halt/crash at x=142 (speed drops from 1200 to 60)
    ]
    positions_car2 = [
        (250, 80, 290, 120),  # t=0.0
        (200, 80, 240, 120),  # t=0.033
        (160, 80, 200, 120),  # t=0.066
        (158, 80, 198, 120),  # t=0.100, sudden halt/crash near car 1
    ]

    verified_trigger = None
    for step in range(4):
        t = step * 0.033
        b1 = positions_car1[step]
        b2 = positions_car2[step]
        d1 = Detection("car", 0.90, BoundingBox(b1[0], b1[1], b1[2], b1[3]))
        d2 = Detection("car", 0.88, BoundingBox(b2[0], b2[1], b2[2], b2[3]))

        tracks = tracker.update([d1, d2], frame_number=step + 1, timestamp_sec=t)
        buffer.add(step + 1, t, raw_frame)

        candidates = col_detector.evaluate(tracks, frame_number=step + 1, timestamp_sec=t)
        for cand in candidates:
            v_state, trig = verifier.process_candidate(
                candidate_id=cand.candidate_id,
                event_type="vehicle_collision",
                score=cand.candidate_score,
                camera_id="CAM-01",
                timestamp_sec=t,
                track_ids=list(cand.track_ids),
                reasons=cand.reasons
            )
            if trig:
                verified_trigger = trig

    assert verified_trigger is not None

    # 4. Evidence Recording
    recorder = EvidenceRecorder(base_output_dir=str(tmp_path / "incidents"))
    evidence_manifest = recorder.record_incident_evidence(
        incident_id=verified_trigger.incident_id,
        key_frames=[(1, 0.0, proc_frame.frame)],
        video_sequence=buffer.get_all(),
        fps=30.0
    )
    assert Path(evidence_manifest["manifest_path"]).exists()

    # 5. Incident Package Formation
    package = IncidentPackage(
        incident_id=verified_trigger.incident_id,
        incident_type=verified_trigger.event_type,
        camera_id=verified_trigger.camera_id,
        timestamp="2026-10-10T12:00:00Z",
        confidence_score=verified_trigger.confidence_score,
        verification_status="verified",
        involved_track_ids=verified_trigger.track_ids,
        reasons=verified_trigger.decision_reasons,
        location=LocationModel(latitude=18.5204, longitude=73.8567, description="Shivajinagar"),
        evidence=EvidencePayload(
            directory=evidence_manifest["evidence_directory"],
            key_frames=evidence_manifest["key_frames"],
            video_clip=evidence_manifest["video_clip"]
        )
    )

    # 6. Database Persistence
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng)
    db = Session()

    persisted = IncidentRepository.create(db, package)
    assert persisted.id == verified_trigger.incident_id
    assert persisted.notification_status == "pending"

    # Query back
    fetched = IncidentRepository.get_by_id(db, verified_trigger.incident_id)
    assert fetched is not None
    assert fetched.incident_type == "vehicle_collision"
    db.close()
