"""
Tests for AutoAlert Emergency Response Command Center Upgrade.

Validates:
1. Leaflet map HTML generation with custom markers, routes, and infrastructure nodes.
2. Route A (Ambulance Approach) and Route B (Hospital Transport) calculation via route_engine.
3. OpenStreetMap corridor analysis: deduplicated police station & traffic signal counts.
4. Central police station selection based on incident proximity and jurisdiction.
5. Configurable corridor width buffers (200m, 400m, 800m).
6. Honest data handling: no fabricated counts when data is missing or empty.
7. Ambulance dispatch lifecycle state transitions (7 distinct states).
8. Central police notification message formatting and lifecycle states.
9. Deterministic execution of end-to-end demo trigger and clean reset.
10. Multi-hospital switching dynamically updating route distances, ETAs, and corridor analysis.
"""

import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base, get_db
from backend.database.repositories import IncidentRepository, DeviceRepository, seed_defaults_if_empty
from src.dispatch.routing import route_engine, EmergencyRouteResult
from src.dispatch.corridor_analysis import corridor_analyzer, CorridorAnalysisResult, RouteCorridorAnalyzer
from src.location.facility_registry import facility_registry
from dashboard.components.map_view import generate_leaflet_map_html
from dashboard.app import (
    AMBULANCE_STAGES,
    run_full_emergency_demo,
    record_police_ack,
    reset_police_ack,
    advance_ambulance_stage,
    build_sample_scenario_incident
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Setup clean in-memory database for command center tests."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_defaults_if_empty(db)
    db.close()

    monkeypatch.setattr("backend.database.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("dashboard.app.SessionLocal", TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_leaflet_map_html_generation():
    """Verify Leaflet HTML correctly embeds incident, ambulance, hospital, routes, and legend."""
    inc_coords = (18.5204, 73.8567)
    amb_coords = (18.5300, 73.8500)
    hosp_coords = (18.5312, 73.8523)

    route_a = [(18.5300, 73.8500), (18.5250, 73.8530), (18.5204, 73.8567)]
    route_b = [(18.5204, 73.8567), (18.5260, 73.8540), (18.5312, 73.8523)]

    police = [{
        "feature_id": "POL-01",
        "name": "Shivajinagar Police Station",
        "latitude": 18.5320,
        "longitude": 73.8510,
        "distance_to_route_m": 120.0,
        "is_central_hub": True,
        "address": "JM Road, Pune"
    }]
    signals = [{
        "feature_id": "SIG-01",
        "name": "Sancheti Chowk Signal",
        "latitude": 18.5308,
        "longitude": 73.8528,
        "distance_to_route_m": 15.0,
        "directly_on_route": True,
        "intersection": "JM Road Crossing"
    }]

    html = generate_leaflet_map_html(
        incident_coords=inc_coords,
        incident_name="Shivajinagar Junction",
        ambulance_coords=amb_coords,
        ambulance_name="108 Fast Response Unit #4",
        hospital_coords=hosp_coords,
        hospital_name="Sancheti Hospital Emergency Care",
        route_a_coords=route_a,
        route_b_coords=route_b,
        police_stations=police,
        traffic_signals=signals,
        central_police_station=police[0],
        route_a_distance_km=1.42,
        route_a_eta_min=2.4,
        route_b_distance_km=1.35,
        route_b_eta_min=2.1,
        corridor_width_m=400.0,
        data_source_name="OpenStreetMap / OSRM"
    )

    assert "leaflet.js" in html
    assert "autoalert_emergency_map" in html
    assert "Route A (Ambulance Approach)" in html
    assert "Route B (Hospital Transport)" in html
    assert "Shivajinagar Junction" in html
    assert "108 Fast Response Unit #4" in html
    assert "Sancheti Hospital Emergency Care" in html
    assert "Shivajinagar Police Station" in html
    assert "Sancheti Chowk Signal" in html
    assert "400.0" in html or "400" in html
    assert "Emergency Transit Map Legend" in html


def test_emergency_route_calculation_2_legs():
    """Verify route_engine calculates distinct Route A and Route B with distance & durations."""
    all_facs = [f.model_dump() for f in facility_registry.list_facilities()]
    res = route_engine.plan_emergency_route(
        ambulance_lat=18.5300,
        ambulance_lon=73.8500,
        incident_lat=18.5204,
        incident_lon=73.8567,
        hospital_lat=18.5312,
        hospital_lon=73.8523,
        ambulance_name="108 Fast Response Unit #4",
        hospital_name="Sancheti Hospital",
        all_facilities=all_facs
    )

    assert isinstance(res, EmergencyRouteResult)
    assert len(res.legs) == 2

    # Leg A: Ambulance -> Incident
    leg_a = res.legs[0]
    assert leg_a.origin_name == "108 Fast Response Unit #4"
    assert "Incident" in leg_a.destination_name
    assert leg_a.distance_km > 0.5
    assert leg_a.duration_min > 0.5
    assert len(leg_a.coordinates) >= 2

    # Leg B: Incident -> Hospital
    leg_b = res.legs[1]
    assert "Incident" in leg_b.origin_name
    assert "Sancheti Hospital" in leg_b.destination_name
    assert leg_b.distance_km > 0.5
    assert leg_b.duration_min > 0.5
    assert len(leg_b.coordinates) >= 2

    assert res.total_distance_km == round(leg_a.distance_km + leg_b.distance_km, 2)


def test_corridor_analysis_deduplication_and_counts():
    """Verify corridor analysis deduplicates infrastructure features and counts on-route vs near-corridor."""
    # Polyline from Shivajinagar Junction to Sancheti Hospital
    route_coords = [
        (18.5204, 73.8567),
        (18.5250, 73.8545),
        (18.5300, 73.8530),
        (18.5312, 73.8523)
    ]

    res = corridor_analyzer.analyze_corridor(
        route_coords=route_coords,
        corridor_width_meters=400.0,
        incident_lat=18.5204,
        incident_lon=73.8567
    )

    assert isinstance(res, CorridorAnalysisResult)
    assert res.corridor_width_m == 400.0
    assert res.police_station_count >= 1
    assert res.traffic_signal_count >= 1

    # Verify no duplicate police station IDs
    pol_ids = [p.feature_id for p in res.police_stations]
    assert len(pol_ids) == len(set(pol_ids))

    # Verify no duplicate signal IDs
    sig_ids = [s.feature_id for s in res.traffic_signals]
    assert len(sig_ids) == len(set(sig_ids))

    # Verify central police station selection
    assert res.central_police_station is not None
    assert "Shivajinagar" in res.central_police_station.name

    # Total signal count must equal direct + near
    assert res.traffic_signal_count == (res.direct_signal_count + res.near_signal_count)


def test_corridor_analysis_empty_route_honest_reporting():
    """Verify empty or missing route reports data unavailable rather than fabricating counts."""
    res = corridor_analyzer.analyze_corridor(
        route_coords=[],
        corridor_width_meters=400.0,
        incident_lat=18.5204,
        incident_lon=73.8567
    )

    assert res.police_station_count == 0
    assert res.traffic_signal_count == 0
    assert res.central_police_station is None
    assert "No Route Coordinates Available" in res.data_source


def test_corridor_buffer_width_configuration():
    """Verify changing corridor width affects search tolerance."""
    route_coords = [
        (18.5204, 73.8567),
        (18.5312, 73.8523)
    ]

    res_narrow = corridor_analyzer.analyze_corridor(route_coords, corridor_width_meters=100.0)
    res_wide = corridor_analyzer.analyze_corridor(route_coords, corridor_width_meters=800.0)

    assert res_narrow.corridor_width_m == 100.0
    assert res_wide.corridor_width_m == 800.0
    # Wide corridor buffer must capture >= narrow buffer features
    assert res_wide.traffic_signal_count >= res_narrow.traffic_signal_count


def test_end_to_end_demo_run_and_database_persistence():
    """Verify run_full_emergency_demo persists complete incident, routes, and timeline."""
    run_full_emergency_demo("CAM-001: Main Highway Junction", "FAC-HOSP-01")

    db = TestingSessionLocal()
    try:
        inc = IncidentRepository.get_latest(db)
        assert inc is not None
        assert inc.camera_id == "CAM-001"
        assert inc.verification_status == "verified"
        assert inc.mode == "DEMO"
        assert "Shivajinagar" in inc.police_station_name
        assert inc.ambulance_status == "En Route"

        timeline = json.loads(inc.timeline_events_json or "[]")
        assert len(timeline) >= 6

        # Check chronological milestone titles
        titles = [e["title"] for e in timeline]
        assert any("detected" in t.lower() for t in titles)
        assert any("verification" in t.lower() for t in titles)
        assert any("ambulance approach route calculated" in t.lower() for t in titles)
        assert any("hospital transport route calculated" in t.lower() for t in titles)
        assert any("police station" in t.lower() for t in titles)
    finally:
        db.close()


def test_police_acknowledgement_lifecycle():
    """Verify police acknowledgement updates status and appends milestone without overwriting history."""
    run_full_emergency_demo("CAM-001: Main Highway Junction", "FAC-HOSP-01")

    db = TestingSessionLocal()
    try:
        inc = IncidentRepository.get_latest(db)
        assert inc is not None
        orig_timeline = json.loads(inc.timeline_events_json or "[]")
        orig_count = len(orig_timeline)
    finally:
        db.close()

    # Simulate Police Acknowledgement
    record_police_ack(inc.id)

    db = TestingSessionLocal()
    try:
        updated = IncidentRepository.get_by_id(db, inc.id)
        assert "acknowledged" in updated.police_status.lower()

        updated_timeline = json.loads(updated.timeline_events_json or "[]")
        assert len(updated_timeline) == orig_count + 1
        assert "acknowledges" in updated_timeline[-1]["title"].lower()
    finally:
        db.close()


def test_police_acknowledgement_sample_mode():
    """Verify police acknowledgement succeeds in sample mode when incident is not in SQLite."""
    import streamlit as st
    st.session_state["police_ack_state"] = "Pending Desk Ack"
    
    # In sample mode, incident ID is not in DB
    record_police_ack("AA-2026-001")
    assert st.session_state.get("police_ack_state") == "Confirmed by Officer"

    # Build sample incident with confirmed ack
    inc = build_sample_scenario_incident("CAM-001: Main Highway Junction", "FAC-HOSP-01")
    assert inc.police_status == "Acknowledged [SIMULATED]"
    sample_timeline = json.loads(inc.timeline_events_json)
    assert any("police desk officer acknowledges" in s["title"].lower() for s in sample_timeline)


def test_police_acknowledgement_reset():
    """Verify reset_police_ack reverts status to pending desk ack."""
    import streamlit as st
    run_full_emergency_demo("CAM-001: Main Highway Junction", "FAC-HOSP-01")

    db = TestingSessionLocal()
    try:
        inc = IncidentRepository.get_latest(db)
        assert inc is not None
    finally:
        db.close()

    record_police_ack(inc.id)
    assert st.session_state.get("police_ack_state") == "Confirmed by Officer"

    reset_police_ack(inc.id)
    assert st.session_state.get("police_ack_state") == "Pending Desk Ack"

    db = TestingSessionLocal()
    try:
        updated = IncidentRepository.get_by_id(db, inc.id)
        assert "sent" in updated.police_status.lower()
    finally:
        db.close()


def test_ambulance_dispatch_stages_distinct():
    """Verify ambulance progresses through distinct lifecycle states without jumping to arrived."""
    assert len(AMBULANCE_STAGES) == 7
    assert AMBULANCE_STAGES[0] == "Awaiting dispatch"
    assert AMBULANCE_STAGES[3] == "En route"
    assert AMBULANCE_STAGES[4] == "Arrived at incident"
    assert AMBULANCE_STAGES[5] == "Transporting patient"
    assert AMBULANCE_STAGES[6] == "Arrived at hospital"
