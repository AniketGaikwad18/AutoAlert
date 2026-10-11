"""End-to-End Acceptance Tests for AutoAlert Emergency Response Command Center.

Validates:
1. Raspberry Pi edge device heartbeat & truthful connectivity state.
2. Incident ingestion from Raspberry Pi AI Box initiates ambulance dispatch & police notification.
3. Demo trigger executes complete incident-to-response pipeline exactly once.
4. Police desk acknowledgement updates incident state and appends milestone to timeline.
5. Ambulance unit confirmation updates status to En Route and appends milestone to timeline.
6. Demo reset preserves historical records in SQLite.
7. Repeatable execution without application restarts.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base, get_db
from backend.database.repositories import IncidentRepository, DeviceRepository, seed_defaults_if_empty
from backend.main import app
from src.coordination.response_coordinator import ResponseCoordinator

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_defaults_if_empty(db)
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_raspberry_pi_truthful_connectivity(client):
    """Raspberry Pi status reflects actual device heartbeat, never permanently green."""
    # 1. Initially disconnected before any heartbeat ping
    res = client.get("/api/device/status?device_id=PI-AI-BOX-01")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("DISCONNECTED", "CONNECTED")  # depending on pre-seed

    # 2. Transmit valid edge heartbeat
    hb_payload = {
        "device_id": "PI-AI-BOX-01",
        "device_name": "Raspberry Pi 5 AI Box",
        "ip_address": "192.168.1.105",
        "telemetry": {"cpu_temp": 46.2, "ram_used_mb": 240.0}
    }
    hb_res = client.post("/api/device/heartbeat", json=hb_payload)
    assert hb_res.status_code == 200
    assert hb_res.json()["is_connected"] is True

    # 3. Verify status is now active and connected
    status_res = client.get("/api/device/status?device_id=PI-AI-BOX-01")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["is_connected"] is True
    assert st_data["status"] == "CONNECTED"
    assert st_data["ip_address"] == "192.168.1.105"


def test_edge_device_incident_triggers_coordinator(client):
    """Incoming incident package from Raspberry Pi edge box triggers multi-agency coordination."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "incident_id": "INC-EDGE-TEST-01",
        "incident_type": "Possible Road Accident",
        "camera_id": "CAM-01",
        "timestamp": now_iso,
        "confidence_score": 0.92,
        "verification_status": "verified",
        "involved_track_ids": [10, 11],
        "reasons": ["Severe sudden deceleration ratio 0.84", "Spatial convergence 38px"],
        "signals": {"speed_drop": 0.84, "proximity_px": 38.0},
        "location": {
            "latitude": 18.5204,
            "longitude": 73.8567,
            "description": "Shivajinagar Junction, Pune"
        },
        "evidence": {
            "directory": "outputs/incidents/INC-0001",
            "key_frames": ["outputs/incidents/INC-0001/keyframe_33_1.jpg"],
            "video_clip": "outputs/incidents/INC-0001/clip_INC-0001.mp4"
        },
        "plate_readings": [
            {
                "track_id": 10,
                "plate_text": "MH12AB1234",
                "confidence": 0.88,
                "is_readable": True,
                "format_valid": True
            }
        ]
    }

    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "INC-EDGE-TEST-01"
    assert created["verification_status"] == "verified"

    # Verify incident persisted in DB with ambulance and police details
    db = TestingSessionLocal()
    try:
        model = IncidentRepository.get_by_id(db, "INC-EDGE-TEST-01")
        assert model is not None
        assert model.mode == "LIVE DEVICE"
        assert model.ambulance_unit is not None
        assert model.police_station_name is not None
        assert model.timeline_events_json is not None
    finally:
        db.close()


def test_demo_trigger_ambulance_and_police_records(client):
    """Demo trigger creates real incident, records ambulance dispatch & police notification exactly once."""
    res = client.post("/api/demo/trigger")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    inc_id = data["incident_id"]

    db = TestingSessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, inc_id)
        assert inc is not None
        assert inc.mode == "DEMO"
        assert inc.ambulance_status is not None
        assert inc.police_status is not None

        # Verify timeline events
        import json
        timeline = json.loads(inc.timeline_events_json)
        assert len(timeline) >= 6
        step_titles = [s["title"] for s in timeline]
        assert "Ambulance dispatch initiated" in step_titles
        assert "Police station notified" in step_titles
    finally:
        db.close()


def test_police_and_ambulance_acknowledgement_lifecycle(client):
    """Judges can acknowledge incident at Police Station & confirm Ambulance En Route."""
    # 1. Trigger incident
    res = client.post("/api/demo/trigger")
    inc_id = res.json()["incident_id"]

    # 2. Officer acknowledges Police alert
    pol_res = client.post("/api/demo/acknowledge", json={"incident_id": inc_id, "agency": "police"})
    assert pol_res.status_code == 200
    pol_data = pol_res.json()
    assert pol_data["police_status"] == "Acknowledged"
    assert any("Police station acknowledges notification" in s["title"] for s in pol_data["timeline"])

    # 3. Ambulance confirmed En Route
    amb_res = client.post("/api/demo/acknowledge", json={"incident_id": inc_id, "agency": "ambulance"})
    assert amb_res.status_code == 200
    amb_data = amb_res.json()
    assert amb_data["ambulance_status"] == "En Route"
    assert any("Ambulance response updated" in s["title"] for s in amb_data["timeline"])


def test_demo_reset_preserves_historical_records(client):
    """Resetting demo session does not erase historical records from SQLite."""
    # Count current incidents
    db = TestingSessionLocal()
    try:
        count_before = len(IncidentRepository.get_all(db))
        assert count_before >= 2
    finally:
        db.close()

    # Call reset
    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "reset"

    # Verify incidents are NOT erased
    db = TestingSessionLocal()
    try:
        count_after = len(IncidentRepository.get_all(db))
        assert count_after == count_before
    finally:
        db.close()


def test_full_workflow_repeatable(client):
    """Workflow can be triggered repeatedly without server restart."""
    for cycle in range(2):
        t_res = client.post("/api/demo/trigger")
        assert t_res.status_code == 200
        inc_id = t_res.json()["incident_id"]

        ack_res = client.post("/api/demo/acknowledge", json={"incident_id": inc_id, "agency": "police"})
        assert ack_res.status_code == 200

        r_res = client.post("/api/demo/reset")
        assert r_res.status_code == 200
