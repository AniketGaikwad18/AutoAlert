# AutoAlert: AI/IoT Emergency Detection Platform

AutoAlert is an edge-native AI/IoT emergency detection and response platform designed to upgrade existing CCTV cameras rather than replace them.

## Core Flow
```
Existing CCTV -> Video Processing -> Object Detection -> Tracking ->
Event Candidate Detection -> Verification Engine -> Evidence Recording ->
Incident Package -> Central FastAPI Backend -> Simulated Facility Matching ->
AutoAlert Command Center Dashboard
```

## Target Event Capabilities
1. **Vehicle Collision Candidate Detection**: Multi-signal temporal tracking, relative motion, velocity divergence, spatial persistence.
2. **Prolonged Person Motionlessness**: Temporal window tracking to identify possible emergencies without asserting medical diagnosis.
3. **Visual Anomaly Detection**: Color and contour segmentation with temporal persistence for liquid/hazard anomalies.
4. **Number Plate OCR & Aggregation**: Vehicle association, frame crop preprocessing, OCR extraction, confidence scoring and temporal aggregation.

## System Components
- **Edge AI Box Pipeline** (`src/`): Video ingestion, OpenCV processing, YOLOv8 detection, multi-object tracking, event candidate generation, verification engine, evidence recording, ANPR.
- **Central Backend** (`backend/`): FastAPI REST API, SQLite database with SQLAlchemy ORM, incident package ingestion, facility matching service.
- **Command Center Dashboard** (`dashboard/`): Streamlit real-time interactive incident review, camera management, evidence playback, simulated EMS dispatch tracking.

## Development & Usage
See `docs/development_plan.md` for the 20-stage development roadmap and `docs/deployment.md` for operational setup instructions.
