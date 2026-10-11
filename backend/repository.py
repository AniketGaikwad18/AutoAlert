"""
Stage 15 Backend Repository Interface for AutoAlert.

Provides a clean abstraction for persisting and querying incidents, cameras, and facilities.
Stage 15 uses SQLAlchemyRepository for SQLite database persistence.
"""

from __future__ import annotations

import logging
from backend.database.database import init_db
from backend.database.repositories import SQLAlchemyRepository

logger = logging.getLogger(__name__)

# Initialize database tables on startup
init_db()

# Global repository instance backed by SQLite database
repository = SQLAlchemyRepository()

