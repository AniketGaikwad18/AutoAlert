"""
AutoAlert Local End-to-End Pipeline Demonstration Script (Stage 20).

Demonstrates the complete local pipeline lifecycle:
1. Video / Frame Ingestion -> FrameProcessor
2. Object Detection & Multi-Object Tracking
3. Multi-Signal Collision Candidate Detection
4. Multi-Frame Verification Engine
5. Evidence Recording (Key frames, metadata JSON)
6. License Plate OCR & Temporal Aggregation
7. Incident Package Construction & Serialization
8. Database Persistence via SQLAlchemy / Repository
9. Nearest Emergency Facility Matching & Simulated Dispatch Lifecycle

Usage:
    python scripts/run_local_demo.py
    python scripts/run_local_demo.py --frames 30 --output outputs/evidence
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import cv2
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.video.frame_processor import FrameProcessor
from src.detection.detector import Detection
from src.tracking.tracker import MultiObjectTracker, TrackedObject, TrackSnapshot
from src.events.collision import CollisionCandidateDetector
from src.events.verifier import EventVerifier, VerifierConfig
from src.evidence.frame_capture import FrameBuffer
from src.evidence.recorder import EvidenceRecorder, EvidenceRecorderConfig
from src.license_plate.preprocessor import PlateCrop
from src.license_plate.ocr import PlateOCREngine
from src.license_plate.aggregator import PlateTemporalAggregator
from src.core.incident import IncidentPackage, LocationInfo
from backend.repository import repository
from dashboard.api_client import DashboardAPIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("local_demo")


def run_demo(num_frames: int = 30, evidence_out: str = "outputs/evidence") -> None:
    print("=" * 72)
    print("  AUTOALERT LOCAL END-TO-END PIPELINE DEMONSTRATION (STAGE 20)")
    print("  Prototype AI/IoT Box Emergency Detection Flow")
    print("=" * 72)

    os.makedirs("data", exist_ok=True)
    os.makedirs(evidence_out, exist_ok=True)

    # --------------------------------------------------------------------------
    # 1. Video Frame Ingestion & Normalization
    # --------------------------------------------------------------------------
    print("\n[Step 1/8] Ingesting and Preprocessing Synthetic Video Frames...")
    fps = 10.0
    width, height = 640, 480
    metadata = {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": num_frames,
        "source_path": "synthetic_demo_feed",
    }
    processor = FrameProcessor(metadata, target_width=width, target_height=height)
    frame_buffer = FrameBuffer(max_buffer_size=100)

    raw_frames = []
    for frame_idx in range(num_frames):
        timestamp = frame_idx / fps
        img = np.full((height, width, 3), (35, 35, 35), dtype=np.uint8)

        # Draw road lanes
        cv2.line(img, (0, 240), (640, 240), (100, 100, 100), 2)
        cv2.line(img, (0, 360), (640, 360), (100, 100, 100), 2)

        # Draw converging vehicle 1 (moving right) and vehicle 2 (moving left)
        x1 = min(280, int(60 + frame_idx * 10))
        x2 = max(310, int(540 - frame_idx * 10))
        cv2.rectangle(img, (x1, 260), (x1 + 60, 320), (0, 0, 200), -1)   # Vehicle 1 (Red)
        cv2.rectangle(img, (x2, 260), (x2 + 60, 320), (200, 0, 0), -1)   # Vehicle 2 (Blue)

        cv2.putText(img, f"Frame {frame_idx:02d} - AutoAlert Ingestion", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        proc_frame = processor.process(img, frame_idx)
        raw_frames.append(proc_frame.image)
        frame_buffer.add_frame(frame_idx, timestamp, proc_frame.image)

    print(f"  -> Generated and buffered {len(raw_frames)} normalized frames.")

    # --------------------------------------------------------------------------
    # 2. Object Tracking
    # --------------------------------------------------------------------------
    print("\n[Step 2/8] Executing Multi-Object Tracking (IoU-Hungarian)...")
    tracker = MultiObjectTracker(min_hits=1)
    for idx, frame in enumerate(raw_frames):
        x1 = min(280, int(60 + idx * 10))
        x2 = max(310, int(540 - idx * 10))
        dets = [
            Detection(class_name="car", confidence=0.92, bbox=(x1, 260, x1 + 60, 320)),
            Detection(class_name="truck", confidence=0.89, bbox=(x2, 260, x2 + 60, 320)),
        ]
        tracks = tracker.update(dets, frame_index=idx)
    print(f"  -> Active tracks tracked across frames: {[t.track_id for t in tracks]}")

    # --------------------------------------------------------------------------
    # 3. Collision Candidate Scoring
    # --------------------------------------------------------------------------
    print("\n[Step 3/8] Evaluating 4-Signal Collision Candidate Logic...")
    from src.events.collision import CollisionCandidate, SignalReason
    collision_detector = CollisionCandidateDetector()

    # Build tracks with high closing speed and sudden deceleration at collision point
    h1 = [
        (0, (50, 260, 110, 320)),
        (1, (90, 260, 150, 320)),
        (2, (130, 260, 190, 320)),
        (3, (170, 260, 230, 320)),
        (4, (210, 260, 270, 320)),
        (5, (215, 260, 275, 320)),  # abrupt stop
    ]
    h2 = [
        (0, (450, 260, 510, 320)),
        (1, (410, 260, 470, 320)),
        (2, (370, 260, 430, 320)),
        (3, (330, 260, 390, 320)),
        (4, (290, 260, 350, 320)),
        (5, (285, 260, 345, 320)),  # abrupt stop
    ]
    snaps1 = [TrackSnapshot(bbox=b, confidence=0.92, frame_index=f) for f, b in h1]
    snaps2 = [TrackSnapshot(bbox=b, confidence=0.89, frame_index=f) for f, b in h2]
    t1 = TrackedObject(track_id=1, class_name="car", bbox=h1[-1][1], confidence=0.92, history=snaps1, age=len(h1), hits=len(h1), time_since_update=0)
    t2 = TrackedObject(track_id=2, class_name="truck", bbox=h2[-1][1], confidence=0.89, history=snaps2, age=len(h2), hits=len(h2), time_since_update=0)

    candidates = collision_detector.detect_candidates([t1, t2], frame_index=5, timestamp=0.5)
    print(f"  -> Detected {len(candidates)} collision candidate(s).")
    if not candidates:
        print("  [INFO] Creating standard candidate for demo.")
        cand = CollisionCandidate(
            candidate_id="CAND-COLLISION-DEMO-01",
            frame_index=5,
            timestamp=0.5,
            track_ids=[1, 2],
            candidate_score=0.88,
            signals=SignalReason(
                spatial_proximity_score=1.0,
                approach_rate_score=0.9,
                trajectory_convergence_score=0.95,
                abrupt_deceleration_score=0.85,
            ),
            vehicle_classes=["car", "truck"],
        )
    else:
        cand = candidates[0]
    print(f"  -> Candidate ID: {cand.candidate_id}, Initial Score: {cand.candidate_score:.2f}")

    # --------------------------------------------------------------------------
    # 4. Multi-Frame Verification Engine
    # --------------------------------------------------------------------------
    print("\n[Step 4/8] Running Multi-Frame Verification State Machine...")
    verifier = EventVerifier(config=VerifierConfig(required_confirmations=1, min_confidence_score=0.60))
    verified_incident = verifier.process_candidate(cand, frame_index=num_frames - 1, timestamp=(num_frames - 1) / fps)
    print(f"  -> Verification Status: {verified_incident.verification_state.value.upper()}")
    print(f"  -> Final Confidence Score: {verified_incident.confidence_score:.2f}")

    # --------------------------------------------------------------------------
    # 5. Evidence Recording
    # --------------------------------------------------------------------------
    print(f"\n[Step 5/8] Recording Key Frames & Evidence Package to '{evidence_out}'...")
    recorder_config = EvidenceRecorderConfig(
        output_dir=evidence_out,
        save_key_frames=True,
        save_video_clip=False, # Faster and robust in demo
        fps=fps,
    )
    recorder = EvidenceRecorder(config=recorder_config)
    ev_report = recorder.record_evidence(verified_incident, frame_buffer)
    ev_frames = ev_report.evidence_files.get("key_frames", []) if ev_report else []
    print(f"  -> Saved {len(ev_frames)} key frames to evidence directory.")

    # --------------------------------------------------------------------------
    # 6. License Plate OCR & Temporal Aggregation
    # --------------------------------------------------------------------------
    print("\n[Step 6/8] Performing License Plate Detection & OCR Aggregation...")
    ocr_engine = PlateOCREngine()
    aggregator = PlateTemporalAggregator()

    plate_img = np.full((60, 200, 3), (240, 240, 240), dtype=np.uint8)
    cv2.rectangle(plate_img, (2, 2), (198, 58), (0, 0, 0), 2)
    cv2.putText(plate_img, "MH12DE1432", (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    crop = PlateCrop(
        crop_id="CROP-DEMO-01",
        track_id=1,
        frame_index=num_frames - 1,
        raw_crop=plate_img,
        processed_crop=plate_img,
        bbox=(20, 20, 80, 220),
        confidence=0.90,
        quality_score=0.95,
    )
    reading = ocr_engine.read_plate(crop)
    aggregator.add_reading(reading)
    best_plate = aggregator.aggregate_track(track_id=1)
    print(f"  -> Best aggregated plate: '{best_plate.best_plate_number}' (conf: {best_plate.aggregated_confidence:.2f}, status: {best_plate.status})")

    # --------------------------------------------------------------------------
    # 7. Incident Package Construction & Database Ingestion
    # --------------------------------------------------------------------------
    print("\n[Step 7/8] Constructing Incident Package & Ingesting to Database...")
    pkg = IncidentPackage(
        incident_id=verified_incident.incident_id,
        incident_type="vehicle_collision",
        camera_id="CAM-NORTH-01",
        timestamp=verified_incident.timestamp,
        verification_status="verified",
        confidence_score=verified_incident.confidence_score,
        involved_track_ids=[1, 2],
        evidence_frames=ev_frames,
        location=LocationInfo(latitude=18.5204, longitude=73.8567, name="North Gate Junction"),
        plate_readings=[
            {
                "track_id": 1,
                "plate_number": best_plate.best_plate_number,
                "confidence": best_plate.aggregated_confidence,
                "format_validated": best_plate.format_validated,
                "status": best_plate.status,
            }
        ],
        reason_metadata={"notes": "Stage 20 Local Demo Execution"},
    )
    from backend.schemas.incident import IncidentPackageCreateSchema
    schema_payload = IncidentPackageCreateSchema(**pkg.to_dict())
    saved_inc = repository.add_incident(schema_payload)
    print(f"  -> Persisted incident '{saved_inc.incident_id}' to SQLite database.")

    # --------------------------------------------------------------------------
    # 8. Nearest Facility Matching & Simulated Dispatch Lifecycle
    # --------------------------------------------------------------------------
    print("\n[Step 8/8] Executing Simulated Facility Matching & Notification Workflow...")
    dash_client = DashboardAPIClient()
    matched = dash_client.match_facilities(
        incident_id=saved_inc.incident_id,
        latitude=18.5204,
        longitude=73.8567,
        limit=2,
    )
    print(f"  -> Matched {len(matched)} simulated nearby emergency facilities:")
    for m in matched:
        print(f"      - {m['name']} ({m['type']}) : {m.get('distance_km', 0.0):.2f} km away")

    if matched:
        target_fac = matched[0]
        notif = dash_client.trigger_notification(
            incident_id=saved_inc.incident_id,
            facility_id=target_fac["facility_id"],
            message=f"DEMO DISPATCH: Vehicle collision at North Gate Junction",
        )
        print(f"  -> Created simulated dispatch notification '{notif['notification_id']}' (Status: {notif['status']})")

        # Advance notification state
        ack = dash_client.update_notification_status(notif["notification_id"], "acknowledged", reason="Desk operator confirmed")
        print(f"  -> Notification advanced to: '{ack['status']}'")

    print("\n" + "=" * 72)
    print("  LOCAL DEMO COMPLETED SUCCESSFULLY!")
    print("  To view this incident in the Command Center UI, run:")
    print("      python scripts/start_dashboard.py")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoAlert Local End-to-End Demo")
    parser.add_argument("--frames", type=int, default=30, help="Number of synthetic frames (default: 30)")
    parser.add_argument("--output", type=str, default="outputs/evidence", help="Evidence output directory")
    args = parser.parse_args()

    run_demo(num_frames=args.frames, evidence_out=args.output)


if __name__ == "__main__":
    main()
