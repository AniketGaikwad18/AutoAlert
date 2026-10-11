"""
Tests for Stage 15 SQLite database persistence layer.

Verifies table creation, CRUD operations, JSON serialization/deserialization,
and default data seeding using an in-memory SQLite database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.database import Base
from backend.database.models import IncidentModel, CameraModel, FacilityModel
from backend.database.repositories import SQLAlchemyRepository
from backend.schemas.incident import (
    IncidentPackageCreateSchema,
    LocationSchema,
    PlateReadingSchema,
)
from backend.schemas.camera import CameraSchema
from backend.schemas.facility import FacilitySchema


@pytest.fixture
def memory_db_repo():
    """Fixture providing a clean in-memory SQLite repository for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    repo = SQLAlchemyRepository(session_factory=TestingSessionLocal)
    yield repo
    Base.metadata.drop_all(bind=engine)


def test_seed_default_data(memory_db_repo):
    """Verify that default camera and facility are seeded on initialization."""
    cameras = memory_db_repo.list_cameras()
    facilities = memory_db_repo.list_facilities()

    assert len(cameras) >= 1
    assert any(c.camera_id == "CAM-MAIN-01" for c in cameras)

    assert len(facilities) >= 1
    assert any(f.facility_id == "FAC-HOSPITAL-01" for f in facilities)
    assert facilities[0].is_simulated is True


def test_add_and_get_incident(memory_db_repo):
    """Verify persisting and retrieving an incident package."""
    incident_data = IncidentPackageCreateSchema(
        incident_id="INC-2026-TEST01",
        incident_type="collision",
        camera_id="CAM-01",
        timestamp=1700000000.0,
        verification_status="verified",
        confidence_score=0.92,
        created_at="2026-09-17T12:00:00Z",
        involved_track_ids=[101, 102],
        evidence_frames=["/tmp/evidence1.jpg", "/tmp/evidence2.jpg"],
        evidence_video_path="/tmp/clip.mp4",
        location=LocationSchema(latitude=18.52, longitude=73.85, name="Main Gate"),
        plate_readings=[
            PlateReadingSchema(
                track_id=101,
                plate_number="MH12AB1234",
                confidence=0.88,
                format_validated=True,
                status="verified_reading",
            )
        ],
        reason_metadata={"trigger": "high_overlap_velocity_drop"},
    )

    persisted = memory_db_repo.add_incident(incident_data)
    assert persisted.incident_id == "INC-2026-TEST01"
    assert persisted.confidence_score == 0.92

    fetched = memory_db_repo.get_incident("INC-2026-TEST01")
    assert fetched is not None
    assert fetched.incident_id == "INC-2026-TEST01"
    assert fetched.incident_type == "collision"
    assert fetched.involved_track_ids == [101, 102]
    assert fetched.location is not None
    assert fetched.location.name == "Main Gate"
    assert len(fetched.plate_readings) == 1
    assert fetched.plate_readings[0].plate_number == "MH12AB1234"


def test_get_nonexistent_incident(memory_db_repo):
    """Verify get_incident returns None when incident is missing."""
    res = memory_db_repo.get_incident("INC-NONEXISTENT")
    assert res is None


def test_list_incidents_filtering(memory_db_repo):
    """Verify filtering incident listings by type."""
    inc1 = IncidentPackageCreateSchema(
        incident_id="INC-FILTER-01",
        incident_type="collision",
        camera_id="CAM-01",
        timestamp=1700000001.0,
        verification_status="verified",
        confidence_score=0.9,
        created_at="2026-09-17T12:01:00Z",
        involved_track_ids=[1],
        evidence_frames=[],
    )
    inc2 = IncidentPackageCreateSchema(
        incident_id="INC-FILTER-02",
        incident_type="prolonged_motionlessness",
        camera_id="CAM-01",
        timestamp=1700000002.0,
        verification_status="verified",
        confidence_score=0.85,
        created_at="2026-09-17T12:02:00Z",
        involved_track_ids=[2],
        evidence_frames=[],
    )

    memory_db_repo.add_incident(inc1)
    memory_db_repo.add_incident(inc2)

    collisions = memory_db_repo.list_incidents(incident_type="collision")
    assert len(collisions) == 1
    assert collisions[0].incident_id == "INC-FILTER-01"

    motionless = memory_db_repo.list_incidents(incident_type="prolonged_motionlessness")
    assert len(motionless) == 1
    assert motionless[0].incident_id == "INC-FILTER-02"

    all_incidents = memory_db_repo.list_incidents()
    assert len(all_incidents) == 2


def test_camera_crud_operations(memory_db_repo):
    """Verify creating, listing, retrieving, and updating camera status."""
    new_cam = CameraSchema(
        camera_id="CAM-DB-02",
        name="South Exit Camera",
        location="South Gate",
        stream_url="rtsp://localhost:8554/stream2",
        status="active",
        zone_id="ZONE-SOUTH",
    )

    memory_db_repo.add_camera(new_cam)

    fetched = memory_db_repo.get_camera("CAM-DB-02")
    assert fetched is not None
    assert fetched.name == "South Exit Camera"

    updated = memory_db_repo.update_camera_status("CAM-DB-02", "maintenance")
    assert updated is not None
    assert updated.status == "maintenance"

    assert memory_db_repo.get_camera("CAM-DB-02").status == "maintenance"


def test_facility_crud_operations(memory_db_repo):
    """Verify adding and listing simulated emergency response facilities."""
    new_facility = FacilitySchema(
        facility_id="FAC-POLICE-01",
        name="District Central Police Station (Simulated)",
        type="police",
        phone_contact="555-0100 (SIMULATED)",
        latitude=18.53,
        longitude=73.86,
        available=True,
        is_simulated=True,
    )

    memory_db_repo.add_facility(new_facility)

    facilities = memory_db_repo.list_facilities()
    assert any(f.facility_id == "FAC-POLICE-01" for f in facilities)
