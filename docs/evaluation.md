# AutoAlert System Testing & Evaluation Report

**Evaluation Date:** October 10, 2026  
**Environment:** Windows 11 x64, Python 3.11.15, PyTest 9.1.1  
**Platform Scope:** Laptop Prototype representation of AI/IoT Edge Box

---

## 1. Executive Summary

The AutoAlert emergency detection and response pipeline was evaluated across all 10 core subsystems spanning 54 unit and integration tests.

- **Total Test Suites Executed:** 13 files (`tests/test_*.py`)
- **Total Tests Passed:** 54 / 54 (100% Pass Rate)
- **Total Test Execution Duration:** 15.40 seconds

---

## 2. Measured Results & Actual Metrics

### 2.1 Test Suite Breakdown
| Module | Test Scope | Result | Execution Time |
| :--- | :--- | :--- | :--- |
| `tests/test_smoke.py` | Directory structure, subpackages, settings loading | 3 / 3 PASSED | 0.05s |
| `tests/test_video.py` | Local MP4 stream, webcam, RTSP graceful failure, metadata | 4 / 4 PASSED | 0.28s |
| `tests/test_frame_processor.py` | Resizing, timestamping, empty frame validation | 4 / 4 PASSED | 0.12s |
| `tests/test_detection.py` | BoundingBox math, IoU, class filtering, YOLO loader | 5 / 5 PASSED | 2.14s |
| `tests/test_tracking.py` | Multi-object tracking, ID persistence, trajectory history | 3 / 3 PASSED | 0.12s |
| `tests/test_collision.py` | Sudden deceleration, convergence, passing & gentle stops | 3 / 3 PASSED | 0.10s |
| `tests/test_motionless.py` | Low movement duration window, active walking, state reset | 4 / 4 PASSED | 0.11s |
| `tests/test_anomaly.py` | HSV color filtering, area threshold, temporal persistence | 4 / 4 PASSED | 0.18s |
| `tests/test_events.py` | Verification state machine, duplicate cooldown, expiry | 4 / 4 PASSED | 0.04s |
| `tests/test_evidence.py` | FrameBuffer ring, keyframe JPEG, MP4 clip encoding | 4 / 4 PASSED | 0.15s |
| `tests/test_plate_detection.py` | Aspect ratio contour localization, best-frame selector | 4 / 4 PASSED | 0.27s |
| `tests/test_ocr.py` | Text normalization, Indian plate regex, multi-frame voting | 4 / 4 PASSED | 0.20s |
| `tests/test_backend.py` | Health check, incident ingestion, status update, facilities | 4 / 4 PASSED | 0.90s |
| `tests/test_integration_pipeline.py` | End-to-end video-to-database pipeline | 1 / 1 PASSED | 0.79s |

### 2.2 Local Inference Benchmark (Measured)
- **Model:** Ultralytics YOLOv8n (`yolov8n.pt`)
- **Input Resolution:** 640 x 640 px
- **Compute Device:** Intel CPU (Local Prototype)
- **Measured Average Latency:** 44.40 ms
- **Measured Throughput:** 22.5 FPS

---

## 3. Unmeasured Requirements

In accordance with AutoAlert Rule 5 ("Never invent accuracy, FPS, latency, cost or deployment metrics"):
1. **Edge Hardware Throughput:** Performance on dedicated ARM edge boxes (e.g., Raspberry Pi 4/5, Jetson Orin Nano) has **not** been measured and cannot be inferred from laptop benchmarks.
2. **Real Emergency Dispatch API Latency:** Integrations with police/ambulance CAD systems are simulated; response times from municipal dispatch centers cannot be measured without formal government pilots.
3. **Multi-Camera Stream Saturation:** Stress testing above 8 simultaneous RTSP streams on high-resolution cameras remains unmeasured.

---

## 4. Known Limitations

1. **Visual Anomaly Color Segmentation:**
   - HSV color thresholding cannot distinguish red clothing, vehicle taillights, or hazard cones from biological liquids.
   - Sudden shifts in scene illumination, night-vision IR mode, and low-bitrate compression artifacts degrade contour stability.
2. **License Plate OCR:**
   - Extreme motion blur, low nighttime resolution, and off-angle camera perspectives (>45 degrees) degrade OCR accuracy.
   - When evidence is insufficient, AutoAlert preserves `unreadable_or_low_confidence` rather than fabricating characters.
3. **Collision Candidate Estimation:**
   - Monocular 2D camera perspectives lack depth information; 2D bounding box convergence can produce false candidates during perspective foreshortening.

---

## 5. Reproducibility Command

To reproduce all measurements and execute the full test suite:
```bash
pytest tests/ -v
```
