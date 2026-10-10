"""Launcher for AutoAlert Streamlit Command Center Dashboard."""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    app_path = ROOT_DIR / "dashboard" / "app.py"
    print(f"Starting AutoAlert Dashboard at {app_path} ...")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nAutoAlert Dashboard stopped.")
