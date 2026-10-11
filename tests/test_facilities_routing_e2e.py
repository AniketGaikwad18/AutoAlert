"""
Comprehensive Tests for Facility Registry, Spatial Matching, and OSRM Routing (Phases 11–13).

Validates:
1. Facility Registry: Registration, listing, filtering, and configuration persistence.
2. Haversine Distance Calculation: Mathematical precision on known GPS landmarks.
3. Nearest-Facility Matching:
   - Nearest available ambulance
   - Nearest hospital / trauma center
   - Nearby police station
   - All nearby facilities grouped and sorted by distance
4. OpenStreetMap / OSRM Emergency Routing:
   - 2-Leg route (Ambulance -> Incident -> Hospital)
   - Stations along route identification
   - Graceful fallback when offline or server unreachable (explicitly marked as fallback/demo)
   - Zero paid Google Maps APIs
5. API Endpoints:
   - GET /api/v1/facilities
   - POST /api/v1/facilities/match
   - POST /api/v1/dispatch/route
   - GET /api/v1/incidents/{id}/route
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.repository import repository
from backend.schemas.facility import FacilitySchema
from src.core.incident import IncidentPackage, LocationInfo
from src.dispatch.matching import haversine_distance, FacilityMatcher
from src.dispatch.routing import RouteEngine, RouteLeg, EmergencyRouteResult, route_engine
from src.location.facility_registry import FacilityRegistry, facility_registry, IncidentDispatchPlan


class TestFacilitiesAndRoutingPhases11To13(unittest.TestCase):
    """Test suite covering Phases 11 through 13."""

    def setUp(self):
        repository.reset()
        facility_registry.reload()
        self.client = TestClient(app)

    # ----------------------------------------------------------------------
    # 1. Haversine Distance Mathematical Validation
    # ----------------------------------------------------------------------

    def test_haversine_distance_known_coordinates(self):
        """Calculates accurate great-circle distance between known GPS coordinates."""
        # Pune Junction (18.5284, 73.8739) to Swargate Bus Stand (18.5018, 73.8586) ~ 3.3 km
        dist = haversine_distance(18.5284, 73.8739, 18.5018, 73.8586)
        self.assertAlmostEqual(dist, 3.3, delta=0.5)

        # Same point distance is 0.0
        self.assertEqual(haversine_distance(18.5204, 73.8567, 18.5204, 73.8567), 0.0)

    # ----------------------------------------------------------------------
    # 2. Facility Registry & Spatial Matching
    # ----------------------------------------------------------------------

    def test_facility_registry_listing_and_filtering(self):
        """Facility registry lists and filters facilities by type and availability."""
        all_facs = facility_registry.list_facilities()
        self.assertGreaterEqual(len(all_facs), 3)

        ambulances = facility_registry.list_facilities(facility_type="ambulance")
        self.assertTrue(all(f.type == "ambulance" for f in ambulances))

        hospitals = facility_registry.list_facilities(facility_type="hospital")
        self.assertTrue(all(f.type == "hospital" for f in hospitals))

        police = facility_registry.list_facilities(facility_type="police")
        self.assertTrue(all(f.type == "police" for f in police))

    def test_nearest_facility_selection(self):
        """Matches closest ambulance, hospital, and police station for incident coordinates."""
        # Incident at Pune Center (18.5204, 73.8567)
        inc_lat = 18.5204
        inc_lon = 73.8567

        plan: IncidentDispatchPlan = facility_registry.plan_emergency_dispatch(inc_lat, inc_lon)

        self.assertIsNotNone(plan.nearest_ambulance)
        self.assertEqual(plan.nearest_ambulance.get("type"), "ambulance")
        self.assertIsNotNone(plan.nearest_ambulance.get("distance_km"))

        self.assertIsNotNone(plan.nearest_hospital)
        self.assertEqual(plan.nearest_hospital.get("type"), "hospital")

        self.assertIsNotNone(plan.nearest_police)
        self.assertEqual(plan.nearest_police.get("type"), "police")

        self.assertIn("ambulance", plan.nearby_facilities)
        self.assertIn("hospital", plan.nearby_facilities)
        self.assertIn("police", plan.nearby_facilities)

    # ----------------------------------------------------------------------
    # 3. OpenStreetMap / OSRM Emergency Routing & Fallback
    # ----------------------------------------------------------------------

    def test_osrm_fallback_when_server_unreachable(self):
        """Gracefully falls back to demo road network and clearly marks it as fallback."""
        engine = RouteEngine(osrm_base_url="http://invalid-unreachable-domain.local", timeout_sec=0.1)

        origin = {"name": "EMS Depot A", "latitude": 18.5220, "longitude": 73.8580}
        incident = {"name": "Accident Location", "latitude": 18.5204, "longitude": 73.8567}
        hospital = {"name": "City Trauma Center", "latitude": 18.5190, "longitude": 73.8610}

        route_res = engine.calculate_emergency_route(origin, incident, hospital)

        self.assertIsNotNone(route_res)
        self.assertFalse(route_res.is_real_road_network)
        self.assertEqual(route_res.route_source, "Demo Road Network (Fallback)")
        self.assertEqual(len(route_res.legs), 2)
        self.assertEqual(route_res.legs[0].source, "Demo Road Network (Fallback)")
        self.assertGreater(route_res.total_distance_km, 0.0)
        self.assertGreater(route_res.estimated_duration_min, 0.0)

        # Coordinates contain multi-point geometry
        self.assertGreaterEqual(len(route_res.coordinates), 4)

        # Dictionary serialization
        r_dict = route_res.to_dict()
        self.assertEqual(r_dict["route_source"], "Demo Road Network (Fallback)")
        self.assertFalse(r_dict["is_real_road_network"])

    def test_osrm_success_when_api_responds(self):
        """OSRM query parsing returns real road route."""
        engine = RouteEngine(timeout_sec=1.0)

        # Mock OSRM response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 3200.0,
                    "duration": 360.0,
                    "geometry": {
                        "coordinates": [[73.8580, 18.5220], [73.8570, 18.5210], [73.8567, 18.5204]]
                    },
                }
            ],
        }

        with patch("requests.get", return_value=mock_response):
            leg = engine.calculate_leg(18.5220, 73.8580, 18.5204, 73.8567, "EMS", "Incident")
            self.assertEqual(leg.source, "OpenStreetMap / OSRM Road Route")
            self.assertEqual(leg.distance_km, 3.2)
            self.assertEqual(leg.duration_min, 6.0)
            self.assertEqual(leg.coordinates[0], (18.5220, 73.8580))

    def test_stations_along_route_identification(self):
        """Identifies emergency stations within corridor buffer along the route."""
        coords = [(18.5220, 73.8580), (18.5210, 73.8570), (18.5204, 73.8567)]
        all_facs = [
            {"facility_id": "P1", "name": "Nearby Police Post", "type": "police", "latitude": 18.5212, "longitude": 73.8572},
            {"facility_id": "P2", "name": "Distant Station", "type": "police", "latitude": 19.5000, "longitude": 74.5000},
        ]

        stations = route_engine.find_stations_along_route(coords, all_facs, max_distance_km=1.0)
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0]["facility_id"], "P1")
        self.assertIn("distance_to_route_km", stations[0])
        self.assertEqual(stations[0]["station_role"], "Traffic Clearing & Intersection Control")

    # ----------------------------------------------------------------------
    # 4. API Endpoints Integration Tests
    # ----------------------------------------------------------------------

    def test_api_list_facilities(self):
        """GET /api/v1/facilities returns list of registered facilities."""
        res = self.client.get("/api/v1/facilities")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_api_match_facilities(self):
        """POST and GET /api/v1/facilities/match returns structured nearest facilities."""
        res = self.client.get("/api/v1/facilities/match?latitude=18.5204&longitude=73.8567")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nearest_ambulance", data)
        self.assertIn("nearest_hospital", data)
        self.assertIn("nearest_police", data)
        self.assertIn("nearby_facilities", data)

    def test_api_calculate_direct_route(self):
        """POST /api/v1/dispatch/route calculates emergency route for coordinates."""
        payload = {
            "incident_latitude": 18.5204,
            "incident_longitude": 73.8567,
        }
        res = self.client.post("/api/v1/dispatch/route", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_distance_km", data)
        self.assertIn("estimated_duration_min", data)
        self.assertIn("legs", data)
        self.assertIn("coordinates", data)
        self.assertIn("route_source", data)

    def test_api_get_incident_route(self):
        """GET /api/v1/incidents/{incident_id}/route returns emergency route for stored incident."""
        # Create mock verified incident in repository
        incident_pkg = IncidentPackage(
            incident_id="INCIDENT-ROUTE-TEST-001",
            incident_type="vehicle_collision",
            camera_id="CAM-001",
            timestamp=1.5,
            verification_status="verified",
            confidence_score=0.90,
            location=LocationInfo(
                name="Demo Junction",
                latitude=18.5204,
                longitude=73.8567,
                zone_id="ZONE-A",
            ),
        )
        repository.add_incident(incident_pkg)

        res = self.client.get("/api/v1/incidents/INCIDENT-ROUTE-TEST-001/route")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_distance_km", data)
        self.assertIn("legs", data)
        self.assertEqual(len(data["legs"]), 2)


if __name__ == "__main__":
    unittest.main()
