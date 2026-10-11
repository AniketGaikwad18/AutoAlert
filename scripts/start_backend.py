"""
AutoAlert Backend Startup Script (Stage 20).

Launches the FastAPI backend application on the configured host and port.

Usage:
    python scripts/start_backend.py
    python scripts/start_backend.py --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("start_backend")


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoAlert FastAPI Backend Server")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("API_HOST", "127.0.0.1"),
        help="Host address to bind (default: 127.0.0.1 or env API_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("API_PORT", "8000")),
        help="Port to bind (default: 8000 or env API_PORT)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("API_RELOAD", "false").lower() in ("true", "1", "yes"),
        help="Enable auto-reload on code change",
    )
    args = parser.parse_args()

    # Ensure required directories exist before starting
    os.makedirs("data", exist_ok=True)
    os.makedirs("outputs/evidence", exist_ok=True)

    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn is not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    logger.info("Starting AutoAlert FastAPI Backend on http://%s:%d (reload=%s)", args.host, args.port, args.reload)
    logger.info("API Health endpoint: http://%s:%d/health", args.host, args.port)
    logger.info("API Documentation:  http://%s:%d/docs", args.host, args.port)

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
