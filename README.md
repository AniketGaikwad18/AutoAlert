# AutoAlert: AI/IoT Emergency Detection & Response Platform

AutoAlert is an edge-native AI/IoT emergency detection and response platform designed to upgrade existing CCTV cameras into intelligent emergency detection nodes rather than replacing them.

The system analyzes real-time CCTV feeds at the edge, verifies accidents and hazardous conditions using multi-signal kinematics, resolves precise incident locations, coordinates dispatch routes for ambulances and hospitals, and transmits automated notifications to police headquarters with an authoritative 5-stage lifecycle.

---

## 💡 About the Project & Motivation

The inspiration for AutoAlert originated from a real-life emergency where an ambulance carrying a critical patient was stranded in heavy gridlock. Watching that situation highlighted a critical gap: existing CCTV cameras passively record accidents after the fact, but rarely trigger proactive, instant emergency response.

Instead of replacing the millions of CCTV cameras already deployed across cities, AutoAlert connects a compact, weatherproof AI Box alongside existing CCTV cameras. The system continuously monitors the stream, verifies real accidents to prevent false alarms, and dispatches coordinated alerts to emergency services before bystanders even dial emergency services.

---

## 🔄 End-to-End System Workflow

```
Existing CCTV Stream
       │
       ▼
Edge AI Processing (YOLOv8 Detection & Multi-Object Tracking)
       │
       ▼
Kinematic Verification Engine (Velocity divergence, spatial overlap, persistence)
       │
       ▼
Incident Package Packaging & Cryptographic Evidence Capture
       │
       ▼
Central FastAPI Backend (Persistence & Dispatch Corridor Calculation)
       │
       ▼
Emergency Routing Engine (OSRM Leg A Ambulance Approach + Leg B Hospital Transit)
       │
       ▼
Police Coordination & Notification Lifecycle (5-Stage State Machine)
       │
       ▼
AutoAlert Command Center Dashboard (Real-Time Interactive Review)
```

---

## 🎯 Target Event Capabilities

1. **Vehicle Collision Candidate Detection**: Multi-signal kinematic analysis evaluating speed drops, spatial convergence, trajectory deflection, and multi-frame temporal persistence.
2. **Prolonged Person Motionlessness**: Temporal window tracking detecting individuals lying motionless without asserting medical diagnosis.
3. **Visual Hazard / Anomaly Detection**: Color and contour segmentation tracking anomalies with temporal persistence.
4. **Number Plate OCR & ANPR**: Vehicle association, perspective crop preprocessing, EasyOCR reading, confidence scoring, and temporal aggregation.
5. **Emergency Corridor & Route Optimization**: OpenStreetMap and OSRM integration calculating real-time dual-leg emergency corridors (Ambulance to Incident, Incident to Hospital) with green-corridor signal mapping.
6. **State-Driven Notification Lifecycle**: 5-stage lifecycle state machine (`Prepared` → `Sent` → `Delivered` → `Acknowledged` → `Response Initiated`) with simulation safety badges.

---

## 🏗️ Repository Architecture

```
AutoAlert/
├── backend/                  # Central FastAPI Backend & Database
│   ├── database/             # SQLite database, SQLAlchemy models & repositories
│   ├── routes/               # API endpoints (incidents, notifications, cameras, facilities)
│   └── schemas/              # Pydantic validation schemas
├── config/                   # System, camera, and facility configurations
├── dashboard/                # Real-time Streamlit Command Center Dashboard
│   ├── app.py                # Main command center application
│   └── components/           # UI components, filters, and interactive Leaflet map
├── data/                     # Demo videos, sample frames, and reference data
├── docs/                     # Architecture, security, API specs, and development guides
├── src/                      # Edge AI Processing & Coordination Core
│   ├── coordination/         # Response coordinator
│   ├── core/                 # Incident schemas and event models
│   ├── detection/            # YOLOv8 object detector
│   ├── dispatch/             # Routing, notification service, and corridor analysis
│   ├── events/               # Collision, anomaly, and motionlessness verifiers
│   ├── evidence/             # Frame capture and incident recording
│   ├── license_plate/        # ANPR detector and OCR pipeline
│   ├── location/             # Camera and emergency facility registries
│   └── tracking/             # Multi-object ByteTrack tracker
└── tests/                    # End-to-end test suite (Pytest)
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/AniketGaikwad18/AutoAlert.git
cd AutoAlert

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Backend API
```bash
python scripts/start_backend.py
# API documentation available at http://localhost:8000/docs
```

### 4. Launch the Command Center Dashboard
```bash
streamlit run dashboard/app.py
# Command Center available at http://localhost:8501
```

### 5. Run Automated Tests
```bash
pytest tests/
```

---

## 📜 License & Acknowledgements

Created by **Aniket Gaikwad**. Built with FastAPI, PyTorch, Ultralytics YOLOv8, Streamlit, Leaflet, and OpenStreetMap.


These is the best idea of me till date.
