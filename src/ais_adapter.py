"""
AIS (Automatic Identification System) adapter
Monitors maritime traffic through critical chokepoints
Focuses on tankers and energy transport vessels
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import time
import math

from base_feed_adapter import BaseFeedAdapter, InterventionEvent


class AISAdapter(BaseFeedAdapter):
    """
    AIS tracking adapter for monitoring maritime chokepoints
    Tracks vessel movements through Hormuz, Bab el-Mandeb, etc.
    """

    # API endpoints (multiple providers - will try free options first)
    MARINETRAFFIC_API_URL = "https://api.marinetraffic.com/api/portnet"
    # Note: MarineTraffic requires paid API
    # Alternative: use public AIS feeds or satellite AIS services

    # Chokepoint definitions
    CHOKEPOINTS = {
        'strait_of_hormuz': {
            'name': 'Strait of Hormuz',
            'description': 'Critical bottleneck for oil shipments from Persian Gulf',
            'bbox': {
                'min_lat': 25.0, 'max_lat': 27.0,
                'min_lon': 55.0, 'max_lon': 57.5
            },
            'width_km': 54,
            'critical': True,
            'avg_daily_tanker_transits': 15  # Approximate
        },
        'bab_el_mandeb': {
            'name': 'Bab el-Mandeb',
            'description': 'Gateway to Suez Canal from Indian Ocean',
            'bbox': {
                'min_lat': 12.0, 'max_lat': 13.5,
                'min_lon': 42.5, 'max_lon': 44.0
            },
            'width_km': 29,
            'critical': True,
            'avg_daily_tanker_transits': 5  # Approximate
        },
        'suez_canal': {
            'name': 'Suez Canal',
            'description': 'Critical link between Mediterranean and Red Sea',
            'bbox': {
                'min_lat': 29.5, 'max_lat': 31.0,
                'min_lon': 32.0, 'max_lon': 33.0
            },
            'width_km': 205,
            'critical': True,
            'avg_daily_tanker_transits': 50  # Approximate
        },
        'bosphorus': {
            'name': 'Bosphorus Strait',
            'description': 'Connects Black Sea to Mediterranean',
            'bbox': {
                'min_lat': 40.5, 'max_lat': 41.5,
                'min_lon': 28.5, 'max_lon': 29.5
            },
            'width_km': 3.4,
            'critical': True,
            'avg_daily_tanker_transits': 3  # Approximate
        },
        'malacca': {
            'name': 'Strait of Malacca',
            'description': 'Main shipping lane between Indian Ocean and Pacific',
            'bbox': {
                'min_lat': 1.0, 'max_lat': 5.0,
                'min_lon': 99.0, 'max_lon': 103.0
            },
            'width_km': 250,
            'critical': True,
            'avg_daily_tanker_transits': 30  # Approximate
        }
    }

    # Vessel types of interest
    VESSEL_TYPES_ENERGY = [
        'Tanker',
        'Oil Tanker',
        'Chemical Tanker',
        'LNG Tanker',
        'LPG Tanker',
        'Bitumen Tanker'
    ]

    # Alert conditions
    ALERT_CONDITIONS = {
        'stopped_tanker': {
            'description': 'Tanker stopped for extended period',
            'stop_duration_threshold': 3600,  # 1 hour in seconds
            'confidence_boost': 0.3
        },
        'deviation': {
            'description': 'Significant deviation from normal route',
            'deviation_threshold': 10.0,  # km deviation
            'confidence_boost': 0.2
        },
        'high_density': {
            'description': 'Unusually high vessel density',
            'density_threshold': 50,  # vessels in area
            'confidence_boost': 0.2
        },
        'military_vessel': {
            'description': 'Military vessel presence in chokepoint',
            'confidence_boost': 0.4
        }
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.api_provider = config.get('api_provider', 'marinetraffic')
        self.simulated_mode = config.get('simulated_mode', True)  # Start in simulated mode
        self.history_window_hours = config.get('history_window_hours', 24)
        self.chokepoints_to_monitor = config.get('chokepoints', [])

        # If no chokepoints specified, monitor all critical ones
        if not self.chokepoints_to_monitor:
            self.chokepoints_to_monitor = [
                k for k, v in self.CHOKEPOINTS.items()
                if v.get('critical', False)
            ]

        if self.simulated_mode:
            print("WARNING: AIS adapter running in SIMULATED MODE")
            print("         Real AIS API requires paid subscription")
            print("         Configure api_key and set simulated_mode: false for real data")

    def fetch_events(self) -> List[InterventionEvent]:
        """
        Fetch AIS data and detect anomalies at chokepoints
        """
        events = []

        if self.simulated_mode:
            # Generate simulated data for testing
            print("  Running in SIMULATED MODE - generating test data")
            events = self._generate_simulated_events()
        elif self.api_key:
            # Fetch real AIS data
            for chokepoint_id in self.chokepoints_to_monitor:
                try:
                    vessels = self._fetch_chokepoint_vessels(chokepoint_id)
                    anomalies = self._detect_anomalies(vessels, chokepoint_id)
                    events.extend(anomalies)

                except Exception as e:
                    print(f"  Error monitoring {chokepoint_id}: {e}")
                    continue
        else:
            print("  ERROR: AIS API key required for real data")
            print("         Either provide api_key or set simulated_mode: true")

        print(f"  Found {len(events)} maritime anomalies")
        return events

    def _fetch_chokepoint_vessels(self, chokepoint_id: str) -> List[Dict[str, Any]]:
        """
        Fetch vessel positions for a chokepoint
        This would call the actual AIS API
        """
        vessels = []

        try:
            chokepoint = self.CHOKEPOINTS[chokepoint_id]
            bbox = chokepoint['bbox']

            # Build API request (example for MarineTraffic)
            # Note: Actual API implementation depends on provider
            params = {
                'apiKey': self.api_key,
                'msgtype': 'extended',
                'box': f"{bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']}",
                'vesselTypes': ','.join([str(i) for i in range(70, 77)])  # Tanker types
            }

            response = requests.get(
                self.MARINETRAFFIC_API_URL,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                # Parse vessel data
                vessels = self._parse_vessel_data(data)

            elif response.status_code == 429:
                print(f"  Rate limit exceeded for AIS API")
                time.sleep(5)

        except Exception as e:
            print(f"  Error fetching AIS data: {e}")

        return vessels

    def _parse_vessel_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse vessel data from AIS API response
        """
        vessels = []

        # Implementation depends on API provider format
        # This is a placeholder for parsing logic

        return vessels

    def _detect_anomalies(
        self,
        vessels: List[Dict[str, Any]],
        chokepoint_id: str
    ) -> List[InterventionEvent]:
        """
        Detect anomalies in vessel movements
        """
        events = []
        chokepoint = self.CHOKEPOINTS[chokepoint_id]

        # Detect stopped tankers
        for vessel in vessels:
            if self._is_tanker(vessel):
                if self._is_vessel_stopped(vessel):
                    event = self._create_stopped_vessel_event(vessel, chokepoint)
                    events.append(event)

                if self._has_route_deviation(vessel):
                    event = self._create_deviation_event(vessel, chokepoint)
                    events.append(event)

            if self._is_military_vessel(vessel):
                event = self._create_military_vessel_event(vessel, chokepoint)
                events.append(event)

        # Detect unusual density
        tankers = [v for v in vessels if self._is_tanker(v)]
        if len(tankers) > self.ALERT_CONDITIONS['high_density']['density_threshold']:
            event = self._create_high_density_event(tankers, chokepoint)
            events.append(event)

        return events

    def _generate_simulated_events(self) -> List[InterventionEvent]:
        """
        Generate simulated AIS events for testing
        """
        events = []

        # Generate random anomalies for each monitored chokepoint
        for chokepoint_id in self.chokepoints_to_monitor:
            chokepoint = self.CHOKEPOINTS[chokepoint_id]

            # 30% chance of stopped tanker
            if random.random() < 0.3:
                events.append(self._create_simulated_stopped_tanker(chokepoint))

            # 20% chance of military vessel
            if random.random() < 0.2:
                events.append(self._create_simulated_military_vessel(chokepoint))

            # 10% chance of route deviation
            if random.random() < 0.1:
                events.append(self._create_simulated_deviation(chokepoint))

        return events

    def _create_stopped_vessel_event(
        self,
        vessel: Dict[str, Any],
        chokepoint: Dict[str, Any]
    ) -> InterventionEvent:
        """Create event for stopped tanker"""
        return InterventionEvent(
            source=f"AIS ({self.api_provider})",
            event_type="maritime_anomaly",
            title=f"Tanker Stopped in {chokepoint['name']}",
            description=(
                f"Tanker vessel has stopped moving in critical chokepoint.\n"
                f"Vessel: {vessel.get('name', 'Unknown')}\n"
                f"Position: {vessel.get('lat', 0):.4f}, {vessel.get('lon', 0):.4f}\n"
                f"Speed: {vessel.get('speed', 0)} knots\n"
                f"Duration: {vessel.get('stop_duration', 0)} seconds\n"
                f"Chokepoint: {chokepoint['name']}\n"
                f"Width: {chokepoint['width_km']} km"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(vessel.get('lat', 0), vessel.get('lon', 0)),
            confidence=0.7,
            metadata={
                'vessel_id': vessel.get('id'),
                'vessel_name': vessel.get('name'),
                'vessel_type': vessel.get('type'),
                'speed': vessel.get('speed', 0),
                'stop_duration': vessel.get('stop_duration', 0),
                'chokepoint_id': list(self.CHOKEPOINTS.keys())[list(self.CHOKEPOINTS.values()).index(chokepoint)],
                'anomaly_type': 'stopped_tanker'
            }
        )

    def _create_military_vessel_event(
        self,
        vessel: Dict[str, Any],
        chokepoint: Dict[str, Any]
    ) -> InterventionEvent:
        """Create event for military vessel presence"""
        return InterventionEvent(
            source=f"AIS ({self.api_provider})",
            event_type="military_activity",
            title=f"Military Vessel in {chokepoint['name']}",
            description=(
                f"Military vessel detected in critical chokepoint.\n"
                f"Vessel: {vessel.get('name', 'Unknown')}\n"
                f"Type: {vessel.get('type', 'Unknown')}\n"
                f"Position: {vessel.get('lat', 0):.4f}, {vessel.get('lon', 0):.4f}\n"
                f"Speed: {vessel.get('speed', 0)} knots\n"
                f"Chokepoint: {chokepoint['name']}\n"
                f"Width: {chokepoint['width_km']} km"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(vessel.get('lat', 0), vessel.get('lon', 0)),
            confidence=0.8,
            metadata={
                'vessel_id': vessel.get('id'),
                'vessel_name': vessel.get('name'),
                'vessel_type': vessel.get('type'),
                'speed': vessel.get('speed', 0),
                'chokepoint_id': list(self.CHOKEPOINTS.keys())[list(self.CHOKEPOINTS.values()).index(chokepoint)],
                'anomaly_type': 'military_vessel'
            }
        )

    def _create_high_density_event(
        self,
        vessels: List[Dict[str, Any]],
        chokepoint: Dict[str, Any]
    ) -> InterventionEvent:
        """Create event for unusual vessel density"""
        return InterventionEvent(
            source=f"AIS ({self.api_provider})",
            event_type="maritime_congestion",
            title=f"High Vessel Density in {chokepoint['name']}",
            description=(
                f"Unusual concentration of tankers in chokepoint.\n"
                f"Tanker count: {len(vessels)}\n"
                f"Average daily transits: ~{chokepoint['avg_daily_tanker_transits']}\n"
                f"Chokepoint: {chokepoint['name']}\n"
                f"Width: {chokepoint['width_km']} km\n"
                f"This may indicate operational delays or increased security"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            confidence=0.6,
            metadata={
                'vessel_count': len(vessels),
                'vessel_ids': [v.get('id') for v in vessels[:10]],
                'chokepoint_id': list(self.CHOKEPOINTS.keys())[list(self.CHOKEPOINTS.values()).index(chokepoint)],
                'avg_daily_transits': chokepoint['avg_daily_tanker_transits'],
                'anomaly_type': 'high_density'
            }
        )

    def _create_deviation_event(
        self,
        vessel: Dict[str, Any],
        chokepoint: Dict[str, Any]
    ) -> InterventionEvent:
        """Create event for route deviation"""
        return InterventionEvent(
            source=f"AIS ({self.api_provider})",
            event_type="maritime_anomaly",
            title=f"Route Deviation in {chokepoint['name']}",
            description=(
                f"Tanker deviating from typical route through chokepoint.\n"
                f"Vessel: {vessel.get('name', 'Unknown')}\n"
                f"Position: {vessel.get('lat', 0):.4f}, {vessel.get('lon', 0):.4f}\n"
                f"Deviation: {vessel.get('deviation', 0):.1f} km\n"
                f"Destination: {vessel.get('destination', 'Unknown')}\n"
                f"Chokepoint: {chokepoint['name']}"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(vessel.get('lat', 0), vessel.get('lon', 0)),
            confidence=0.5,
            metadata={
                'vessel_id': vessel.get('id'),
                'vessel_name': vessel.get('name'),
                'deviation_km': vessel.get('deviation', 0),
                'destination': vessel.get('destination'),
                'chokepoint_id': list(self.CHOKEPOINTS.keys())[list(self.CHOKEPOINTS.values()).index(chokepoint)],
                'anomaly_type': 'deviation'
            }
        )

    # Simulated event generators for testing
    def _create_simulated_stopped_tanker(self, chokepoint: Dict[str, Any]) -> InterventionEvent:
        import random

        bbox = chokepoint['bbox']
        lat = random.uniform(bbox['min_lat'], bbox['max_lat'])
        lon = random.uniform(bbox['min_lon'], bbox['max_lon'])

        return InterventionEvent(
            source="AIS (Simulated)",
            event_type="maritime_anomaly",
            title=f"[SIM] Tanker Stopped in {chokepoint['name']}",
            description=(
                f"SIMULATED: Tanker vessel has stopped moving in critical chokepoint.\n"
                f"Vessel: SIM_TANKER_{random.randint(1000, 9999)}\n"
                f"Position: {lat:.4f}, {lon:.4f}\n"
                f"Speed: 0.0 knots\n"
                f"Duration: 5400 seconds (1.5 hours)\n"
                f"Chokepoint: {chokepoint['name']}\n"
                f"Width: {chokepoint['width_km']} km"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(lat, lon),
            confidence=0.7,
            metadata={
                'vessel_id': f'SIM_{random.randint(1000, 9999)}',
                'vessel_name': f'SIM_TANKER_{random.randint(1000, 9999)}',
                'vessel_type': 'Oil Tanker',
                'speed': 0.0,
                'stop_duration': 5400,
                'chokepoint': chokepoint['name'],
                'anomaly_type': 'stopped_tanker',
                'simulated': True
            }
        )

    def _create_simulated_military_vessel(self, chokepoint: Dict[str, Any]) -> InterventionEvent:
        import random

        bbox = chokepoint['bbox']
        lat = random.uniform(bbox['min_lat'], bbox['max_lat'])
        lon = random.uniform(bbox['min_lon'], bbox['max_lon'])

        return InterventionEvent(
            source="AIS (Simulated)",
            event_type="military_activity",
            title=f"[SIM] Military Vessel in {chokepoint['name']}",
            description=(
                f"SIMULATED: Military vessel detected in critical chokepoint.\n"
                f"Vessel: SIM_MILITARY_{random.randint(1000, 9999)}\n"
                f"Type: Frigate\n"
                f"Position: {lat:.4f}, {lon:.4f}\n"
                f"Speed: {random.uniform(10, 20):.1f} knots\n"
                f"Chokepoint: {chokepoint['name']}\n"
                f"Width: {chokepoint['width_km']} km"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(lat, lon),
            confidence=0.8,
            metadata={
                'vessel_id': f'SIM_MIL_{random.randint(1000, 9999)}',
                'vessel_name': f'SIM_MILITARY_{random.randint(1000, 9999)}',
                'vessel_type': 'Frigate',
                'speed': random.uniform(10, 20),
                'chokepoint': chokepoint['name'],
                'anomaly_type': 'military_vessel',
                'simulated': True
            }
        )

    def _create_simulated_deviation(self, chokepoint: Dict[str, Any]) -> InterventionEvent:
        import random

        bbox = chokepoint['bbox']
        lat = random.uniform(bbox['min_lat'], bbox['max_lat'])
        lon = random.uniform(bbox['min_lon'], bbox['max_lon'])

        return InterventionEvent(
            source="AIS (Simulated)",
            event_type="maritime_anomaly",
            title=f"[SIM] Route Deviation in {chokepoint['name']}",
            description=(
                f"SIMULATED: Tanker deviating from typical route through chokepoint.\n"
                f"Vessel: SIM_TANKER_{random.randint(1000, 9999)}\n"
                f"Position: {lat:.4f}, {lon:.4f}\n"
                f"Deviation: {random.uniform(10, 20):.1f} km\n"
                f"Destination: Rotterdam\n"
                f"Chokepoint: {chokepoint['name']}"
            ),
            timestamp=datetime.now(),
            location=chokepoint['name'],
            coordinates=(lat, lon),
            confidence=0.5,
            metadata={
                'vessel_id': f'SIM_{random.randint(1000, 9999)}',
                'vessel_name': f'SIM_TANKER_{random.randint(1000, 9999)}',
                'deviation_km': random.uniform(10, 20),
                'destination': 'Rotterdam',
                'chokepoint': chokepoint['name'],
                'anomaly_type': 'deviation',
                'simulated': True
            }
        )

    # Helper methods
    def _is_tanker(self, vessel: Dict[str, Any]) -> bool:
        """Check if vessel is a tanker"""
        vessel_type = vessel.get('type', '').lower()
        return any(t.lower() in vessel_type for t in self.VESSEL_TYPES_ENERGY)

    def _is_military_vessel(self, vessel: Dict[str, Any]) -> bool:
        """Check if vessel is military"""
        vessel_type = vessel.get('type', '').lower()
        return 'military' in vessel_type or 'navy' in vessel_type or 'frigate' in vessel_type

    def _is_vessel_stopped(self, vessel: Dict[str, Any]) -> bool:
        """Check if vessel has stopped moving"""
        speed = vessel.get('speed', 0)
        stop_duration = vessel.get('stop_duration', 0)
        return speed < 0.5 and stop_duration > self.ALERT_CONDITIONS['stopped_tanker']['stop_duration_threshold']

    def _has_route_deviation(self, vessel: Dict[str, Any]) -> bool:
        """Check if vessel has deviated from route"""
        deviation = vessel.get('deviation', 0)
        return deviation > self.ALERT_CONDITIONS['deviation']['deviation_threshold']


# Add random import for simulated events
import random
