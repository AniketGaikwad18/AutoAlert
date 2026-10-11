"""FastAPI application entry point for AutoAlert central command backend."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.database import init_db, SessionLocal
from backend.database.repositories import seed_defaults_if_empty
from backend.routes.incidents import router as incidents_router
from backend.routes.cameras import router as cameras_router
from backend.routes.facilities import router as facilities_router
from backend.routes.device import router as device_router
from backend.routes.demo import router as demo_router
from backend.routes.notifications import router as notifications_router
from backend.routes.analysis import router as analysis_router
from backend.routes.teammate import router as teammate_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autoalert.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    logger.info("Initializing AutoAlert database and default seed records...")
    init_db()
    db = SessionLocal()
    try:
        seed_defaults_if_empty(db)
    finally:
        db.close()
    logger.info("AutoAlert backend startup complete.")
    yield
    logger.info("AutoAlert backend shutting down.")


app = FastAPI(
    title="AutoAlert Central Command API",
    description="Emergency event ingestion, camera tracking, and simulated response backend.",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for dashboard and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(incidents_router)
app.include_router(cameras_router)
app.include_router(facilities_router)
app.include_router(device_router)
app.include_router(demo_router)
app.include_router(notifications_router)
app.include_router(analysis_router)
app.include_router(teammate_router)


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "ok",
        "service": "AutoAlert Central Backend",
        "version": "0.1.0",
        "simulation_mode": True,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
