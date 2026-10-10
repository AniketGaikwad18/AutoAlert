# AutoAlert Development Plan (Stages 1 through 20)

This document outlines the systematic, incremental development phases of the AutoAlert platform in accordance with the AutoAlert Engineering Rules (`.agents/skills/autoalert-engineering/SKILL.md`).

---

### Stage 1: Foundation and Repository Setup
- Establish directory structure, virtual environment configuration, configuration templates, entry point, and initial smoke tests.

### Stage 2: Video / CCTV Input Layer
- Create `src/video/camera.py` and `src/video/stream.py` supporting local video files, webcams, and RTSP stream abstraction.
- Graceful initialization, error handling, metadata extraction, and resource cleanup.

### Stage 3: OpenCV Frame Processing
- Implement `src/video/frame_processor.py` for frame numbering, timestamp derivation, configurable resizing, frame validation, and lightweight preprocessing hooks.

### Stage 4: Object Detection
- Integrate Ultralytics YOLOv8 detector in `src/detection/detector.py`, `vehicle_detector.py`, and `person_detector.py`.
- Support structured detection outputs with classes of interest: person, car, motorcycle, bus, truck.

### Stage 5: Multi-Object Tracking
- Implement `src/tracking/tracker.py` to maintain track IDs, bounding boxes, velocities, and trajectory history across frames.

### Stage 6: Vehicle Collision Candidate Detection
- Implement `src/events/collision.py` using multi-signal temporal indicators (relative distance change, sudden deceleration/velocity shift, trajectory angle divergence, spatial interaction).
- Strictly emit *candidates*, not verified accidents.

### Stage 7: Prolonged Person Motionlessness
- Implement `src/events/motionless.py` to detect low-displacement tracks over configurable temporal windows.
- Design clean state resets on resumed movement or lost tracks.

### Stage 8: Visual Anomaly Detection
- Implement `src/events/anomaly.py` utilizing HSV color filtering, contour area thresholds, and temporal persistence for prototype hazard detection.

### Stage 9: Event Verification Engine
- Implement `src/events/verifier.py` and `src/core/event.py` managing state transitions (`CANDIDATE` -> `VERIFYING` -> `VERIFIED` -> `REJECTED`/`EXPIRED`).
- Enforce duplicate suppression cooldowns and audit logging of reasoning signals.

### Stage 10: Evidence Recording
- Implement `src/evidence/recorder.py` and `frame_capture.py` to record key incident frames and short pre/post incident video clips from memory ring buffers.

### Stage 11: Number Plate Detection
- Implement `src/license_plate/detector.py` and `preprocessor.py` to crop license plate candidates associated with tracked vehicle IDs.

### Stage 12: OCR and Temporal Aggregation
- Implement `src/license_plate/ocr.py` and `aggregator.py` to run OCR on candidate crops, normalize text, aggregate across multiple timestamps, and compute confidence.

### Stage 13: Incident Object and Package
- Implement `src/core/incident.py` defining standard structured incident models, serialization, and payload generation for backend transport.

### Stage 14: Central FastAPI Backend
- Implement `backend/main.py` with modular API routers (`/incidents`, `/cameras`, `/facilities`), health checks, schema validation, and REST semantics.

### Stage 15: Database Persistence
- Implement `backend/database/` with SQLAlchemy ORM models, SQLite storage, repositories, and transactional operations.

### Stage 16: AutoAlert Command Center Dashboard
- Implement `dashboard/app.py` in Streamlit displaying real-time incident feeds, evidence video/frame playback, plate inspection, and camera status.

### Stage 17: Facility Matching & Simulated Notifications
- Implement nearest-facility matching (Haversine distance calculation) and simulated notification state transitions (`PENDING`, `NOTIFIED`, `ACKNOWLEDGED`, `RESPONDING`).

### Stage 18: Testing and Evaluation
- Build end-to-end integration tests, evaluate detection, tracking, candidate generation, verification, and backend ingestion.
- Output comprehensive evaluation report in `docs/evaluation.md`.

### Stage 19: Edge Device Benchmarking
- Create `scripts/benchmark.py` measuring inference latency, end-to-end FPS, memory, and CPU utilization.
- Output edge requirements analysis in `docs/edge_benchmark.md`.

### Stage 20: Deployment Preparation
- Provide setup instructions, systemd/startup scripts, configuration guidelines, and operational runbook in `docs/deployment.md`.
