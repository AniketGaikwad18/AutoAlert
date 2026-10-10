# AutoAlert Edge-Deployment Benchmark & Hardware Readiness

**Document Version:** 1.0  
**Status:** Laptop Prototype Benchmarked; Edge Deployment Checklist Defined

---

## 1. Prototype Baseline Performance (Measured on Current Machine)

*All metrics below were empirically measured by executing `python scripts/benchmark.py` on the host prototype laptop. In accordance with Rule 5, zero metrics have been estimated or fabricated.*

### 1.1 Test Configuration
- **Operating System:** Windows 11 (AMD64)
- **Host Processor:** Intel Core Architecture (GenuineIntel x86_64)
- **Runtime:** Python 3.11.15
- **Vision Model:** Ultralytics YOLOv8n (`yolov8n.pt`, PyTorch float32 CPU)
- **Frame Resolution:** 640 x 480 px
- **Sample Iterations:** 20 consecutive inference cycles

### 1.2 Empirical Performance Measurements
| Metric | Measured Value | Analysis |
| :--- | :--- | :--- |
| **Frame Preprocessing** | **0.02 ms** | OpenCV bilinear resize and channel verification |
| **Object Detection (Inference)** | **38.54 ms** | PyTorch CPU forward pass |
| **Multi-Object Tracking** | **0.01 ms** | Greedy IoU / centroid association & state update |
| **Total End-to-End Latency** | **38.57 ms** | Time from raw frame arrival to event candidate evaluation |
| **Pipeline Throughput** | **25.9 FPS** | Real-time capable (>25 FPS CCTV stream ingest) |
| **Process Memory (RAM)** | **368.8 MB** | Peak RSS resident memory consumption |

---

## 2. Why Edge Performance Must NOT Be Guessed

In accordance with AutoAlert Engineering Rules:
- **Do not claim Raspberry Pi performance without running on Raspberry Pi.**
- **Do not select final hardware from guesses.**

An x86_64 laptop CPU possesses significantly higher single-core IPC, cache hierarchy, and power envelope (15W–45W) compared to low-power edge SBCs (e.g. Raspberry Pi 4/5: 5W–12W, ARM Cortex-A72/A76). Running PyTorch CPU models directly on ARM without hardware acceleration typically causes latency degradation (often dropping to 2–5 FPS) and high thermal throttling.

---

## 3. Candidate Edge Hardware Qualification Checklist

Before deploying AutoAlert onto candidate edge boxes (Raspberry Pi 5, NVIDIA Jetson Orin Nano, Orange Pi 5 with RK3588 NPU, or Hailo-8 AI accelerators), the following criteria must be empirically measured on the physical target unit:

### 3.1 Compute & Runtime Compatibility
- [ ] Export YOLOv8 to target runtime:
  - ONNX Runtime / NCNN for CPU ARM
  - TensorRT INT8 / FP16 for NVIDIA Jetson
  - Rockchip RKNN for RK3588 NPU
  - Hailo TAPPAS runtime for Raspberry Pi 5 AI Kit
- [ ] Measure post-quantization accuracy retention (ensure mAP degradation < 2%).

### 3.2 Real-Time Throughput & Latency
- [ ] Sustained FPS at 1080p and 720p stream ingest.
- [ ] Minimum target: ≥ 15 FPS sustained per camera feed.

### 3.3 Thermal & Power Behavior
- [ ] Measure steady-state junction temperature under continuous 100% video analysis load for 12 hours.
- [ ] Verify passive or active cooling prevents thermal throttling (CPU clock drop).
- [ ] Measure peak and average power draw (Watts) to size PoE (Power over Ethernet) or 12V DC power supplies.

### 3.4 Camera Ingestion & Recovery
- [ ] Verify RTSP stream reconnection stability over intermittent Wi-Fi / Ethernet drops.
- [ ] Confirm H.264/H.265 hardware video decoding (V4L2 / NVDEC) offloads CPU during multi-stream capture.
- [ ] Ensure automatic watchdog restart if memory leak or hardware fault occurs.
