import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base, get_db
from backend.database.repositories import seed_defaults_if_empty
from backend.main import app

# In-memory SQLite database with StaticPool for isolated fast testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def client():
    """Create test client with fresh isolated in-memory database."""
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


def test_health_check(client):
    """Test /api/health endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["simulation_mode"] is True


def test_cameras_seeded_and_retrievable(client):
    """Test retrieving seeded cameras."""
    res = client.get("/api/cameras")
    assert res.status_code == 200
    cameras = res.json()
    assert len(cameras) >= 1
    assert any(c["id"] == "CAM-01" for c in cameras)


def test_post_and_retrieve_incident(client):
    """Test receiving validated incident package, retrieving it, and updating status."""
    payload = {
        "incident_id": "INC-TEST-999",
        "incident_type": "vehicle_collision",
        "camera_id": "CAM-01",
        "timestamp": "2026-10-10T12:30:00Z",
        "confidence_score": 0.89,
        "verification_status": "verified",
        "involved_track_ids": [1, 2],
        "reasons": ["Sudden deceleration", "Trajectory deflection"],
        "signals": {"speed_drop": 0.75},
        "location": {"latitude": 18.5204, "longitude": 73.8567, "description": "Pune"},
        "evidence": {"directory": "outputs/incidents/INC-TEST-999", "key_frames": ["frame1.jpg"]},
        "plate_readings": [
            {
                "track_id": 1,
                "plate_text": "MH12AB1234",
                "confidence": 0.85,
                "is_readable": True,
                "format_valid": True,
            }
        ]
    }

    # 1. POST incident
    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "INC-TEST-999"
    assert created["notification_status"] == "pending"

    # 2. GET incident by ID
    res = client.get("/api/incidents/INC-TEST-999")
    assert res.status_code == 200
    retrieved = res.json()
    assert retrieved["id"] == "INC-TEST-999"
    assert len(retrieved["plate_readings"]) == 1
    assert retrieved["plate_readings"][0]["plate_text"] == "MH12AB1234"

    # 3. PATCH status to 'notified'
    res = client.patch("/api/incidents/INC-TEST-999/status", json={"notification_status": "notified"})
    assert res.status_code == 200
    assert res.json()["notification_status"] == "notified"

    # 4. PATCH invalid status returns 422
    res = client.patch("/api/incidents/INC-TEST-999/status", json={"notification_status": "invalid_status"})
    assert res.status_code == 422


def test_facilities_and_nearest_matching(client):
    """Test retrieving facilities and matching nearest facilities via coordinates."""
    # List all facilities
    res = client.get("/api/facilities")
    assert res.status_code == 200
    facs = res.json()
    assert len(facs) >= 1

    # Match nearest to Shivajinagar (18.5204, 73.8567)
    res = client.get("/api/facilities/nearest?latitude=18.5204&longitude=73.8567")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    matched = data["matched_facilities"]
    assert "hospital" in matched
    assert "ambulance" in matched
    assert "police" in matched
    assert len(matched["hospital"]) >= 1
    assert "distance_km" in matched["hospital"][0]
    assert matched["hospital"][0]["distance_km"] < 10.0  # Within Pune area
