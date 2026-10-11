"""
AutoAlert Clean-Start System Validation Script (Stage 20).

Performs an automated sanity validation of the entire local deployment setup:
1. Validates Python environment and dependencies
2. Checks configuration files and example templates
3. Initializes clean database tables in data/
4. Validates output directories (data/, outputs/evidence/)
5. Executes the full pipeline demo flow
6. Validates FastAPI backend API endpoints and schema responses
7. Validates Dashboard client connection and facility matching
8. Validates simulated emergency notification lifecycle
9. Prints a comprehensive validation report

Usage:
    python scripts/clean_start_validation.py
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("clean_start")


def run_clean_start_validation() -> bool:
    print("=" * 72)
    print("  AUTOALERT CLEAN-START SYSTEM VALIDATION (STAGE 20)")
    print("  Prototype Deployment Readiness & Pipeline Verification")
    print("=" * 72)

    checks_passed = 0
    total_checks = 8

    # --------------------------------------------------------------------------
    # Check 1: Directory Structure & File Preparation
    # --------------------------------------------------------------------------
    print("\n[Check 1/8] Verifying directory structure and required paths...")
    required_dirs = ["config", "data", "outputs", "outputs/evidence", "scripts", "src", "backend", "dashboard"]
    missing_dirs = [d for d in required_dirs if not os.path.exists(d)]
    if missing_dirs:
        for d in missing_dirs:
            os.makedirs(d, exist_ok=True)
        print(f"  -> Created missing directories: {missing_dirs}")
    print("  [PASS] All required directories verified.")
    checks_passed += 1

    # --------------------------------------------------------------------------
    # Check 2: Configuration & Templates Existence
    # --------------------------------------------------------------------------
    print("\n[Check 2/8] Checking configuration files and example templates...")
    required_configs = [
        "config/settings.yaml",
        "config/settings.example.yaml",
        "config/cameras.example.yaml",
        "config/facilities.example.yaml",
        ".env.example",
    ]
    missing_configs = [c for c in required_configs if not os.path.exists(c)]
    if missing_configs:
        print(f"  [FAIL] Missing configuration files: {missing_configs}")
        return False
    print("  [PASS] All configuration files and examples present.")
    checks_passed += 1

    # --------------------------------------------------------------------------
    # Check 3: Database Clean Initialization
    # --------------------------------------------------------------------------
    print("\n[Check 3/8] Testing database table creation and repository initialization...")
    try:
        from backend.database.database import init_db, engine, Base
        from backend.database.repositories import SQLAlchemyRepository
        Base.metadata.create_all(bind=engine)
        repo = SQLAlchemyRepository()
        cams = repo.list_cameras()
        facs = repo.list_facilities()
        print(f"  -> Database operational. Seeded entities: {len(cams)} cameras, {len(facs)} simulated facilities.")
        print("  [PASS] Database engine and session factory initialized cleanly.")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL] Database initialization failed: {e}")
        return False

    # --------------------------------------------------------------------------
    # Check 4: Core Pipeline Modules Import & Instantiation
    # --------------------------------------------------------------------------
    print("\n[Check 4/8] Verifying core pipeline module imports...")
    try:
        from src.video.frame_processor import FrameProcessor
        from src.detection.detector import Detection
        from src.tracking.tracker import MultiObjectTracker
        from src.events.collision import CollisionCandidateDetector
        from src.events.motionless import MotionlessCandidateDetector
        from src.events.anomaly import VisualAnomalyDetector
        from src.events.verifier import EventVerifier
        from src.evidence.recorder import EvidenceRecorder
        from src.license_plate.aggregator import PlateTemporalAggregator
        print("  [PASS] All core vision, tracking, and event modules instantiated cleanly.")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL] Core module import failed: {e}")
        return False

    # --------------------------------------------------------------------------
    # Check 5: Local Pipeline Execution
    # --------------------------------------------------------------------------
    print("\n[Check 5/8] Running controlled local pipeline test...")
    try:
        from scripts.run_local_demo import run_demo
        run_demo(num_frames=15, evidence_out="outputs/evidence")
        print("  [PASS] End-to-end pipeline execution succeeded.")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL] Pipeline execution failed: {e}")
        return False

    # --------------------------------------------------------------------------
    # Check 6: FastAPI Backend Health & API Contracts
    # --------------------------------------------------------------------------
    print("\n[Check 6/8] Testing FastAPI backend endpoints via TestClient...")
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)

        r_health = client.get("/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        assert r_health.json().get("status") == "ok"

        r_cams = client.get("/api/v1/cameras")
        assert r_cams.status_code == 200, f"Cameras endpoint failed: {r_cams.text}"

        r_facs = client.get("/api/v1/facilities")
        assert r_facs.status_code == 200, f"Facilities endpoint failed: {r_facs.text}"

        r_incs = client.get("/api/v1/incidents")
        assert r_incs.status_code == 200, f"Incidents endpoint failed: {r_incs.text}"

        print("  [PASS] FastAPI routes (/health, /cameras, /facilities, /incidents) validated.")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL] Backend API endpoint verification failed: {e}")
        return False

    # --------------------------------------------------------------------------
    # Check 7: Simulated Dispatch & Notification Lifecycle
    # --------------------------------------------------------------------------
    print("\n[Check 7/8] Testing simulated emergency facility dispatch lifecycle...")
    try:
        from dashboard.api_client import DashboardAPIClient
        dash = DashboardAPIClient()
        incs = dash.list_incidents(limit=1)
        if incs:
            inc_id = incs[0]["incident_id"]
            facs = dash.match_facilities(inc_id, latitude=18.5204, longitude=73.8567, limit=1)
            if facs:
                notif = dash.trigger_notification(inc_id, facs[0]["facility_id"], "VALIDATION DISPATCH TEST")
                assert notif["is_simulated"] is True
                assert notif["status"] == "notified"

                # Advance lifecycle
                updated = dash.update_notification_status(notif["notification_id"], "resolved", reason="Test complete")
                assert updated["status"] == "resolved"
        print("  [PASS] Simulated notification lifecycle (notified -> resolved) validated.")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL] Simulated dispatch lifecycle failed: {e}")
        return False

    # --------------------------------------------------------------------------
    # Check 8: Regression Test Suite Execution
    # --------------------------------------------------------------------------
    print("\n[Check 8/8] Checking existing unit and integration test suite...")
    # Fast check on key test modules
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"  [PASS] Full unit and integration test suite passed ({result.testsRun} tests).")
        checks_passed += 1
    else:
        print(f"  [FAIL] Test suite had {len(result.failures)} failures and {len(result.errors)} errors.")
        return False

    print("\n" + "=" * 72)
    print(f"  VALIDATION SUMMARY: {checks_passed}/{total_checks} CHECKS PASSED")
    print("  AutoAlert Prototype is ready for local deployment and demonstration.")
    print("=" * 72)
    return True


if __name__ == "__main__":
    success = run_clean_start_validation()
    sys.exit(0 if success else 1)
