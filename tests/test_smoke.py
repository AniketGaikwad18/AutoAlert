"""Stage 1 Smoke and Import Validation Tests."""

import importlib
from pathlib import Path
from src.main import verify_foundation, load_config


def test_required_directories_exist():
    """Verify that all target top-level directories exist."""
    health = verify_foundation()
    assert health["status"] == "ready"
    for dir_name, exists in health["directories"].items():
        assert exists is True, f"Directory {dir_name} is missing."


def test_src_subpackages_importable():
    """Verify that all src subpackages can be imported cleanly."""
    packages = [
        "src.video",
        "src.detection",
        "src.tracking",
        "src.events",
        "src.license_plate",
        "src.evidence",
        "src.location",
        "src.core",
        "src.utils",
        "backend.routes",
        "backend.database",
        "backend.schemas",
        "dashboard.pages",
        "dashboard.components",
    ]
    for pkg in packages:
        mod = importlib.import_module(pkg)
        assert mod is not None, f"Failed to import {pkg}"


def test_config_loading():
    """Verify that settings.yaml can be parsed correctly."""
    config = load_config("config/settings.yaml")
    assert "app" in config
    assert config["app"]["name"] == "AutoAlert"
    assert "paths" in config
    assert "video" in config
    assert "detection" in config
