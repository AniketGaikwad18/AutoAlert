"""
Stage 10 Controlled Local Demonstration Script.

Simulates a end-to-end pipeline run from frame buffering to incident verification
and evidence recording (saving key frames, video clips, and metadata JSON reports).
"""

import os
import cv2
import numpy as np

from src.core.event import VerificationState, VerifiedIncident
from src.evidence.frame_capture import FrameBuffer
from src.evidence.recorder import EvidenceRecorder, EvidenceRecorderConfig


def run_demo():
    print("=" * 60)
    print("AutoAlert Stage 10: Evidence Recording Controlled Demo")
    print("=" * 60)

    # 1. Initialize FrameBuffer & populate with synthetic video frames
    fps = 10.0
    buffer = FrameBuffer(max_buffer_size=100)
    width, height = 320, 240

    print("\n1. Generating synthetic video frames into FrameBuffer...")
    for frame_idx in range(1, 31):
        timestamp = frame_idx / fps
        # Create dark background
        img = np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)

        # Draw simulated moving vehicles (Car 1 red, Car 2 blue)
        x1 = min(140, int(30 + frame_idx * 4))
        x2 = max(160, int(280 - frame_idx * 4))
        cv2.rectangle(img, (x1, 100), (x1 + 40, 140), (0, 0, 220), -1)  # Red car
        cv2.rectangle(img, (x2, 100), (x2 + 40, 140), (220, 0, 0), -1)  # Blue car

        # Add frame index overlay text
        cv2.putText(
            img, f"Frame {frame_idx:02d}", (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
        )

        buffer.add_frame(frame_idx, timestamp, img)

    print(f"   Buffered {len(buffer)} frames.")

    # 2. Construct a VerifiedIncident trigger (simulating Stage 9 output)
    print("\n2. Simulating VerifiedIncident trigger from Stage 9...")
    verified_incident = VerifiedIncident(
        incident_id="INCIDENT-VEHICLE_COLLISION-F15-001",
        incident_type="vehicle_collision",
        verification_state=VerificationState.VERIFIED,
        confidence_score=0.92,
        initial_candidate_id="COLLISION_CANDIDATE-T1-T2-F10",
        first_detected_frame=10,
        verified_frame=15,
        timestamp=1.5,
        track_ids=[1, 2],
        signals_summary={
            "spatial_proximity_score": 1.0,
            "approach_rate_score": 0.9,
            "trajectory_convergence_score": 0.95,
            "abrupt_deceleration_score": 0.85,
            "closing_speed_px_per_frame": 8.0,
            "vehicle_classes": ["car", "car"],
        },
        verification_reason="Successfully verified vehicle collision over 3 consecutive frames with score 0.92 >= 0.65",
    )

    print(f"   Incident ID: {verified_incident.incident_id}")
    print(f"   Type: {verified_incident.incident_type}")
    print(f"   Confidence Score: {verified_incident.confidence_score:.2f}")

    # 3. Configure EvidenceRecorder
    output_dir = "outputs/evidence"
    config = EvidenceRecorderConfig(
        output_dir=output_dir,
        save_key_frames=True,
        save_video_clip=True,
        pre_event_buffer_seconds=0.5,
        post_event_buffer_seconds=1.0,
        fps=fps,
        video_codec="mp4v",
    )
    recorder = EvidenceRecorder(config=config)

    # 4. Execute evidence recording
    print(f"\n3. Recording evidence package to '{output_dir}'...")
    report = recorder.record_evidence(verified_incident, buffer)

    if report is not None:
        print("\nSUCCESS: Evidence Package Created!")
        print(f"   Report JSON: {report.evidence_files.get('report_json')}")
        print(f"   Key Frames:  {report.evidence_files.get('key_frames')}")
        print(f"   Video Clip:  {report.evidence_files.get('video_clip')}")

        folder = os.path.dirname(report.evidence_files.get("report_json", ""))
        full_path = os.path.abspath(os.path.join(output_dir, folder))
        print(f"\n   Package directory: {full_path}")
    else:
        print("\nERROR: Failed to record evidence package.")


if __name__ == "__main__":
    run_demo()
