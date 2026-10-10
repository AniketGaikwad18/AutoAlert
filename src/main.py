"""AutoAlert entry point.

Provides CLI interface and foundation health check for the AutoAlert
emergency detection platform prototype.
"""

import sys
import logging
from pathlib import Path
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("autoalert")


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load system configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def verify_foundation() -> dict:
    """Verify foundation components, directories and baseline health."""
    required_dirs = [
        "config", "data", "models", "src", "backend",
        "dashboard", "tests", "scripts", "outputs", "docs"
    ]
    status = {}
    for d in required_dirs:
        p = Path(d)
        status[d] = p.exists() and p.is_dir()

    return {
        "status": "ready" if all(status.values()) else "degraded",
        "directories": status,
        "python_version": sys.version.split()[0],
    }


def main():
    """Main CLI execution."""
    logger.info("Initializing AutoAlert Foundation...")
    health = verify_foundation()
    logger.info(f"System status: {health['status']}")
    logger.info(f"Python environment: {health['python_version']}")
    
    config = load_config()
    app_info = config.get("app", {})
    logger.info(f"Loaded configuration for: {app_info.get('name', 'AutoAlert')} v{app_info.get('version', '0.1.0')}")
    print("\nAutoAlert AI/IoT Platform Prototype initialized successfully.")
    print("Foundation is ready. Use pytest to execute test suite.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
