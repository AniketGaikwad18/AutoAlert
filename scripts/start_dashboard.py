"""
AutoAlert Dashboard Startup Script (Stage 20).

Launches the Streamlit Command Center UI on the configured host and port.

Usage:
    python scripts/start_dashboard.py
    python scripts/start_dashboard.py --port 8501
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("start_dashboard")


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoAlert Command Center Dashboard")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
        help="Host address to bind (default: 127.0.0.1 or env DASHBOARD_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("DASHBOARD_PORT", "8501")),
        help="Port to bind (default: 8501 or env DASHBOARD_PORT)",
    )
    args = parser.parse_args()

    app_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "app.py")
    app_path = os.path.abspath(app_path)

    if not os.path.exists(app_path):
        logger.error("Dashboard entry point not found at %s", app_path)
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ]

    logger.info("Launching Streamlit dashboard on http://%s:%d ...", args.host, args.port)
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Dashboard shutdown requested by user.")
    except Exception as e:
        logger.error("Failed to run dashboard: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
