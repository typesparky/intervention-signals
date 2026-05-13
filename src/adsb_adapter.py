"""
ADS-B Exchange military flight tracking adapter
"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from geopy.distance import geodesic
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_feed_adapter import BaseFeedAdapter, InterventionEvent


class ADSBAdapter(BaseFeedAdapter):
    """Adapter for ADS-B Exchange military aircraft tracking"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.feed_type = "api"
        self.aircraft_types = config.get('aircraft_types', [])
        self.alert_conditions = config.get('alert_conditions', {})
        self.normal_baselines = {}  # Store baseline behavior for anomaly detection

    def fetch_events(self) -> List[InterventionEvent]:
        """Fetch military aircraft and detect anomalies"""
        try:
            # Fetch military aircraft data
            response = requests.get(self.url, timeout=30)
            response.raise_for_status()

            aircraft_data = response.json()

            if 'ac' not in aircraft_data:
                return []

            events = []
            aircraft_list = aircraft_data['ac']

            # Filter for relevant aircraft types
            relevant_aircraft = [
                ac for ac in aircraft_list
                if self._is_military_aircraft(ac)
            ]

            # Detect anomalies
            for aircraft in relevant_aircraft:
                anomaly_events = self._detect_anomalies(aircraft)
                events.extend(anomaly_events)

            return events

        except Exception as e:
            print(f"Error fetching ADS-B data: {e}")
            return []

    def _is_military_aircraft(self, aircraft: Dict[str, Any]) -> bool:
        """Check if aircraft is of military interest"""
        aircraft_type = aircraft.get('t', '')  # Type field

        # Check against configured military aircraft types
        if self.aircraft_types:
            return any(mtype.upper() in aircraft_type.upper() for mtype in self.aircraft_types)

        # Default military aircraft indicators
        military_indicators = ['B-52', 'B-1', 'B-2', 'F-22', 'F-35', 'A-10', 'KC-', 'E-3']
        return any(ind in aircraft_type for ind in military_indicators)

    def _detect_anomalies(self, aircraft: Dict[str, Any]) -> List[InterventionEvent]:
        """Detect anomalous flight patterns"""
        events = []

        try:
            callsign = aircraft.get('flight', 'UNKNOWN')
            aircraft_type = aircraft.get('t', 'Unknown')
            lat = aircraft.get('lat')
            lon = aircraft.get('lon')
            alt = aircraft.get('alt_baro', aircraft.get('alt_geom', 0))
            speed = aircraft.get('gs', 0)  # Ground speed
            heading = aircraft.get('track', 0)  # Track/heading

            # Location
            location = self._get_location_name(lat, lon) if lat and lon else None
            coordinates = (lat, lon) if lat and lon else None

            # Anomaly 1: Abnormal altitude for aircraft type
            if self._is_abnormal_altitude(aircraft_type, alt):
                event = InterventionEvent(
                    source=self.name,
                    event_type='abnormal_altitude',
                    title=f"Unusual altitude: {aircraft_type} {callsign}",
                    description=f"{aircraft_type} at {alt} ft (normal range: {self._get_normal_altitude_range(aircraft_type)})",
                    timestamp=datetime.now(timezone.utc),
                    location=location,
                    coordinates=coordinates,
                    confidence=0.6,
                    metadata={
                        'callsign': callsign,
                        'aircraft_type': aircraft_type,
                        'altitude': alt,
                        'speed': speed,
                        'heading': heading
                    }
                )
                events.append(event)

            # Anomaly 2: Abnormal deployment location
            if self._is_unusual_deployment(lat, lon):
                event = InterventionEvent(
                    source=self.name,
                    event_type='abnormal_deployment',
                    title=f"Unusual deployment: {aircraft_type} {callsign}",
                    description=f"{aircraft_type} detected in unusual location ({location})",
                    timestamp=datetime.now(timezone.utc),
                    location=location,
                    coordinates=coordinates,
                    confidence=0.7,
                    metadata={
                        'callsign': callsign,
                        'aircraft_type': aircraft_type,
                        'altitude': alt,
                        'speed': speed
                    }
                )
                events.append(event)

            # Anomaly 3: Formation flying (multiple aircraft close together)
            if self._is_in_formation(aircraft, aircraft.get('nearby_aircraft', [])):
                event = InterventionEvent(
                    source=self.name,
                    event_type='formation_flight',
                    title=f"Formation flight detected: {aircraft_type}",
                    description=f"Multiple {aircraft_type} aircraft flying in formation near {location}",
                    timestamp=datetime.now(timezone.utc),
                    location=location,
                    coordinates=coordinates,
                    confidence=0.8,
                    metadata={
                        'callsign': callsign,
                        'aircraft_type': aircraft_type,
                        'formation_size': len(aircraft.get('nearby_aircraft', [])) + 1
                    }
                )
                events.append(event)

        except Exception as e:
            print(f"Error detecting anomalies for aircraft: {e}")

        return events

    def _is_abnormal_altitude(self, aircraft_type: str, altitude: int) -> bool:
        """Check if altitude is abnormal for aircraft type"""
        normal_ranges = {
            'B-52': (20000, 50000),
            'B-1': (15000, 45000),
            'B-2': (25000, 50000),
            'F-22': (10000, 65000),
            'F-35': (10000, 50000),
            'A-10': (5000, 35000),
            'C-130': (5000, 35000),
            'KC-135': (15000, 40000),
            'E-3': (20000, 40000)
        }

        # Check if any aircraft type matches
        for ac_type, (min_alt, max_alt) in normal_ranges.items():
            if ac_type.upper() in aircraft_type.upper():
                return altitude < min_alt or altitude > max_alt

        # Unknown aircraft type - flag if above 60000 or below 1000
        return altitude > 60000 or altitude < 1000

    def _get_normal_altitude_range(self, aircraft_type: str) -> str:
        """Get normal altitude range for aircraft type"""
        normal_ranges = {
            'B-52': (20000, 50000),
            'B-1': (15000, 45000),
            'B-2': (25000, 50000),
            'F-22': (10000, 65000),
            'F-35': (10000, 50000),
            'A-10': (5000, 35000),
            'C-130': (5000, 35000),
            'KC-135': (15000, 40000),
            'E-3': (20000, 40000)
        }

        for ac_type, (min_alt, max_alt) in normal_ranges.items():
            if ac_type.upper() in aircraft_type.upper():
                return f"{min_alt}-{max_alt} ft"

        return "10,000-50,000 ft (estimated)"

    def _is_unusual_deployment(self, lat: float, lon: float) -> bool:
        """Check if location is unusual for military aircraft"""
        # Define regions of interest
        conflict_zones = [
            # Middle East
            {'name': 'Middle East', 'coords': (33.0, 45.0), 'radius': 1500},
            # Ukraine
            {'name': 'Ukraine', 'coords': (48.0, 31.0), 'radius': 800},
            # Taiwan Strait
            {'name': 'Taiwan Strait', 'coords': (25.0, 120.0), 'radius': 600},
            # South China Sea
            {'name': 'South China Sea', 'coords': (12.0, 115.0), 'radius': 1200},
            # Korea Peninsula
            {'name': 'Korea Peninsula', 'coords': (38.0, 127.0), 'radius': 600},
        ]

        # Normal bases
        normal_bases = [
            {'name': 'CONUS', 'coords': (39.0, -98.0), 'radius': 2000},
            {'name': 'Europe', 'coords': (50.0, 10.0), 'radius': 1500},
            {'name': 'Japan', 'coords': (36.0, 138.0), 'radius': 800},
        ]

        # Check if near conflict zones
        for zone in conflict_zones:
            distance = geodesic((lat, lon), zone['coords']).km
            if distance < zone['radius']:
                # Check if NOT near a normal base
                near_base = False
                for base in normal_bases:
                    base_distance = geodesic((lat, lon), base['coords']).km
                    if base_distance < base['radius']:
                        near_base = True
                        break

                if not near_base:
                    return True

        return False

    def _is_in_formation(self, aircraft: Dict[str, Any], nearby_aircraft: List[Dict[str, Any]]) -> bool:
        """Check if aircraft is flying in formation"""
        if not nearby_aircraft:
            return False

        aircraft_type = aircraft.get('t', '')
        lat = aircraft.get('lat')
        lon = aircraft.get('lon')
        alt = aircraft.get('alt_baro', aircraft.get('alt_geom', 0))

        # Formation criteria:
        # - Same aircraft type
        # - Within 5 km horizontally
        # - Within 1000 ft vertically
        # - Similar heading (within 30 degrees)

        formation_count = 0
        for other in nearby_aircraft:
            if other.get('t', '') != aircraft_type:
                continue

            other_lat = other.get('lat')
            other_lon = other.get('lon')
            other_alt = other.get('alt_baro', other.get('alt_geom', 0))

            if not other_lat or not other_lon:
                continue

            # Horizontal distance
            h_distance = geodesic((lat, lon), (other_lat, other_lon)).km
            if h_distance > 5:
                continue

            # Vertical distance
            v_distance = abs(alt - other_alt)
            if v_distance > 1000:
                continue

            # Heading difference
            heading = aircraft.get('track', 0)
            other_heading = other.get('track', 0)
            heading_diff = abs(heading - other_heading)
            if heading_diff > 180:
                heading_diff = 360 - heading_diff

            if heading_diff > 30:
                continue

            formation_count += 1
            if formation_count >= 2:  # At least 2 other aircraft
                return True

        return False

    def _get_location_name(self, lat: float, lon: float) -> Optional[str]:
        """Get rough location name from coordinates"""
        # Simplified location identification
        # In production, use reverse geocoding API
        regions = {
            'Middle East': (30.0, 45.0, 2500),
            'Ukraine': (48.0, 31.0, 1000),
            'Taiwan Strait': (25.0, 120.0, 800),
            'South China Sea': (12.0, 115.0, 1500),
            'Korea Peninsula': (38.0, 127.0, 800),
            'CONUS': (39.0, -98.0, 2500),
            'Europe': (50.0, 10.0, 2000),
        }

        for region, (center_lat, center_lon, radius) in regions.items():
            distance = geodesic((lat, lon), (center_lat, center_lon)).km
            if distance < radius:
                return region

        return f"{lat:.2f}, {lon:.2f}"
