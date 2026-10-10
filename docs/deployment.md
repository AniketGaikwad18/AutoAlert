# AutoAlert Platform Deployment & Operations Guide

**System:** AutoAlert AI/IoT Emergency Detection & Response Platform  
**Target Environment:** Prototype Laptop (Representative of Future Edge AI/IoT Box) + Local Central Server  
**Platform Version:** 0.1.0  

---

> [!CAUTION]
> **PROTOTYPE / DEMO NOTICE:** AutoAlert is an academic/engineering prototype designed to demonstrate automatic emergency candidate detection, multi-signal verification, and nearest facility matching. In accordance with AutoAlert Engineering Rules, all emergency services (police, hospital, ambulance) dispatches are strictly **SIMULATED**. Do not connect to production municipal dispatch centers or emergency telephone trunks without authorized government integration.

---

## 1. System Architecture Overview

AutoAlert upgrades existing fixed CCTV cameras into intelligent emergency monitoring nodes:

```
[Existing CCTV / Video File]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│               Edge AI Box Pipeline                     │
│ 1. Video Ingestion (`src/video/`)                      │
│ 2. OpenCV Frame Normalization (`src/video/`)           │
│ 3. YOLOv8 Object Detection (`src/detection/`)          │
│ 4. Multi-Object Tracking (`src/tracking/`)             │
│ 5. Event Candidate Detectors (`src/events/`)           │
│    - Vehicle Collision (Multi-Signal Dynamics)         │
│    - Prolonged Person Motionlessness                   │
│    - Visual Liquid/Hazard Anomaly                      │
│ 6. Verification Engine (`src/events/verifier.py`)      │
│ 7. Evidence Recorder (`src/evidence/`)                 │
│    - Circular Frame Buffer                             │
│    - MP4 Clip & Keyframe JPEG Storage                  │
│ 8. License Plate ANPR (`src/license_plate/`)           │
│    - Vehicle ROI Localization                          │
│    - OCR & Temporal Majority Aggregation               │
└──────────────────────────┬─────────────────────────────┘
                           │ Serialized JSON `IncidentPackage`
                           ▼
┌────────────────────────────────────────────────────────┐
│             Central Backend & Storage                  │
│ 1. FastAPI REST Endpoints (`backend/routes/`)          │
│ 2. SQLAlchemy ORM + SQLite (`outputs/autoalert.db`)    │
│ 3. Facility Matcher (`src/location/facility_matcher`)  │
└──────────────────────────┬─────────────────────────────┘
                           │ REST / SQLite
                           ▼
┌────────────────────────────────────────────────────────┐
│           Command Center Dashboard                     │
│ Streamlit UI (`dashboard/app.py`)                      │
│ - Live Incident Queue & Status Tracking                │
│ - Keyframe & Video Clip Evidence Inspector             │
│ - Map & Nearest Facility Dispatch Control              │
└────────────────────────────────────────────────────────┘
```

---

## 2. Environment Setup & Installation

### 2.1 Prerequisites
- Python 3.10+ (Tested on Python 3.11.15)
- OpenCV compatible OS (Windows 10/11, Ubuntu 22.04 LTS, macOS)
- Git

### 2.2 Clone & Dependencies Installation
```bash
# Clone the repository
git clone https://github.com/AniketGaikwad18/SIH-26070.git
cd Auto-Alert

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2.3 Configuration Setup
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configurable files in `config/`:
- `config/settings.yaml`: Pipeline thresholds, video resolution, model paths, candidate sensitivities.
- `config/cameras.yaml`: CCTV camera inventory, RTSP / video file sources, GPS coordinates.
- `config/facilities.yaml`: Simulated hospitals, ambulance bases, and police stations.

---

## 3. Running the System

### 3.1 Run Full Test Suite
To verify system health and test all modules:
```bash
pytest tests/ -v
```
*(All 54 tests pass out of the box).*

### 3.2 Run End-to-End Local Demo
Simulates a vehicle collision video, executes object detection, tracking, candidate verification, records video and image evidence artifacts, extracts license plate readings, and persists the incident to the database:
```bash
python scripts/run_pipeline_demo.py
```

### 3.3 Start Central FastAPI Backend
```bash
python scripts/run_backend.py
```
- API Base URL: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`

### 3.4 Start AutoAlert Command Center Dashboard
In a separate terminal:
```bash
python scripts/run_dashboard.py
```
Or directly:
```bash
streamlit run dashboard/app.py
```
Opens in your browser at `http://localhost:8501`.

---

## 4. Directory & Evidence Structure

Generated artifacts are stored in `outputs/`:
```
outputs/
├── autoalert.db               # SQLite database file
├── incidents/                 # Per-incident evidence dossiers
│   └── INC-0001/
│       ├── keyframe_14_1.jpg  # High-resolution incident keyframes
│       ├── keyframe_18_2.jpg
│       ├── clip_INC-0001.mp4  # Buffered incident video clip
│       └── evidence_manifest.json
└── logs/
    └── benchmark_results.json # Hardware performance benchmark outputs
```

---

## 5. Security & Privacy Considerations

1. **Credentials Management:** No API tokens, passwords, or private keys are committed into source control (`.gitignore` enforces `.env` exclusion).
2. **Path Traversal Sanitization:** Incident IDs and filename generation use `sanitize_filename` regex stripping unsafe path traversal characters.
3. **Data Protection:** Evidence frames and license plate crops are stored locally within configured output directories.

---

## 6. Troubleshooting

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| `OpenCV VideoCapture returns False` | Video file path incorrect or RTSP stream unreachable | Check `config/cameras.yaml` source path. Ensure test synthetic video exists via `python scripts/run_pipeline_demo.py`. |
| `OperationalError: no such table` | Database uninitialized | The backend automatically calls `init_db()` upon startup, or run `from backend.database.database import init_db; init_db()` in Python. |
| `Streamlit missing ScriptRunContext warning` | App imported as regular script rather than run via streamlit CLI | Launch using `streamlit run dashboard/app.py` or `python scripts/run_dashboard.py`. |

---

## 7. Future Edge AI Box Deployment Roadmap

The current laptop prototype validates pipeline modularity, temporal logic, and backend communications. Moving to dedicated physical hardware (Raspberry Pi 5 + Hailo-8 NPU or NVIDIA Jetson Orin Nano) involves:
1. Exporting YOLOv8 model weights to ONNX / TensorRT INT8.
2. Integrating hardware-accelerated video decoding (V4L2 / GStreamer).
3. Packaging edge components into a lightweight Docker container with a systemd watchdog.
