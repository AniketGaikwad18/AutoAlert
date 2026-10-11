"""
AutoAlert Database Initialization Script (Stage 20).

Initializes SQLite or PostgreSQL database tables, prepares storage directories,
and optionally seeds sample camera registries and simulated emergency facilities.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --reset
    python scripts/init_db.py --seed-config
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import yaml

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.database import init_db, engine, Base
from backend.database.repositories import SQLAlchemyRepository
from backend.schemas.camera import CameraSchema
from backend.schemas.facility import FacilitySchema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_db")


def seed_from_config(repo: SQLAlchemyRepository) -> None:
    """Optionally load cameras and facilities from yaml configuration files."""
    cameras_path = os.path.join("config", "cameras.yaml")
    facilities_path = os.path.join("config", "facilities.yaml")

    if os.path.exists(cameras_path):
        try:
            with open(cameras_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for cam in data.get("cameras", []):
                    schema = CameraSchema(**cam)
                    repo.add_camera(schema)
                    logger.info("Loaded camera from config: %s (%s)", schema.camera_id, schema.name)
        except Exception as e:
            logger.warning("Could not load cameras from config: %s", e)

    if os.path.exists(facilities_path):
        try:
            with open(facilities_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for fac in data.get("facilities", []):
                    schema = FacilitySchema(**fac)
                    repo.add_facility(schema)
                    logger.info("Loaded simulated facility from config: %s (%s)", schema.facility_id, schema.name)
        except Exception as e:
            logger.warning("Could not load facilities from config: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoAlert Database Initialization")
    parser.add_argument("--reset", action="store_true", help="Wipe existing tables and re-initialize")
    parser.add_argument("--seed-config", action="store_true", help="Seed data from config/cameras.yaml and config/facilities.yaml")
    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    os.makedirs("outputs/evidence", exist_ok=True)

    if args.reset:
        logger.warning("Resetting database tables...")
        Base.metadata.drop_all(bind=engine)

    logger.info("Creating database tables...")
    init_db()

    repo = SQLAlchemyRepository()

    if args.seed_config:
        logger.info("Seeding database from config files...")
        seed_from_config(repo)

    cams = repo.list_cameras()
    facs = repo.list_facilities()
    incs = repo.list_incidents()

    logger.info("Database initialized successfully.")
    logger.info("Current counts: %d cameras, %d facilities, %d incidents.", len(cams), len(facs), len(incs))


if __name__ == "__main__":
    main()
