import os
from pathlib import Path

dirs = [
    "data/videos/raw", "data/videos/test", "data/images", "data/plates", "data/test_cases",
    "models/detection", "models/tracking", "models/license_plate",
    "outputs/incidents", "outputs/videos", "outputs/frames", "outputs/logs",
    "scripts", "docs",
    "src/video", "src/detection", "src/tracking", "src/events",
    "src/license_plate", "src/evidence", "src/location", "src/core", "src/utils",
    "backend/routes", "backend/database", "backend/schemas",
    "dashboard/pages", "dashboard/components",
    "tests"
]

for d in dirs:
    Path(d).mkdir(parents=True, exist_ok=True)
    if "data/" in d or "models/" in d or "outputs/" in d:
        gitkeep = Path(d) / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

packages = [
    "src", "src/video", "src/detection", "src/tracking", "src/events",
    "src/license_plate", "src/evidence", "src/location", "src/core", "src/utils",
    "backend", "backend/routes", "backend/database", "backend/schemas",
    "dashboard", "dashboard/pages", "dashboard/components",
    "tests"
]

for pkg in packages:
    init_file = Path(pkg) / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Package initialization."""\n', encoding="utf-8")

print("Directory structure and packages initialized successfully.")
