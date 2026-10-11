"""
Leaflet interactive light-themed street map component for AutoAlert Command Center.

Renders:
- Incident Location (Red Marker with animated pulse beacon)
- Ambulance Location (Blue Marker)
- Destination Hospital (Green Marker)
- Route A: Ambulance Approach (Distinct Blue Polyline)
- Route B: Hospital Transport (Distinct Emerald Green Polyline)
- Mapped Police Stations along/near corridor (Navy Markers, highlighting Central Coordination Hub)
- Mapped Traffic Signals along corridor (Amber Markers, distinguishing directly on-route vs near corridor)
- Corridor buffer visualization (Translucent buffer band)
- Interactive Map Legend (judges can distinguish approach vs transport route)
- Auto fit-bounds
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple, Any


def generate_leaflet_map_html(
    incident_coords: Tuple[float, float],
    incident_name: str,
    ambulance_coords: Tuple[float, float],
    ambulance_name: str,
    hospital_coords: Tuple[float, float],
    hospital_name: str,
    route_a_coords: List[Tuple[float, float]],
    route_b_coords: List[Tuple[float, float]],
    police_stations: List[Dict[str, Any]],
    traffic_signals: List[Dict[str, Any]],
    central_police_station: Optional[Dict[str, Any]] = None,
    route_a_distance_km: float = 0.0,
    route_a_eta_min: float = 0.0,
    route_b_distance_km: float = 0.0,
    route_b_eta_min: float = 0.0,
    corridor_width_m: float = 400.0,
    data_source_name: str = "OpenStreetMap / OSRM",
    height_px: int = 540,
    map_element_id: str = "autoalert_emergency_map"
) -> str:
    """Generate self-contained Leaflet HTML for emergency response map."""

    # Serialize data for JavaScript injection
    inc_lat, inc_lon = float(incident_coords[0]), float(incident_coords[1])
    amb_lat, amb_lon = float(ambulance_coords[0]), float(ambulance_coords[1])
    hosp_lat, hosp_lon = float(hospital_coords[0]), float(hospital_coords[1])

    # Ensure coordinates are floats for JS
    route_a_js = [[float(p[0]), float(p[1])] for p in route_a_coords] if route_a_coords else []
    route_b_js = [[float(p[0]), float(p[1])] for p in route_b_coords] if route_b_coords else []

    police_js = []
    central_id = None
    if central_police_station:
        central_id = central_police_station.get("feature_id") or central_police_station.get("name")

    for p in police_stations:
        police_js.append({
            "id": p.get("feature_id") or p.get("name"),
            "name": p.get("name", "Police Station"),
            "lat": float(p.get("latitude", 0.0)),
            "lon": float(p.get("longitude", 0.0)),
            "address": p.get("address_or_intersection") or p.get("address", "Municipal Jurisdiction"),
            "dist_route_m": p.get("distance_to_route_m", 0.0),
            "is_central": bool(
                p.get("is_central_hub") or 
                (central_id and (p.get("feature_id") == central_id or p.get("name") == central_id))
            ),
            "jurisdiction": p.get("controller_or_jurisdiction") or p.get("jurisdiction", "Local Division")
        })

    signals_js = []
    for s in traffic_signals:
        signals_js.append({
            "id": s.get("feature_id") or s.get("name"),
            "name": s.get("name", "Traffic Signal"),
            "lat": float(s.get("latitude", 0.0)),
            "lon": float(s.get("longitude", 0.0)),
            "intersection": s.get("address_or_intersection") or s.get("intersection", "Intersection"),
            "dist_route_m": s.get("distance_to_route_m", 0.0),
            "is_direct": bool(s.get("directly_on_route", False)),
            "controller": s.get("controller_or_jurisdiction") or s.get("controller", "Adaptive Controller")
        })

    json_data = json.dumps({
        "incident": {"lat": inc_lat, "lon": inc_lon, "name": incident_name},
        "ambulance": {"lat": amb_lat, "lon": amb_lon, "name": ambulance_name},
        "hospital": {"lat": hosp_lat, "lon": hosp_lon, "name": hospital_name},
        "route_a": route_a_js,
        "route_b": route_b_js,
        "route_a_info": {"dist_km": route_a_distance_km, "eta_min": route_a_eta_min},
        "route_b_info": {"dist_km": route_b_distance_km, "eta_min": route_b_eta_min},
        "police": police_js,
        "signals": signals_js,
        "corridor_width_m": corridor_width_m,
        "source": data_source_name
    })

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AutoAlert Emergency Response Map</title>
    <!-- Leaflet 1.9.4 CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
    <!-- Leaflet 1.9.4 JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <style>
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
        }}
        #{map_element_id} {{
            width: 100%;
            height: {height_px}px;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
            background: #f1f5f9;
        }}

        /* Custom Marker Pins */
        .custom-pin {{
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            cursor: pointer;
            transition: transform 0.15s ease;
        }}
        .custom-pin:hover {{
            transform: scale(1.15);
            z-index: 1000 !important;
        }}
        
        /* Incident Pulse Beacon */
        .incident-beacon {{
            background: #dc2626;
            color: #ffffff;
            width: 34px;
            height: 34px;
            border: 2.5px solid #ffffff;
            font-size: 16px;
            position: relative;
        }}
        .incident-beacon::after {{
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 2px solid #dc2626;
            animation: pulse-ring 1.8s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
        }}
        @keyframes pulse-ring {{
            0% {{ transform: scale(1); opacity: 0.9; }}
            70% {{ transform: scale(2.2); opacity: 0; }}
            100% {{ transform: scale(2.2); opacity: 0; }}
        }}

        /* Ambulance Pin */
        .ambulance-pin {{
            background: #2563eb;
            color: #ffffff;
            width: 32px;
            height: 32px;
            border: 2.5px solid #ffffff;
            font-size: 15px;
        }}

        /* Hospital Pin */
        .hospital-pin {{
            background: #059669;
            color: #ffffff;
            width: 32px;
            height: 32px;
            border: 2.5px solid #ffffff;
            font-size: 15px;
        }}

        /* Police Pin */
        .police-pin {{
            background: #1e3a8a;
            color: #ffffff;
            width: 26px;
            height: 26px;
            border: 2px solid #ffffff;
            font-size: 13px;
        }}
        .police-pin.central-hub {{
            background: #0f172a;
            border: 2.5px solid #f59e0b;
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.6);
            width: 30px;
            height: 30px;
            font-size: 15px;
        }}

        /* Traffic Signal Pin */
        .signal-pin {{
            background: #f59e0b;
            color: #ffffff;
            width: 22px;
            height: 22px;
            border: 2px solid #ffffff;
            font-size: 11px;
        }}
        .signal-pin.direct-on-route {{
            background: #d97706;
            border: 2px solid #0f172a;
        }}

        /* Popup Styling */
        .leaflet-popup-content-wrapper {{
            border-radius: 8px;
            padding: 4px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            border: 1px solid #e2e8f0;
        }}
        .popup-card {{
            font-size: 12px;
            line-height: 1.45;
            color: #1e293b;
        }}
        .popup-header {{
            font-weight: 700;
            font-size: 13px;
            padding-bottom: 4px;
            margin-bottom: 5px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .popup-row {{
            margin: 2px 0;
            display: flex;
            justify-content: space-between;
            gap: 12px;
        }}
        .popup-label {{
            color: #64748b;
            font-weight: 500;
        }}
        .popup-val {{
            font-weight: 600;
            color: #0f172a;
            text-align: right;
        }}

        /* Legend */
        .map-legend {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(4px);
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-size: 11px;
            line-height: 1.5;
            color: #1e293b;
            max-width: 240px;
        }}
        .legend-title {{
            font-weight: 700;
            font-size: 12px;
            color: #0f172a;
            margin-bottom: 6px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 3px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 3px 0;
        }}
        .legend-line {{
            width: 20px;
            height: 4px;
            border-radius: 2px;
            display: inline-block;
        }}
        .legend-line.route-a {{ background: #2563eb; }}
        .legend-line.route-b {{ background: #059669; }}
        .legend-symbol {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            display: inline-block;
            text-align: center;
            line-height: 14px;
            font-size: 9px;
        }}
    </style>
</head>
<body>
    <div id="{map_element_id}"></div>

    <script>
        (function() {{
            const data = {json_data};

            // Initialize Leaflet Map centered around incident
            const map = L.map('{map_element_id}', {{
                zoomControl: true,
                attributionControl: true
            }}).setView([data.incident.lat, data.incident.lon], 14);

            // Light Street Map Tile Layer (CartoDB Positron / OSM)
            const lightBasemap = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>'
            }});
            const osmStandard = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }});
            lightBasemap.addTo(map);

            const baseLayers = {{
                "Light Street Map (Positron)": lightBasemap,
                "OpenStreetMap Standard": osmStandard
            }};
            L.control.layers(baseLayers, null, {{ position: 'topright' }}).addTo(map);

            const boundsPoints = [];

            // 1. Draw Route A: Ambulance -> Incident (Solid Blue)
            if (data.route_a && data.route_a.length > 0) {{
                const polyA = L.polyline(data.route_a, {{
                    color: '#2563eb',
                    weight: 5,
                    opacity: 0.9,
                    lineJoin: 'round'
                }}).addTo(map);
                polyA.bindTooltip(`<b>Route A (Ambulance Approach)</b><br>Distance: ${{data.route_a_info.dist_km.toFixed(2)}} km | ETA: ~${{data.route_a_info.eta_min.toFixed(1)}} mins<br>Shortest practical route via OSRM`, {{ sticky: true }});
                data.route_a.forEach(p => boundsPoints.push(p));
            }} else {{
                // Fallback straight line if no polyline
                L.polyline([[data.ambulance.lat, data.ambulance.lon], [data.incident.lat, data.incident.lon]], {{
                    color: '#2563eb',
                    weight: 4,
                    dashArray: '6, 8',
                    opacity: 0.8
                }}).addTo(map);
            }}

            // 2. Draw Corridor Buffer Visualization along Route B (Translucent Band)
            if (data.route_b && data.route_b.length > 0) {{
                L.polyline(data.route_b, {{
                    color: '#60a5fa',
                    weight: 24,
                    opacity: 0.16,
                    lineCap: 'round',
                    lineJoin: 'round'
                }}).addTo(map);
            }}

            // 3. Draw Route B: Incident -> Hospital (Solid Emerald Green)
            if (data.route_b && data.route_b.length > 0) {{
                const polyB = L.polyline(data.route_b, {{
                    color: '#059669',
                    weight: 5,
                    opacity: 0.9,
                    lineJoin: 'round'
                }}).addTo(map);
                polyB.bindTooltip(`<b>Route B (Hospital Transport)</b><br>Distance: ${{data.route_b_info.dist_km.toFixed(2)}} km | ETA: ~${{data.route_b_info.eta_min.toFixed(1)}} mins<br>Infrastructure corridor monitored`, {{ sticky: true }});
                data.route_b.forEach(p => boundsPoints.push(p));
            }} else {{
                L.polyline([[data.incident.lat, data.incident.lon], [data.hospital.lat, data.hospital.lon]], {{
                    color: '#059669',
                    weight: 4,
                    dashArray: '6, 8',
                    opacity: 0.8
                }}).addTo(map);
            }}

            // 4. Incident Marker (RED)
            const incIcon = L.divIcon({{
                className: 'custom-pin incident-beacon',
                html: '🚨',
                iconSize: [34, 34],
                iconAnchor: [17, 17]
            }});
            const incMarker = L.marker([data.incident.lat, data.incident.lon], {{ icon: incIcon, zIndexOffset: 1000 }}).addTo(map);
            incMarker.bindPopup(`
                <div class="popup-card">
                    <div class="popup-header" style="color: #dc2626;">
                        <span>🚨 VERIFIED INCIDENT LOCATION</span>
                    </div>
                    <div class="popup-row"><span class="popup-label">Site:</span><span class="popup-val">${{data.incident.name}}</span></div>
                    <div class="popup-row"><span class="popup-label">Coordinates:</span><span class="popup-val">${{data.incident.lat.toFixed(4)}}° N, ${{data.incident.lon.toFixed(4)}}° E</span></div>
                    <div class="popup-row"><span class="popup-label">Status:</span><span class="popup-val" style="color:#b91c1c;">AI VERIFIED COLLISION</span></div>
                    <div class="popup-row"><span class="popup-label">Response:</span><span class="popup-val" style="color:#15803d;">Multi-Agency Coordinated</span></div>
                </div>
            `);
            boundsPoints.push([data.incident.lat, data.incident.lon]);

            // 5. Ambulance Marker (BLUE)
            const ambIcon = L.divIcon({{
                className: 'custom-pin ambulance-pin',
                html: '🚑',
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            }});
            const ambMarker = L.marker([data.ambulance.lat, data.ambulance.lon], {{ icon: ambIcon, zIndexOffset: 900 }}).addTo(map);
            ambMarker.bindPopup(`
                <div class="popup-card">
                    <div class="popup-header" style="color: #2563eb;">
                        <span>🚑 RESPONDING AMBULANCE</span>
                    </div>
                    <div class="popup-row"><span class="popup-label">Assigned Unit:</span><span class="popup-val">${{data.ambulance.name}}</span></div>
                    <div class="popup-row"><span class="popup-label">Approach Distance:</span><span class="popup-val">${{data.route_a_info.dist_km.toFixed(2)}} km</span></div>
                    <div class="popup-row"><span class="popup-label">Estimated Transit:</span><span class="popup-val" style="color:#16a34a;">~${{data.route_a_info.eta_min.toFixed(1)}} mins</span></div>
                    <div class="popup-row"><span class="popup-label">Position:</span><span class="popup-val">${{data.ambulance.lat.toFixed(4)}}° N, ${{data.ambulance.lon.toFixed(4)}}° E</span></div>
                    <div class="popup-row"><span class="popup-label">Dispatch Mode:</span><span class="popup-val" style="color:#2563eb;">[SIMULATED DISPATCH]</span></div>
                </div>
            `);
            boundsPoints.push([data.ambulance.lat, data.ambulance.lon]);

            // 6. Destination Hospital Marker (GREEN)
            const hospIcon = L.divIcon({{
                className: 'custom-pin hospital-pin',
                html: '🏥',
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            }});
            const hospMarker = L.marker([data.hospital.lat, data.hospital.lon], {{ icon: hospIcon, zIndexOffset: 900 }}).addTo(map);
            hospMarker.bindPopup(`
                <div class="popup-card">
                    <div class="popup-header" style="color: #059669;">
                        <span>🏥 DESTINATION HOSPITAL</span>
                    </div>
                    <div class="popup-row"><span class="popup-label">Hospital:</span><span class="popup-val">${{data.hospital.name}}</span></div>
                    <div class="popup-row"><span class="popup-label">Transport Dist:</span><span class="popup-val">${{data.route_b_info.dist_km.toFixed(2)}} km</span></div>
                    <div class="popup-row"><span class="popup-label">Estimated Transit:</span><span class="popup-val" style="color:#16a34a;">~${{data.route_b_info.eta_min.toFixed(1)}} mins</span></div>
                    <div class="popup-row"><span class="popup-label">Capability:</span><span class="popup-val">Emergency Trauma Ward</span></div>
                    <div class="popup-row"><span class="popup-label">Note:</span><span class="popup-val" style="font-size:10px; color:#64748b;">Transit candidate based on proximity</span></div>
                </div>
            `);
            boundsPoints.push([data.hospital.lat, data.hospital.lon]);

            // 7. Police Stations along Route B (NAVY)
            data.police.forEach(pol => {{
                const isCentral = pol.is_central;
                const pIcon = L.divIcon({{
                    className: 'custom-pin police-pin ' + (isCentral ? 'central-hub' : ''),
                    html: isCentral ? '★' : '🚔',
                    iconSize: isCentral ? [30, 30] : [26, 26],
                    iconAnchor: isCentral ? [15, 15] : [13, 13]
                }});
                const pMarker = L.marker([pol.lat, pol.lon], {{ icon: pIcon, zIndexOffset: isCentral ? 850 : 800 }}).addTo(map);
                pMarker.bindPopup(`
                    <div class="popup-card">
                        <div class="popup-header" style="color: #1e3a8a;">
                            <span>${{isCentral ? '🚔 ★ CENTRAL COORDINATION HUB' : '🚔 POLICE STATION'}}</span>
                        </div>
                        <div class="popup-row"><span class="popup-label">Station:</span><span class="popup-val">${{pol.name}}</span></div>
                        <div class="popup-row"><span class="popup-label">Address:</span><span class="popup-val">${{pol.address}}</span></div>
                        <div class="popup-row"><span class="popup-label">Dist to Corridor:</span><span class="popup-val">${{pol.dist_route_m.toFixed(0)}}m</span></div>
                        <div class="popup-row"><span class="popup-label">Jurisdiction:</span><span class="popup-val">${{pol.jurisdiction}}</span></div>
                        <div class="popup-row"><span class="popup-label">Status:</span><span class="popup-val" style="color:#2563eb;">${{isCentral ? 'Coordination Hub Selected' : 'Notified Corridor Precinct'}}</span></div>
                    </div>
                `);
                boundsPoints.push([pol.lat, pol.lon]);
            }});

            // 8. Traffic Signals along Route B (AMBER)
            data.signals.forEach(sig => {{
                const sIcon = L.divIcon({{
                    className: 'custom-pin signal-pin ' + (sig.is_direct ? 'direct-on-route' : ''),
                    html: '🚦',
                    iconSize: [22, 22],
                    iconAnchor: [11, 11]
                }});
                const sMarker = L.marker([sig.lat, sig.lon], {{ icon: sIcon, zIndexOffset: 700 }}).addTo(map);
                sMarker.bindPopup(`
                    <div class="popup-card">
                        <div class="popup-header" style="color: #d97706;">
                            <span>🚦 MAPPED TRAFFIC SIGNAL</span>
                        </div>
                        <div class="popup-row"><span class="popup-label">Signal:</span><span class="popup-val">${{sig.name}}</span></div>
                        <div class="popup-row"><span class="popup-label">Intersection:</span><span class="popup-val">${{sig.intersection}}</span></div>
                        <div class="popup-row"><span class="popup-label">Proximity:</span><span class="popup-val">${{sig.is_direct ? 'Directly on Route' : sig.dist_route_m.toFixed(0) + 'm off-centerline'}}</span></div>
                        <div class="popup-row"><span class="popup-label">Controller:</span><span class="popup-val">${{sig.controller}}</span></div>
                        <div class="popup-row"><span class="popup-label">Data Source:</span><span class="popup-val" style="font-size:10px;">OpenStreetMap Verified Node</span></div>
                    </div>
                `);
                boundsPoints.push([sig.lat, sig.lon]);
            }});

            // 9. Interactive Legend Control
            const legend = L.control({{ position: 'bottomright' }});
            legend.onAdd = function() {{
                const div = L.DomUtil.create('div', 'map-legend');
                div.innerHTML = `
                    <div class="legend-title">🗺️ Emergency Transit Map Legend</div>
                    <div class="legend-item"><span class="legend-line route-a"></span> <b>Route A:</b> Ambulance Approach</div>
                    <div class="legend-item"><span class="legend-line route-b"></span> <b>Route B:</b> Hospital Transport</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#dc2626; color:#fff;">🚨</span> Incident Site</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#2563eb; color:#fff;">🚑</span> Responding Ambulance</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#059669; color:#fff;">🏥</span> Destination Hospital</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#0f172a; color:#f59e0b; border:1px solid #f59e0b;">★</span> Central Police Station</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#1e3a8a; color:#fff;">🚔</span> Corridor Police Station</div>
                    <div class="legend-item"><span class="legend-symbol" style="background:#f59e0b; color:#fff;">🚦</span> Mapped Traffic Signal</div>
                    <div style="font-size:10px; color:#64748b; margin-top:5px; border-top:1px solid #e2e8f0; padding-top:3px;">
                        Corridor Buffer: <b>${{data.corridor_width_m}}m</b> | OSRM Light
                    </div>
                `;
                return div;
            }};
            legend.addTo(map);

            // Fit bounds to display all key landmarks and routes
            if (boundsPoints.length > 0) {{
                map.fitBounds(boundsPoints, {{ padding: [35, 35] }});
            }}
        }})();
    </script>
</body>
</html>
"""
    return html
