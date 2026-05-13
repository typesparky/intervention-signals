"""
NASA FIRMS (Fire Information for Resource Management System) adapter
Monitors heat signatures for refinery/pipeline infrastructure
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time

from base_feed_adapter import BaseFeedAdapter, InterventionEvent


class FIRMSAdapter(BaseFeedAdapter):
    """
    NASA FIRMS API adapter for monitoring thermal anomalies
    at critical infrastructure sites (refineries, pipelines)
    """

    # NASA FIRMS API endpoints
    FIRMS_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/country/csv"
    FIRMS_AREA_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    # Critical infrastructure coordinates (lat, lon, radius_km)
    # Refineries, pipelines, and key energy infrastructure
    INFRASTRUCTURE_SITES = {
        # Middle East Refineries
        "ras_tanura": {"lat": 26.64, "lon": 50.03, "radius": 10, "name": "Ras Tanura Refinery (Saudi Arabia)"},
        "jubail": {"lat": 27.02, "lon": 49.66, "radius": 15, "name": "Jubail Industrial City (Saudi Arabia)"},
        "yanbu": {"lat": 24.09, "lon": 38.03, "radius": 10, "name": "Yanbu Refinery (Saudi Arabia)"},
        "ruwais": {"lat": 24.10, "lon": 52.73, "radius": 10, "name": "Ruwais Refinery (UAE)"},
        "fujairah": {"lat": 25.12, "lon": 56.33, "radius": 15, "name": "Fujairah Oil Terminal (UAE)"},
        "kharg_island": {"lat": 29.23, "lon": 50.33, "radius": 15, "name": "Kharg Island Terminal (Iran)"},

        # Pipeline Corridors
        "east_west_pipeline": {"lat": 25.00, "lon": 45.00, "radius": 50, "name": "East-West Pipeline (Saudi Arabia)"},
        "kirkuk_ceyhan": {"lat": 35.00, "lon": 43.00, "radius": 30, "name": "Kirkuk-Ceyhan Pipeline Corridor"},

        # Strait of Hormuz Infrastructure
        "hormuz_terminals": {"lat": 26.50, "lon": 54.50, "radius": 20, "name": "Strait of Hormuz Terminals"},

        # Bab el-Mandeb Area
        "bab_el_mandeb": {"lat": 12.70, "lon": 43.40, "radius": 25, "name": "Bab el-Mandeb Shipping Lane"},

        # North Africa Refineries
        "skikda": {"lat": 36.88, "lon": 6.91, "radius": 10, "name": "Skikda Refinery (Algeria)"},
        "arzew": {"lat": 35.86, "lon": 0.28, "radius": 10, "name": "Arzew Complex (Algeria)"},

        # Red Sea Infrastructure
        "jeddah": {"lat": 21.50, "lon": 39.18, "radius": 15, "name": "Jeddah Refinery (Saudi Arabia)"},
        "yanbu_port": {"lat": 24.00, "lon": 38.00, "radius": 15, "name": "Yanbu Port Facilities (Saudi Arabia)"},
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.satellite_source = config.get('satellite_source', 'MODIS_NRT')
        self.confidence_threshold = config.get('confidence_threshold', 75)  # 75-100%
        self.infrastructure_override = config.get('infrastructure_override', {})
        self.max_fire_age_hours = config.get('max_fire_age_hours', 24)

        # Merge custom infrastructure sites with defaults
        if 'custom_sites' in config:
            self.INFRASTRUCTURE_SITES.update(config['custom_sites'])

        if not self.api_key:
            print("WARNING: NASA FIRMS API key not provided. Get one from: https://earthdata.nasa.gov/")

    def fetch_events(self) -> List[InterventionEvent]:
        """
        Fetch recent thermal anomalies from NASA FIRMS
        Returns events near critical infrastructure sites
        """
        events = []

        if not self.api_key:
            print("  ERROR: NASA FIRMS API key required")
            return events

        # Get date range for the last 24 hours
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=self.max_fire_age_hours)

        # Query FIRMS API for each infrastructure site
        for site_id, site_info in self.INFRASTRUCTURE_SITES.items():
            try:
                # Calculate bounding box
                radius = site_info['radius']
                lat = site_info['lat']
                lon = site_info['lon']

                # Approximate bounding box (1 degree ~ 111km)
                lat_delta = radius / 111.0
                lon_delta = radius / (111.0 * abs(lat) + 1)

                bbox = f"{lat-lon_delta},{lon-lat_delta},{lat+lon_delta},{lon+lon_delta}"

                # Build API request
                params = {
                    'api_key': self.api_key,
                    'satellite_source': self.satellite_source,
                    'bbox': bbox,
                    'date_range': f"{start_date.strftime('%Y-%m-%d')}T{start_date.strftime('%H:%M:%S')};{end_date.strftime('%Y-%m-%d')}T{end_date.strftime('%H:%M:%S')}",
                    'format': 'json'
                }

                # Make API request
                response = requests.get(
                    self.FIRMS_AREA_API_URL,
                    params=params,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()

                    # Parse fire detections
                    for fire in data:
                        event = self._parse_fire_event(fire, site_info)
                        if event:
                            events.append(event)

                elif response.status_code == 429:
                    print(f"  Rate limit exceeded for FIRMS API")
                    time.sleep(5)  # Wait before retrying

            except Exception as e:
                print(f"  Error fetching FIRMS data for {site_info['name']}: {e}")
                continue

        # Filter by confidence threshold
        events = [e for e in events if e.confidence >= (self.confidence_threshold / 100.0)]

        print(f"  Found {len(events)} thermal anomalies near infrastructure")
        return events

    def _parse_fire_event(
        self,
        fire: Dict[str, Any],
        site_info: Dict[str, Any]
    ) -> Optional[InterventionEvent]:
        """
        Parse a FIRMS fire detection into an InterventionEvent
        """
        try:
            # Extract fire data
            lat = float(fire.get('latitude', 0))
            lon = float(fire.get('longitude', 0))
            confidence = float(fire.get('confidence', 0)) / 100.0  # Normalize to 0-1
            brightness = float(fire.get('brightness', 0))
            frp = float(fire.get('frp', 0))  # Fire Radiative Power
            satellite = fire.get('satellite', 'Unknown')
            instrument = fire.get('instrument', 'Unknown')
            detected_at = datetime.strptime(
                fire.get('acq_date') + ' ' + fire.get('acq_time'),
                '%Y-%m-%d %H:%M:%S'
            )

            # Determine event type based on intensity
            if frp > 50 or brightness > 400:
                event_type = "critical_thermal_anomaly"
            elif frp > 20 or brightness > 350:
                event_type = "significant_thermal_anomaly"
            else:
                event_type = "thermal_anomaly"

            # Build title
            title = f"Thermal Anomaly Detected - {site_info['name']}"

            # Build description
            description = (
                f"NASA {satellite} detected thermal anomaly near {site_info['name']}.\n"
                f"Location: {lat:.4f}, {lon:.4f}\n"
                f"Confidence: {confidence:.0%}\n"
                f"Brightness: {brightness:.1f} K\n"
                f"Fire Radiative Power: {frp:.1f} MW\n"
                f"Instrument: {instrument}\n"
                f"Detected: {detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Distance from site center: ~{site_info.get('radius', 'N/A')} km"
            )

            # Calculate adjusted confidence based on fire intensity
            adjusted_confidence = min(confidence + (frp / 200.0), 1.0)

            # Create event
            event = InterventionEvent(
                source=f"NASA FIRMS ({satellite})",
                event_type=event_type,
                title=title,
                description=description,
                timestamp=detected_at,
                location=site_info['name'],
                coordinates=(lat, lon),
                confidence=adjusted_confidence,
                metadata={
                    'satellite': satellite,
                    'instrument': instrument,
                    'brightness': brightness,
                    'frp': frp,
                    'site_id': list(self.INFRASTRUCTURE_SITES.keys())[list(self.INFRASTRUCTURE_SITES.values()).index(site_info)],
                    'site_name': site_info['name'],
                    'site_center': (site_info['lat'], site_info['lon']),
                    'distance_km': site_info.get('radius', 'N/A'),
                    'fire_data': fire
                }
            )

            return event

        except Exception as e:
            print(f"  Error parsing fire event: {e}")
            return None

    def get_infrastructure_status(
        self,
        site_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current status of infrastructure sites
        Returns list of sites with recent thermal activity
        """
        if not self.api_key:
            return {}

        events = self.fetch_events()

        # Group events by site
        site_status = {}
        for event in events:
            site_name = event.metadata.get('site_name', 'Unknown')
            if site_name not in site_status:
                site_status[site_name] = {
                    'site_name': site_name,
                    'recent_anomalies': [],
                    'last_anomaly': None,
                    'max_intensity': 0.0
                }

            site_status[site_name]['recent_anomalies'].append({
                'timestamp': event.timestamp.isoformat(),
                'confidence': event.confidence,
                'event_type': event.event_type,
                'frp': event.metadata.get('frp', 0)
            })

            # Track last anomaly
            if (site_status[site_name]['last_anomaly'] is None or
                event.timestamp > datetime.fromisoformat(site_status[site_name]['last_anomaly'])):
                site_status[site_name]['last_anomaly'] = event.timestamp.isoformat()

            # Track max intensity
            frp = event.metadata.get('frp', 0)
            if frp > site_status[site_name]['max_intensity']:
                site_status[site_name]['max_intensity'] = frp

        return site_status
