# AutoAlert — Engineering Skills & Architectural Reference

## 1. Project Overview & Vision

**Project Name:** AutoAlert  
**Project Title:** AutoAlert — Autonomous AI Teammate for Merchant Emergency Response  
**Track:** Autonomous AI Teammates (Paytm Build for India AI Hackathon)  
**Tagline:** *Detect. Decide. Coordinate. Respond.*

AutoAlert is an AI-powered emergency-response teammate that adds intelligence to **EXISTING CCTV infrastructure**.  
It is **NOT** a CCTV replacement.

```
EXISTING CCTV
      ↓
AUTOALERT AI TEAMMATE
      ↓
OBSERVE
      ↓
UNDERSTAND
      ↓
VERIFY
      ↓
LOCATE
      ↓
COORDINATE
      ↓
REPORT
      ↓
HUMAN RESPONSE
```

---

## 2. Technical Truth & System Honesty

* **Collision / Accident Detection:** Pretrained object detection (YOLOv8) + multi-object tracking (Centroid / ByteTrack) + temporal physics-heuristic trajectory analysis & multi-frame confirmation buffer.
* **No Unsubstantiated Claims:** The prototype does **NOT** claim a custom deep-learning model trained on labeled accidents. It is explicitly described as pretrained object detection with temporal event logic and verification.
* **Simulated Emergency Dispatch:** Notifications to ambulances, police stations, and hospitals are explicitly **SIMULATED** prototype workflows with structured timeline event logs.
* **No Hallucinated Plates:** OCR strictly extracts readable license plates and reports "Number plate unreadable" when confidence is below threshold.

---

## 3. Modular Architecture

```
Existing CCTV / Uploaded Video
        ↓
Video Processing (`src/video/`)
        ↓
YOLO Detection (`src/detection/`)
        ↓
Object Tracking (`src/tracking/`)
        ↓
Event Engine (`src/events/`)
        ├── Collision (`collision.py`)
        ├── Motionlessness (`motionless.py`)
        └── Visual Anomaly (`anomaly.py`)
        ↓
Temporal Verification (`src/events/verifier.py`)
        ↓
Incident Engine (`src/core/incident.py`)
        ↓
Evidence Generation (`src/evidence/recorder.py`, `incident_report.py`)
        ↓
Location Service (`src/location/camera_registry.py`, `distance.py`)
        ↓
Facility Matching (`src/dispatch/matching.py`)
        ↓
Routing Service (`src/dispatch/routing.py`)
        ↓
Notification Service (`src/dispatch/notification.py`)
        ↓
FastAPI Backend (`backend/`)
        ↓
Streamlit / Web Command Dashboard (`dashboard/`)
```

---

## 4. Technology Choices

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn | High-performance async REST API, auto-generated OpenAPI docs, strict type safety. |
| **Computer Vision** | OpenCV, Ultralytics YOLOv8, NumPy | Industry standard object detection, image processing, video encoding, CLAHE plate enhancement. |
| **Tracking** | Centroid & Multi-Object Tracking | Bounding box trajectory history, velocity vectors, closing speed, deceleration calculation. |
| **OCR** | Tesseract / EasyOCR / Synthetic Fallback | Flexible abstraction for vehicle registration identification with confidence scoring. |
| **Mapping & Routing** | OpenStreetMap & OSRM / Haversine | Open-source geographic calculations and emergency response path generation without paid Google API keys. |
| **Database** | SQLite + Repository Pattern | Zero-setup local persistence, structured schema for seamless migration to PostgreSQL. |
| **Dashboard** | Streamlit + Custom Semantic CSS | Live incident monitor, video player, interactive step-by-step incident verification workflow. |

---

## 5. Development & Testing Rules

1. **Deterministic & Testable:** All event heuristics, distance calculations, and verification thresholds must have unit tests.
2. **Graceful Fallbacks:** Video processing, YOLO loading, OCR engines, and external OSRM routing must provide clean, non-crashing local mock/synthetic fallbacks if weights or network are unavailable.
3. **No Fake Signals:** Never display fabricated accuracy metrics or mock data as live emergency dispatch.
4. **Testing Suite:** Run `pytest` to execute all unit, integration, and end-to-end test suites.

---

## 6. Implementation Status (All 128 Pytest Tests Passing)

- [x] Camera Registry (`src/location/camera_registry.py`, `backend/routes/cameras.py`)
- [x] CCTV Video Ingestion & Frame Processing (`src/video/frame_processor.py`)
- [x] Vehicle & Person Detectors (`src/detection/`)
- [x] Multi-Object Trajectory Tracking (`src/tracking/tracker.py`)
- [x] Vehicle Collision Event Engine (`src/events/collision.py`)
- [x] Person Prolonged Motionlessness Engine (`src/events/motionless.py`)
- [x] Visual Anomaly Detection (`src/events/anomaly.py`)
- [x] Multi-Frame Temporal Verification (`src/events/verifier.py`)
- [x] Incident Object & Package Generation (`src/core/incident.py`)
- [x] Evidence Recording & Frame Capture (`src/evidence/recorder.py`)
- [x] Number Plate Cropping & OCR (`src/license_plate/`)
- [x] Emergency Facility Matching & Haversine Distance (`src/dispatch/matching.py`, `backend/routes/facilities.py`)
- [x] Response Route Generation (`src/dispatch/routing.py`)
- [x] Simulated Notification Dispatch Engine (`src/dispatch/notification.py`, `backend/routes/notifications.py`)
- [x] Central FastAPI Backend (`backend/main.py`)
- [x] Command Center Dashboard (`dashboard/app.py`)
- [x] Full Automated Test Suite (`tests/`, 128 tests passing)
