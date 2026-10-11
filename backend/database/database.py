"""Database engine and session management for AutoAlert backend."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./outputs/autoalert.db")

# Ensure directory for SQLite exists
if DATABASE_URL.startswith("sqlite:///"):
    db_file_path = DATABASE_URL.replace("sqlite:///", "")
    if db_file_path != ":memory:":
        Path(db_file_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None):
    """Create all tables on target engine and perform column migrations if needed."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    # SQLite migration for newly added columns if table already existed
    try:
        with eng.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute("PRAGMA table_info(incidents)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                new_columns = [
                    ("source_device", "TEXT DEFAULT 'Raspberry Pi AI Box'"),
                    ("mode", "TEXT DEFAULT 'DEMO'"),
                    ("ambulance_status", "TEXT DEFAULT 'Awaiting Dispatch'"),
                    ("ambulance_unit", "TEXT DEFAULT '108 Fast Response Unit #4'"),
                    ("ambulance_dispatched_at", "TEXT"),
                    ("ambulance_eta", "TEXT DEFAULT '~4 mins'"),
                    ("police_station_name", "TEXT DEFAULT 'Shivajinagar Central Police Headquarters'"),
                    ("police_status", "TEXT DEFAULT 'Notification Pending'"),
                    ("police_notified_at", "TEXT"),
                    ("timeline_events_json", "TEXT DEFAULT '[]'"),
                    ("notification_message", "TEXT"),
                    ("notification_history_json", "TEXT DEFAULT '[]'"),
                ]
                for col_name, col_type in new_columns:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE incidents ADD COLUMN {col_name} {col_type}")

            cursor.execute("PRAGMA table_info(cameras)")
            existing_cam_cols = {row[1] for row in cursor.fetchall()}
            if existing_cam_cols and "status" not in existing_cam_cols:
                cursor.execute("ALTER TABLE cameras ADD COLUMN status TEXT DEFAULT 'active'")
            if existing_cam_cols and "merchant_name" not in existing_cam_cols:
                cursor.execute("ALTER TABLE cameras ADD COLUMN merchant_name TEXT DEFAULT 'Highway Junction Superstore'")

            conn.connection.commit()
    except Exception as e:
        # Ignore for other database dialects or if table doesn't exist yet
        pass

