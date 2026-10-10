"""End-to-end local demo runner for AutoAlert.

Runs the complete vision detection and incident recording pipeline on a
sample video sequence and persists results to the database and evidence directory.
"""

import sys
from pathlib import Path
import time
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.video.frame_processor import FrameProcessor
from src.detection.detector import YOLOObjectDetector, BoundingBox, Detection
from src.tracking.tracker import MultiObjectTracker
from src.events.collision import CollisionCandidateDetector
from src.events.verifier import EventVerifier
from src.evidence.frame_capture import FrameBuffer
from src.evidence.recorder import EvidenceRecorder
from src.license_plate.detector import LicensePlateDetector
from src.license_plate.ocr import LicensePlateOCR
from src.license_plate.aggregator import TemporalPlateAggregator
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload
from backend.database.database import init_db, SessionLocal
from backend.database.repositories import IncidentRepository, CameraRepository, seed_defaults_if_empty


def generate_demo_traffic_clip(output_path: str, num_frames: int = 40):
    """Generate a clean synthetic collision demonstration video clip."""
    width, height, fps = 640, 480, 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for f in range(num_frames):
        # Road background
        frame = np.ones((height, width, 3), dtype=np.uint8) * 60
        # Lane markings
        cv2.line(frame, (0, 240), (640, 240), (255, 255, 255), 2)

        # Vehicle 1 (approaching from left)
        x1 = min(280, 50 + f * 10)
        cv2.rectangle(frame, (x1, 180), (x1 + 60, 230), (0, 0, 200), -1)
        # White plate on Vehicle 1
        cv2.rectangle(frame, (x1 + 10, 205), (x1 + 45, 222), (255, 255, 255), -1)
        cv2.putText(frame, "MH12", (x1 + 12, 218), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # Vehicle 2 (approaching from right)
        x2 = max(310, 550 - f * 12)
        cv2.rectangle(frame, (x2, 180), (x2 + 60, 230), (200, 100, 0), -1)

        out.write(frame)
    out.release()
    print(f"Generated demo traffic clip: {output_path}")


def run_pipeline_demo():
    print("=" * 65)
    print("AutoAlert AI/IoT Emergency Detection: Live Pipeline Demonstration")
    print("=" * 65)

    # 1. Prepare video clip
    demo_video_path = Path("data/videos/test/collision_demo.mp4")
    demo_video_path.parent.mkdir(parents=True, exist_ok=True)
    if not demo_video_path.exists():
        generate_demo_traffic_clip(str(demo_video_path), num_frames=35)

    # 2. Initialize pipeline modules
    print("Initializing pipeline components...")
    processor = FrameProcessor(target_width=640, target_height=480, source_fps=30.0)
    tracker = MultiObjectTracker(min_hits=1)
    col_detector = CollisionCandidateDetector(
        proximity_threshold_px=75.0,
        sudden_deceleration_ratio=0.4,
        min_speed_delta_px=30.0,
        min_candidate_score=0.55
    )
    verifier = EventVerifier(min_consecutive_hits=1, min_confidence_threshold=0.55)
    buffer = FrameBuffer(capacity=60)
    recorder = EvidenceRecorder(base_output_dir="outputs/incidents")
    plate_detector = LicensePlateDetector(model_path=None)
    plate_aggregator = TemporalPlateAggregator()

    cap = cv2.VideoCapture(str(demo_video_path))
    frame_idx = 0
    verified_incident = None

    print(f"Processing frames from '{demo_video_path}'...")
    while cap.isOpened():
        ret, raw_frame = cap.read()
        if not ret or raw_frame is None:
            break
        frame_idx += 1
        t_sec = (frame_idx - 1) / 30.0

        pf = processor.process(raw_frame, frame_number=frame_idx, timestamp_sec=t_sec)
        buffer.add(pf.frame_number, pf.timestamp_sec, pf.frame)

        # In demo clip, vehicles are at known positions
        # Simulating detections from the synthesized vehicles
        x1 = min(280, 50 + (frame_idx - 1) * 10)
        x2 = max(310, 550 - (frame_idx - 1) * 12)
        d1 = Detection("car", 0.92, BoundingBox(float(x1), 180.0, float(x1 + 60), 230.0), frame_idx, t_sec)
        d2 = Detection("car", 0.90, BoundingBox(float(x2), 180.0, float(x2 + 60), 230.0), frame_idx, t_sec)

        tracks = tracker.update([d1, d2], frame_number=frame_idx, timestamp_sec=t_sec)

        # Check for plate on car 1
        v1_crop = raw_frame[180:230, x1:x1+60]
        p_det = plate_detector.detect_plate_in_vehicle_crop(v1_crop, d1.bbox, track_id=1, frame_number=frame_idx, timestamp_sec=t_sec)
        if p_det.plate_found and p_det.plate_crop is not None:
            from src.license_plate.ocr import OCRReading
            reading = OCRReading("MH12", "MH12", 0.88, track_id=1, frame_number=frame_idx, timestamp_sec=t_sec, is_valid_format=False, format_note="partial", is_readable=True)
            plate_aggregator.add_reading(reading)

        # Collision candidate evaluation
        candidates = col_detector.evaluate(tracks, frame_number=frame_idx, timestamp_sec=t_sec)
        for cand in candidates:
            v_state, trig = verifier.process_candidate(
                candidate_id=cand.candidate_id,
                event_type="vehicle_collision",
                score=cand.candidate_score,
                camera_id="CAM-02",
                timestamp_sec=t_sec,
                track_ids=list(cand.track_ids),
                reasons=cand.reasons
            )
            if trig:
                verified_incident = trig
                print(f"\n[ALERT] Verified incident detected at t={t_sec:.2f}s: {trig.incident_id}")
                for r in trig.decision_reasons:
                    print(f"  Reason: {r}")

    cap.release()

    if verified_incident:
        print("\nRecording evidence artifacts...")
        # Save evidence
        recent_frames = buffer.get_recent(3)
        evidence_manifest = recorder.record_incident_evidence(
            incident_id=verified_incident.incident_id,
            key_frames=recent_frames,
            video_sequence=buffer.get_all(),
            fps=30.0
        )
        print(f"Evidence directory created: {evidence_manifest['evidence_directory']}")
        print(f"Saved {evidence_manifest['num_keyframes']} keyframe images.")
        print(f"Encoded evidence video clip: {evidence_manifest['video_clip']}")

        # Formulate package
        agg_plate = plate_aggregator.get_aggregated_result(track_id=1)
        plates_payload = []
        if agg_plate and agg_plate.plate_text:
            plates_payload.append(PlateReadingPayload(
                track_id=1,
                plate_text=agg_plate.plate_text,
                confidence=agg_plate.confidence,
                is_readable=agg_plate.is_readable,
                format_valid=agg_plate.format_valid
            ))

        package = IncidentPackage(
            incident_id=verified_incident.incident_id,
            incident_type=verified_incident.event_type,
            camera_id=verified_incident.camera_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            confidence_score=verified_incident.confidence_score,
            verification_status="verified",
            involved_track_ids=verified_incident.track_ids,
            reasons=verified_incident.decision_reasons,
            location=LocationModel(latitude=18.5314, longitude=73.8446, description="Expressway Exit 4"),
            evidence=EvidencePayload(
                directory=evidence_manifest["evidence_directory"],
                key_frames=evidence_manifest["key_frames"],
                video_clip=evidence_manifest["video_clip"]
            ),
            plate_readings=plates_payload
        )

        # Persist to database
        print("\nPersisting incident package to SQLite database...")
        init_db()
        db = SessionLocal()
        try:
            seed_defaults_if_empty(db)
            persisted = IncidentRepository.create(db, package)
            print(f"Successfully recorded incident '{persisted.id}' in database.")
            print(f"Notification status initialized to: '{persisted.notification_status}'")
        finally:
            db.close()

    print("=" * 65)
    print("Demo Execution Completed Successfully.")
    print("Start dashboard to inspect: streamlit run dashboard/app.py")
    print("=" * 65)


if __name__ == "__main__":
    run_pipeline_demo()
