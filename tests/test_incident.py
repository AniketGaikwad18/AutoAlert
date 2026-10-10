"""Stage 13 Incident Object and Package Contract Tests."""

import pytest
from pydantic import ValidationError
from src.core.incident import IncidentPackage, LocationModel, EvidencePayload, PlateReadingPayload


def test_valid_incident_package_serialization():
    """Test standard incident package creation and serialization."""
    pkg = IncidentPackage(
        incident_id="INC-2026-0001",
        incident_type="vehicle_collision",
        camera_id="CAM-01",
        timestamp="2026-10-10T12:00:00Z",
        confidence_score=0.88,
        verification_status="verified",
        involved_track_ids=[1, 2],
        reasons=["High deceleration", "Spatial convergence"],
        signals={"distance_px": 35.2},
        location=LocationModel(latitude=18.5204, longitude=73.8567, description="Pune"),
        evidence=EvidencePayload(directory="outputs/incidents/INC-2026-0001", key_frames=["f1.jpg"]),
        plate_readings=[
            PlateReadingPayload(track_id=1, plate_text="MH12AB1234", confidence=0.85, is_readable=True, format_valid=True)
        ]
    )

    data = pkg.to_json_dict()
    assert data["incident_id"] == "INC-2026-0001"
    assert data["location"]["latitude"] == 18.5204
    assert len(data["plate_readings"]) == 1
    assert data["plate_readings"][0]["plate_text"] == "MH12AB1234"


def test_unfabricated_optional_fields_remain_none():
    """Test that absent GPS or plate data remains None without fabrication."""
    pkg = IncidentPackage(
        incident_id="INC-2026-0002",
        incident_type="prolonged_motionlessness",
        camera_id="CAM-02",
        timestamp="2026-10-10T12:05:00Z",
        confidence_score=0.75,
        location=None,  # Not fabricated
        plate_readings=[]
    )

    data = pkg.to_json_dict()
    assert data["location"] is None
    assert data["plate_readings"] == []


def test_invalid_incident_package_validation_failures():
    """Test that missing required fields or out-of-range confidence fail validation."""
    with pytest.raises(ValidationError):
        # Empty incident_id
        IncidentPackage(
            incident_id="",
            incident_type="vehicle_collision",
            camera_id="CAM-01",
            timestamp="2026-10-10T12:00:00Z",
            confidence_score=0.8
        )

    with pytest.raises(ValidationError):
        # Confidence score > 1.0
        IncidentPackage(
            incident_id="INC-01",
            incident_type="vehicle_collision",
            camera_id="CAM-01",
            timestamp="2026-10-10T12:00:00Z",
            confidence_score=1.5
        )
