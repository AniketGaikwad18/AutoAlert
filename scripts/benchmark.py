"""Edge deployment benchmark script for AutoAlert.

Measures actual computational latency, memory footprint, and frame throughput
on the CURRENT prototype machine.
Adheres strictly to AutoAlert Rule 5: Never invent metrics or claim unverified edge performance.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import time
import json
import platform
import psutil
import numpy as np
import cv2

from src.video.frame_processor import FrameProcessor
from src.detection.detector import YOLOObjectDetector
from src.tracking.tracker import MultiObjectTracker
from src.events.collision import CollisionCandidateDetector
from src.events.verifier import EventVerifier


def run_benchmark(
    iterations: int = 20,
    width: int = 640,
    height: int = 480,
    model_name: str = "yolov8n.pt"
) -> dict:
    """Benchmark full pipeline on current hardware."""
    print("=" * 60)
    print("AutoAlert Hardware & Pipeline Performance Benchmark")
    print("=" * 60)

    proc_info = platform.processor() or "Generic x86_64"
    print(f"System: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Processor: {proc_info}")
    print(f"Python Version: {platform.python_version()}")
    print(f"Target Frame Resolution: {width}x{height}")
    print(f"Object Detector Model: {model_name}")
    print(f"Benchmark Iterations: {iterations}")
    print("-" * 60)

    # Initialize components
    processor = FrameProcessor(target_width=width, target_height=height, source_fps=30.0)
    detector = YOLOObjectDetector(model_path=model_name)
    tracker = MultiObjectTracker()
    col_detector = CollisionCandidateDetector()
    verifier = EventVerifier()

    # Generate synthetic traffic frame
    frame = np.ones((height, width, 3), dtype=np.uint8) * 100
    cv2.rectangle(frame, (100, 100), (250, 250), (20, 20, 220), -1)  # Synthetic vehicle shape
    cv2.rectangle(frame, (350, 150), (450, 280), (220, 20, 20), -1)

    # Warmup run
    print("Performing warmup inference...")
    pf = processor.process(frame, frame_number=1, timestamp_sec=0.0)
    if pf and detector.is_ready:
        detector.detect(pf.frame)

    proc = psutil.Process()
    cpu_measurements = []
    e2e_times = []
    detect_times = []
    track_times = []
    process_times = []

    print("Executing benchmark runs...")
    for i in range(iterations):
        t_start = time.perf_counter()

        # 1. Preprocess
        t_p0 = time.perf_counter()
        pf = processor.process(frame, frame_number=i + 1, timestamp_sec=i * 0.033)
        t_p1 = time.perf_counter()
        process_times.append(t_p1 - t_p0)

        # 2. Detect
        t_d0 = time.perf_counter()
        detections = detector.detect(pf.frame, frame_number=pf.frame_number, timestamp_sec=pf.timestamp_sec)
        t_d1 = time.perf_counter()
        detect_times.append(t_d1 - t_d0)

        # 3. Track
        t_t0 = time.perf_counter()
        tracks = tracker.update(detections, frame_number=pf.frame_number, timestamp_sec=pf.timestamp_sec)
        t_t1 = time.perf_counter()
        track_times.append(t_t1 - t_t0)

        # 4. Events & Verification
        cands = col_detector.evaluate(tracks, frame_number=pf.frame_number, timestamp_sec=pf.timestamp_sec)
        for c in cands:
            verifier.process_candidate(
                candidate_id=c.candidate_id,
                event_type="collision",
                score=c.candidate_score,
                camera_id="CAM-BENCH",
                timestamp_sec=pf.timestamp_sec,
                track_ids=list(c.track_ids)
            )

        t_end = time.perf_counter()
        e2e_times.append(t_end - t_start)
        cpu_measurements.append(psutil.cpu_percent(interval=None))

    # Aggregations
    mean_e2e = float(np.mean(e2e_times)) * 1000.0
    mean_detect = float(np.mean(detect_times)) * 1000.0
    mean_track = float(np.mean(track_times)) * 1000.0
    mean_proc = float(np.mean(process_times)) * 1000.0
    fps = 1000.0 / mean_e2e if mean_e2e > 0 else 0.0

    ram_mb = proc.memory_info().rss / (1024.0 * 1024.0)
    avg_cpu = float(np.mean(cpu_measurements)) if cpu_measurements else 0.0

    report = {
        "hardware": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "processor": proc_info,
            "python_version": platform.python_version(),
        },
        "pipeline": {
            "model": model_name,
            "resolution": f"{width}x{height}",
            "iterations": iterations,
        },
        "measured_metrics": {
            "frame_preprocess_latency_ms": round(mean_proc, 2),
            "object_detection_latency_ms": round(mean_detect, 2),
            "tracking_latency_ms": round(mean_track, 2),
            "end_to_end_latency_ms": round(mean_e2e, 2),
            "throughput_fps": round(fps, 1),
            "process_ram_mb": round(ram_mb, 1),
            "approx_cpu_utilization_percent": round(avg_cpu, 1),
        }
    }

    print("-" * 60)
    print("MEASURED BENCHMARK RESULTS (CURRENT MACHINE):")
    print(f"- Preprocessing Latency:  {mean_proc:.2f} ms")
    print(f"- Object Detection Time:  {mean_detect:.2f} ms")
    print(f"- Tracking Update Time:   {mean_track:.2f} ms")
    print(f"- End-to-End Latency:     {mean_e2e:.2f} ms")
    print(f"- Frame Throughput:       {fps:.1f} FPS")
    print(f"- Process RAM Footprint:  {ram_mb:.1f} MB")
    print("=" * 60)

    # Save to outputs/logs
    out_dir = Path("outputs/logs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Results saved to {out_file}")

    return report


if __name__ == "__main__":
    run_benchmark()
