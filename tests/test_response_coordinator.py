"""Tests for Response Coordinator, Adapters, Device Heartbeat, and Demo Workflows."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base, get_db
from backend.database.repositories import seed_defaults_if_empty
from backend.main import app
from src.coordination.response_coordinator import ResponseCoordinator, AmbulanceDispatchAdapter, PoliceNotificationAdapter

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


def test_ambulance_dispatch_lifecycle():
    """Test ambulance dispatch state transitions."""
    adapter = AmbulanceDispatchAdapter(simulation_mode=True)
    d = adapter.initiate_dispatch(incident_id="INC-001", unit_id="Unit-4")
    assert d["status"] == "Dispatch Initiated"
    assert d["unit_id"] == "Unit-4"
    assert d["is_simulated"] is True

    d_ack = adapter.acknowledge_dispatch(d)
    assert d_ack["status"] == "Acknowledged"

    d_route = adapter.set_en_route(d_ack)
    assert d_route["status"] == "En Route"


def test_police_notification_lifecycle():
    """Test police notification delivery and acknowledgement."""
    adapter = PoliceNotificationAdapter(simulation_mode=True)
    n = adapter.send_incident_dossier(incident_id="INC-002", station_name="Shivajinagar Police")
    assert n["status"] == "Delivered"
    assert n["station_name"] == "Shivajinagar Police"

    n_ack = adapter.record_acknowledgement(n)
    assert n_ack["status"] == "Acknowledged"


def test_response_coordinator_8_step_timeline():
    """Test complete 8-step chronological milestone generation."""
    coordinator = ResponseCoordinator(simulation_mode=True)
    result = coordinator.orchestrate_response(
        incident_id="INC-003",
        camera_id="CAM-01",
        location_desc="Shivajinagar Junction",
        initial_timestamp="2026-10-10T12:00:00Z",
        is_demo=True
    )

    assert result["incident_id"] == "INC-003"
    assert result["ambulance"]["status"] == "En Route"
    assert result["police"]["status"] == "Acknowledged"

    timeline = result["timeline"]
    assert len(timeline) == 8
    expected_titles = [
        "CCTV event received",
        "Incident detected by AI Box",
        "Incident verification completed",
        "Incident received by central coordination system",
        "Ambulance dispatch initiated",
        "Police station notified",
        "Response acknowledgement received",
        "Ambulance response status updated"
    ]
    for idx, expected in enumerate(expected_titles):
        assert timeline[idx]["step"] == idx + 1
        assert timeline[idx]["title"] == expected
        assert timeline[idx]["status"] in ("COMPLETED", "EN_ROUTE")


def test_device_heartbeat_and_status_endpoints(client):
    """Test Raspberry Pi AI Box heartbeat and connection status API."""
    # 1. Check initial status before heartbeat
    res = client.get("/api/device/status?device_id=PI-AI-BOX-01")
    assert res.status_code == 200

    # 2. Transmit heartbeat
    hb_payload = {
        "device_id": "PI-AI-BOX-01",
        "device_name": "Raspberry Pi 5 AI Box",
        "ip_address": "192.168.1.105",
        "telemetry": {"cpu_temp": 48.5, "ram_mb": 250}
    }
    hb_res = client.post("/api/device/heartbeat", json=hb_payload)
    assert hb_res.status_code == 200
    assert hb_res.json()["is_connected"] is True

    # 3. Check status is now CONNECTED
    status_res = client.get("/api/device/status?device_id=PI-AI-BOX-01")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["is_connected"] is True
    assert data["status"] == "CONNECTED"


def test_demo_trigger_endpoint(client):
    """Test demo trigger executes complete incident-to-response orchestration."""
    res = client.post("/api/demo/trigger")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["incident_id"].startswith("INC-DEMO-")
    assert data["ambulance_status"] == "En Route"
    assert data["police_status"] == "Acknowledged"
    assert len(data["timeline"]) == 8

    # Reset endpoint
    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "reset"
