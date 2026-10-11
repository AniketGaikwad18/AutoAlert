"""Raspberry Pi AI Box edge client simulator.

Simulates the field-side Raspberry Pi AI Box:
- Emits real-time periodic heartbeats with telemetry to the AutoAlert central backend.
- Supports generating and forwarding real device incident events to demonstrate LIVE DEVICE mode.
"""

import sys
import time
import argparse
import platform
import psutil
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def send_heartbeat(backend_url: str = "http://127.0.0.1:8000") -> bool:
    """Send heartbeat ping with device telemetry."""
    endpoint = f"{backend_url}/api/device/heartbeat"
    payload = {
        "device_id": "PI-AI-BOX-01",
        "device_name": "Raspberry Pi 5 AI Box (Edge Unit 01)",
        "ip_address": "192.168.1.105",
        "telemetry": {
            "platform": platform.platform(),
            "cpu_percent": psutil.cpu_percent(),
            "ram_used_mb": round(psutil.Process().memory_info().rss / (1024 * 1024), 1),
            "device_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    }
    try:
        res = requests.post(endpoint, json=payload, timeout=3.0)
        return res.status_code == 200
    except Exception as e:
        print(f"[Warning] Failed to reach backend at {endpoint}: {e}")
        return False


def trigger_device_incident(backend_url: str = "http://127.0.0.1:8000") -> None:
    """Forward an incident detected by the edge AI Box to the central backend."""
    endpoint = f"{backend_url}/api/incidents"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inc_suffix = time.strftime("%M%S")
    payload = {
        "incident_id": f"INC-LIVE-PI-{inc_suffix}",
        "incident_type": "Possible Road Accident",
        "camera_id": "CAM-01",
        "timestamp": now_iso,
        "confidence_score": 0.912,
        "verification_status": "verified",
        "involved_track_ids": [10, 11],
        "reasons": [
            "Hardware NPU collision candidate verified",
            "Spatial divergence 35px at high deceleration ratio 0.85"
        ],
        "signals": {
            "npu_confidence": 0.912,
            "speed_drop": 0.85
        },
        "location": {
            "latitude": 18.5204,
            "longitude": 73.8567,
            "description": "Shivajinagar Junction, Pune"
        },
        "evidence": {
            "directory": "outputs/incidents/INC-0001",
            "key_frames": ["outputs/incidents/INC-0001/keyframe_33_1.jpg", "outputs/incidents/INC-0001/keyframe_34_2.jpg"],
            "video_clip": "outputs/incidents/INC-0001/clip_INC-0001.mp4"
        },
        "plate_readings": [
            {
                "track_id": 10,
                "plate_text": "MH12AB1234",
                "confidence": 0.89,
                "is_readable": True,
                "format_valid": True
            }
        ]
    }
    try:
        res = requests.post(endpoint, json=payload, timeout=5.0)
        if res.status_code == 201:
            print(f"Successfully transmitted live incident from Pi: {payload['incident_id']}")
        else:
            print(f"Failed to transmit incident: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error transmitting incident: {e}")


def main():
    parser = argparse.ArgumentParser(description="AutoAlert Raspberry Pi Client Simulator")
    parser.add_argument("--backend", default="http://127.0.0.1:8000", help="AutoAlert backend URL")
    parser.add_argument("--trigger", action="store_true", help="Send a single live incident and exit")
    parser.add_argument("--interval", type=int, default=5, help="Heartbeat interval in seconds")
    args = parser.parse_args()

    if args.trigger:
        trigger_device_incident(args.backend)
        return

    print("=" * 60)
    print("AutoAlert Raspberry Pi AI Box: Field Device Simulator")
    print(f"Backend Target: {args.backend}")
    print(f"Heartbeat Interval: {args.interval}s")
    print("Press Ctrl+C to terminate.")
    print("=" * 60)

    while True:
        ok = send_heartbeat(args.backend)
        status_txt = "SUCCESS (Connected)" if ok else "FAILED (Backend offline)"
        print(f"[{time.strftime('%H:%M:%S')}] Heartbeat to {args.backend} -> {status_txt}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
