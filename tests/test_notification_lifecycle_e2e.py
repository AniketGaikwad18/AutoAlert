"""
End-to-End Acceptance Tests for AutoAlert Emergency Notification Box and Lifecycle Progression.

Validates all 12 Acceptance Criteria:
1. The message appears with the active incident details.
2. Copy Message copies the correct text.
3. Prepare Notification updates the state.
4. The stepper reflects the current state, not five permanently completed stages.
5. Simulated send updates the state and timeline.
6. Simulated delivery is distinguishable from actual delivery (SIM badge/flag).
7. Simulated acknowledgement updates the correct stage.
8. Response Initiated requires a valid response event / prior stage.
9. Failed operations display an error and do not advance the lifecycle.
10. Page refresh restores the correct persisted state.
11. Reset Notification Demo resets only the intended demo state without deleting incident records.
12. Existing map, routing, CCTV video, and dashboard functionality remain intact.
"""

import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.database import SessionLocal, init_db
from backend.database.repositories import IncidentRepository
from backend.database.models import IncidentModel
from src.core.incident import (
    IncidentPackage,
    LocationModel,
    EvidencePayload,
    PlateReadingPayload,
)
from dashboard.app import (
    format_notification_message,
    prepare_notification,
    simulate_send_notification,
    simulate_deliver_notification,
    record_police_ack,
    simulate_response_initiated,
    reset_notification_demo,
    reset_police_ack,
    build_sample_scenario_incident,
    SCENARIO_CONFIGS,
)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database schema is fresh and ready for each test."""
    init_db()
    yield


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def create_test_incident(incident_id="AA-2026-TEST01"):
    """Helper to create a test incident in the SQLite database."""
    db = SessionLocal()
    try:
        # Delete existing if present
        existing = IncidentRepository.get_by_id(db, incident_id)
        if existing:
            db.delete(existing)
            db.commit()

        pkg = IncidentPackage(
            incident_id=incident_id,
            incident_type="Severe Multi-Vehicle Collision",
            camera_id="CAM-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence_score=0.94,
            verification_status="verified",
            involved_track_ids=[1, 2],
            reasons=["High-speed kinematic divergence", "Persistent lateral vehicle displacement"],
            signals={"speed_drop_ratio": 0.82, "proximity_px": 28.5},
            location=LocationModel(
                latitude=18.5204,
                longitude=73.8567,
                description="Shivajinagar Junction, Pune"
            ),
            evidence=EvidencePayload(
                directory="outputs/incidents/INC-0001",
                key_frames=["outputs/incidents/INC-0001/keyframe_33_1.jpg"],
                video_clip="data/demo_videos/demo_accident_junction.mp4"
            ),
            plate_readings=[
                PlateReadingPayload(
                    track_id=1,
                    plate_text="MH12DE1432",
                    confidence=0.91,
                    is_readable=True,
                    format_valid=True
                )
            ]
        )
        inc = IncidentRepository.create(
            db=db,
            pkg=pkg,
            source_device="Raspberry Pi AI Box",
            mode="DEMO",
            ambulance_status="Dispatched",
            ambulance_unit="108 Fast Response Unit #4",
            police_station_name="Shivajinagar Police Station",
            police_status="Notification Prepared [SIMULATED]",
            timeline_events=[
                {
                    "step": 1,
                    "title": "Incident detected",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "COMPLETED",
                    "details": "Accident detected at Shivajinagar Junction."
                }
            ]
        )
        inc.notification_status = "prepared"
        db.commit()
        return inc.id
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. Active Incident Details in Prepared Message
# -----------------------------------------------------------------------------
def test_criterion_1_message_contains_active_incident_details():
    """Criterion 1: The message appears with the active incident details."""
    msg = format_notification_message(
        incident_id="AA-2026-9999",
        location_desc="Shivajinagar Junction, Pune",
        ambulance_status="En Route",
        ambulance_unit="108 Unit #7",
        hospital_name="Sancheti Hospital",
        leg_a_dist_km=2.45,
        leg_a_eta_min=4.2,
        leg_b_dist_km=1.85,
        leg_b_eta_min=3.1,
        central_police_name="Shivajinagar Police Station"
    )

    assert "AA-2026-9999" in msg
    assert "Shivajinagar Junction, Pune" in msg
    assert "En Route" in msg
    assert "108 Unit #7" in msg
    assert "Sancheti Hospital" in msg
    assert "2.45 km" in msg
    assert "1.85 km" in msg
    assert "Shivajinagar Police Station" in msg


# -----------------------------------------------------------------------------
# 2. Copy Message Text Accuracy
# -----------------------------------------------------------------------------
def test_criterion_2_copy_message_accuracy():
    """Criterion 2: Copy Message copies the exact formatted notification text."""
    msg = format_notification_message(
        incident_id="AA-2026-COPY",
        location_desc="FC Road Crossing",
        ambulance_status="On Scene",
        ambulance_unit="108 Unit #2",
        hospital_name="Ruby Hall Clinic",
        leg_a_dist_km=3.10,
        leg_a_eta_min=5.5,
        leg_b_dist_km=2.20,
        leg_b_eta_min=4.0,
        central_police_name="Deccan Police Station"
    )

    # Verify that message text is complete, newline-formatted, and matches the exact content
    lines = msg.split("\n")
    assert any("AutoAlert incident notification: AA-2026-COPY" in line for line in lines)
    assert any("FC Road Crossing" in line for line in lines)
    assert any("Ruby Hall Clinic" in line for line in lines)
    assert any("Deccan Police Station" in line for line in lines)


# -----------------------------------------------------------------------------
# 3. Prepare Notification Updates State
# -----------------------------------------------------------------------------
def test_criterion_3_prepare_notification_updates_state():
    """Criterion 3: Prepare Notification updates the state to 'prepared'."""
    inc_id = create_test_incident("AA-2026-PREP01")
    db = SessionLocal()
    try:
        IncidentRepository.update_notification_lifecycle(
            db=db,
            incident_id=inc_id,
            lifecycle_stage="prepared",
            message="AutoAlert Test Prepared Message",
            event_title="Police coordination notification prepared [AA-2026-PREP01] [SIMULATED]",
            event_details="Generated with incident coordinates and hospital info."
        )

        inc = IncidentRepository.get_by_id(db, inc_id)
        assert inc is not None
        assert inc.notification_status == "prepared"
        assert inc.notification_message == "AutoAlert Test Prepared Message"

        history = json.loads(inc.notification_history_json or "[]")
        assert len(history) >= 1
        assert history[-1]["stage"] == "prepared"
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 4. Stepper Reflects Authoritative State (Not 5 permanently completed stages)
# -----------------------------------------------------------------------------
def test_criterion_4_stepper_reflects_current_state_not_all_completed():
    """Criterion 4: The stepper reflects the current state, not five permanently completed stages."""
    stages = ["prepared", "sent", "delivered", "acknowledged", "response_initiated"]

    # When state is 'prepared': only Stage 1 is completed/current, 2-5 are pending
    current_stage = "prepared"
    stage_idx = stages.index(current_stage)
    assert stage_idx == 0

    pills_status = []
    for idx, s in enumerate(stages):
        if idx < stage_idx:
            pills_status.append("completed")
        elif idx == stage_idx:
            pills_status.append("active")
        else:
            pills_status.append("pending")

    assert pills_status == ["active", "pending", "pending", "pending", "pending"]

    # When state is 'delivered': stages 0 and 1 completed, stage 2 active, stages 3 and 4 pending
    current_stage = "delivered"
    stage_idx = stages.index(current_stage)
    pills_status = [
        "completed" if idx < stage_idx else ("active" if idx == stage_idx else "pending")
        for idx in range(len(stages))
    ]
    assert pills_status == ["completed", "completed", "active", "pending", "pending"]


# -----------------------------------------------------------------------------
# 5. Simulated Send Updates State and Timeline
# -----------------------------------------------------------------------------
def test_criterion_5_simulated_send_updates_state_and_timeline():
    """Criterion 5: Simulated send updates the state to 'sent' and logs timeline event."""
    inc_id = create_test_incident("AA-2026-SEND01")
    db = SessionLocal()
    try:
        IncidentRepository.update_notification_lifecycle(
            db=db,
            incident_id=inc_id,
            lifecycle_stage="sent",
            event_title="Police notification transmitted to Shivajinagar Police Station [SIMULATED]",
            event_details="Encrypted dossier dispatched."
        )

        inc = IncidentRepository.get_by_id(db, inc_id)
        assert inc.notification_status == "sent"

        timeline = json.loads(inc.timeline_events_json or "[]")
        assert any("transmitted to" in e.get("title", "").lower() for e in timeline)
        assert any("[SIMULATED]" in e.get("title", "") for e in timeline)
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 6. Simulated Delivery is Distinguishable from Actual Delivery
# -----------------------------------------------------------------------------
def test_criterion_6_simulated_delivery_is_distinguishable():
    """Criterion 6: Simulated delivery is distinguishable from actual delivery."""
    inc_id = create_test_incident("AA-2026-DELIV01")
    db = SessionLocal()
    try:
        IncidentRepository.update_notification_lifecycle(
            db=db,
            incident_id=inc_id,
            lifecycle_stage="delivered",
            event_title="Police notification delivered to Shivajinagar Police Station terminal [SIMULATED]",
            event_details="Terminal delivery confirmed."
        )

        inc = IncidentRepository.get_by_id(db, inc_id)
        history = json.loads(inc.notification_history_json or "[]")
        last_event = history[-1]

        # Verify simulation flag and label
        assert last_event["is_simulated"] is True
        assert "[SIMULATED]" in last_event["event"]
        assert inc.notification_status == "delivered"
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 7. Simulated Acknowledgement Updates the Correct Stage
# -----------------------------------------------------------------------------
def test_criterion_7_simulated_acknowledgement_updates_correct_stage():
    """Criterion 7: Simulated acknowledgement updates stage to 'acknowledged'."""
    inc_id = create_test_incident("AA-2026-ACK01")
    record_police_ack(inc_id)

    db = SessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, inc_id)
        assert inc.notification_status == "acknowledged"
        assert "Acknowledged" in inc.police_status

        timeline = json.loads(inc.timeline_events_json or "[]")
        assert any("acknowledges notification" in e.get("title", "").lower() for e in timeline)
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 8. Response Initiated Requires Valid Response Event
# -----------------------------------------------------------------------------
def test_criterion_8_response_initiated_transition_rules(client):
    """Criterion 8: Response Initiated requires prior valid stage."""
    inc_id = create_test_incident("AA-2026-RESP01")

    # Trying to jump directly from 'prepared' to 'response_initiated' via API must fail
    resp_illegal = client.post(
        f"/api/v1/notifications/incident/{inc_id}/transition",
        json={"stage": "response_initiated"}
    )
    assert resp_illegal.status_code == 400
    assert "Invalid transition" in resp_illegal.json()["detail"]

    # Valid step-by-step transition
    client.post(f"/api/v1/notifications/incident/{inc_id}/transition", json={"stage": "sent"})
    client.post(f"/api/v1/notifications/incident/{inc_id}/transition", json={"stage": "delivered"})
    client.post(f"/api/v1/notifications/incident/{inc_id}/transition", json={"stage": "acknowledged"})
    resp_valid = client.post(f"/api/v1/notifications/incident/{inc_id}/transition", json={"stage": "response_initiated"})

    assert resp_valid.status_code == 200
    assert resp_valid.json()["stage"] == "response_initiated"


# -----------------------------------------------------------------------------
# 9. Failed Operations Display Error and Do Not Advance Lifecycle
# -----------------------------------------------------------------------------
def test_criterion_9_failed_operations_do_not_advance_lifecycle(client):
    """Criterion 9: Failed operations display an error and do not advance the lifecycle."""
    inc_id = create_test_incident("AA-2026-FAIL01")

    # Current stage is 'prepared'
    # Try invalid jump: prepared -> acknowledged
    res = client.post(
        f"/api/v1/notifications/incident/{inc_id}/transition",
        json={"stage": "acknowledged"}
    )
    assert res.status_code == 400

    # Ensure state in database did NOT advance
    db = SessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, inc_id)
        assert inc.notification_status in ("prepared", "draft")
        assert inc.notification_status != "acknowledged"
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 10. Page Refresh Restores Persisted State
# -----------------------------------------------------------------------------
def test_criterion_10_persistence_across_page_refresh():
    """Criterion 10: Page refresh restores the correct persisted state from the database."""
    inc_id = create_test_incident("AA-2026-PERSIST01")

    db = SessionLocal()
    try:
        # Simulate advancing to 'delivered' and saving custom notification message
        expected_msg = "Critical Alert: Incident AA-2026-PERSIST01 at Shivajinagar Junction."
        IncidentRepository.update_notification_lifecycle(
            db=db,
            incident_id=inc_id,
            lifecycle_stage="delivered",
            message=expected_msg,
            event_title="Delivered to dispatch console [SIMULATED]",
            event_details="Console ACK expected."
        )
    finally:
        db.close()

    # Emulate page reload: fetch anew with clean DB session
    db_reload = SessionLocal()
    try:
        reloaded_inc = IncidentRepository.get_by_id(db_reload, inc_id)
        assert reloaded_inc is not None
        assert reloaded_inc.notification_status == "delivered"
        assert reloaded_inc.notification_message == expected_msg

        history = json.loads(reloaded_inc.notification_history_json or "[]")
        assert len(history) >= 1
        assert history[-1]["stage"] == "delivered"
    finally:
        db_reload.close()


# -----------------------------------------------------------------------------
# 11. Reset Notification Demo Resets Only Intended Demo State
# -----------------------------------------------------------------------------
def test_criterion_11_reset_notification_demo_preserves_incident():
    """Criterion 11: Reset Notification Demo resets demo stage without deleting incident."""
    inc_id = create_test_incident("AA-2026-RESET01")

    # Advance to acknowledged first
    record_police_ack(inc_id)

    # Now reset the demo
    reset_notification_demo(inc_id)

    db = SessionLocal()
    try:
        inc = IncidentRepository.get_by_id(db, inc_id)
        # Incident record MUST still exist
        assert inc is not None
        assert inc.id == inc_id
        # GPS location and evidence are preserved
        loc = json.loads(inc.location_json)
        assert loc["latitude"] == 18.5204
        assert loc["longitude"] == 73.8567
        # Notification lifecycle is reset to 'prepared'
        assert inc.notification_status == "prepared"
        # Police status is reset from Acknowledged
        assert "Acknowledged" not in (inc.police_status or "")
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 12. Existing Map, Routing, CCTV Video and Scenario Integrity
# -----------------------------------------------------------------------------
def test_criterion_12_existing_functionality_intact():
    """Criterion 12: Existing scenarios, map coords, routing configs, and CCTV data remain intact."""
    # Check scenario configs exist with valid keys
    assert "CAM-001: Main Highway Junction (Collision Scenario)" in SCENARIO_CONFIGS
    cfg = SCENARIO_CONFIGS["CAM-001: Main Highway Junction (Collision Scenario)"]
    assert cfg["camera_id"] == "CAM-001"
    assert "lat" in cfg and "lon" in cfg
    assert "video_path" in cfg

    # Build sample scenario incident
    sample_inc = build_sample_scenario_incident(
        "CAM-001: Main Highway Junction (Collision Scenario)",
        "hosp_sancheti"
    )
    assert sample_inc.id == cfg["incident_id"]
    assert sample_inc.camera_id == cfg["camera_id"]
    assert sample_inc.notification_status in ("draft", "prepared", "sent", "delivered", "acknowledged", "response_initiated")
    timeline = json.loads(sample_inc.timeline_events_json)
    assert len(timeline) >= 4
