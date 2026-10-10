---
name: autoalert-engineering
description: Engineering rules for the AutoAlert AI/IoT emergency detection platform.
---

# AutoAlert Engineering Rules

AutoAlert upgrades existing CCTV infrastructure using an AI/IoT Box.
The laptop is the prototype representation of that future box.

Core flow:
Existing CCTV -> Video -> Frame Processing -> Detection -> Tracking ->
Event Candidate -> Verification -> Evidence -> Incident Package ->
Central Backend -> Dashboard / simulated emergency response.

Rules:
1. Implement one stage at a time.
2. Every major module must be independently testable.
3. Keep detection, tracking, event detection, verification, evidence and backend concerns separate.
4. Never claim a feature works unless executable code and validation exist.
5. Never invent accuracy, FPS, latency, cost or deployment metrics.
6. Do not treat bounding-box overlap as proof of collision.
7. Do not treat motionlessness as proof of injury.
8. Do not describe simple HSV/color segmentation as reliable blood detection.
9. Do not treat OCR output as ground truth.
10. OCR must support unreadable / low-confidence results.
11. Do not hard-code credentials, tokens, API keys or private URLs.
12. Do not claim real police, ambulance or hospital integration unless authorized integration exists.
13. Prototype emergency-service workflows must be simulated.
14. Prefer modular, explainable solutions over unnecessary complexity.
15. Do not rewrite unrelated working modules.
16. Before a major change: inspect -> plan -> implement -> test -> report.
17. After a change, state exactly what was implemented and what remains unimplemented.
18. Do not optimize for Raspberry Pi until the laptop pipeline is validated.
19. Preserve structured logging and configurable paths/settings.
20. Ask before downloading large/random datasets or introducing major new dependencies.

Collision candidate logic should eventually consider multiple temporal signals such as:
tracking, relative motion, trajectory changes, distance changes, sudden motion changes,
temporal persistence and scene context.

Number-plate pipeline:
vehicle detection -> tracking -> best-frame selection -> plate detection ->
crop/preprocess -> OCR -> temporal aggregation -> confidence.

Verified incident data may include:
incident ID, type, camera ID, timestamp, location, evidence frames,
short evidence video, object/track IDs, plate text when readable,
OCR confidence and verification status.
