"""
ACLED (Armed Conflict Location & Event Data) adapter
Uses OAuth authentication for secure API access
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time

from base_feed_adapter import BaseFeedAdapter, InterventionEvent


class ACLEDAdapter(BaseFeedAdapter):
    """
    ACLED API adapter with OAuth authentication
    Focuses on conflict events that could impact energy markets
    """

    # ACLED API endpoints
    ACLED_API_URL = "https://api.acleddata.com/api/acled/read"
    OAUTH_TOKEN_URL = "https://acleddata.com/oauth/token"
    REFRESH_TOKEN_URL = "https://acleddata.com/oauth/token"

    # Event codes for conflict types
    # See: https://acleddata.com/data/codebook/
    EVENT_TYPES_CONFLICT = [
        'Battles',  # Military battles
        'Violence against civilians',  # Attacks on civilians
        'Explosions/Remote violence',  # IEDs, shelling, airstrikes
        'Riots',  # Civil unrest
        'Protests',  # Can indicate instability
    ]

    # Actor types of interest
    ACTOR_TYPES_ENERGY_RELEVANT = [
        'Military Forces of State',  # Regular military
        'Rebel Forces',  # Insurgent groups
        'Political Militias',  # Armed political groups
        'Terrorist Organizations',  # Designated terrorist groups
        'External Forces/Others',  # Foreign military/interventions
    ]

    # Regions of interest for energy markets
    ENERGY_REGIONS = {
        'middle_east': {
            'name': 'Middle East',
            'countries': ['Saudi Arabia', 'Iran', 'Iraq', 'Kuwait', 'UAE', 'Qatar',
                         'Oman', 'Yemen', 'Syria', 'Jordan', 'Lebanon', 'Israel'],
            'keywords': ['refinery', 'pipeline', 'oil', 'gas', 'petroleum', 'energy',
                        'tanker', 'terminal', 'port', 'facility', 'plant', 'export',
                        'hormuz', 'strait', 'shipping', 'naval']
        },
        'north_africa': {
            'name': 'North Africa',
            'countries': ['Algeria', 'Libya', 'Egypt', 'Tunisia', 'Morocco', 'Sudan'],
            'keywords': ['refinery', 'pipeline', 'oil', 'gas', 'energy', 'terminal',
                        'port', 'plant', 'export']
        },
        'hormuz_bab_mandeb': {
            'name': 'Strategic Chokepoints',
            'countries': ['Yemen', 'Oman', 'Iran', 'Eritrea', 'Djibouti', 'Somalia', 'Sudan'],
            'keywords': ['ship', 'tanker', 'vessel', 'naval', 'missile', 'attack',
                        'hijack', 'seizure', 'blockade', 'strait', 'chokepoint',
                        'bab el-mandeb', 'hormuz', 'red sea', 'gulf of aden']
        }
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # OAuth credentials (username/email and password)
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        
        # API configuration
        self.api_version = config.get('api_version', '2.0')
        self.lookback_days = config.get('lookback_days', 3)
        self.fatalities_threshold = config.get('fatalities_threshold', 5)
        self.include_all_events = config.get('include_all_events', False)
        
        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        if not self.username or not self.password:
            print("WARNING: ACLED credentials not provided. Need username and password.")
        else:
            # Get initial token
            self._authenticate()

    def _authenticate(self):
        """
        Authenticate with ACLED API using OAuth
        Returns access token valid for 24 hours
        """
        if not self.username or not self.password:
            return False
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password',
            'client_id': 'acled',
            'scope': 'authenticated'
        }
        
        try:
            response = requests.post(self.OAUTH_TOKEN_URL, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 86400)  # Default 24 hours
                
                # Calculate expiration time
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                print(f"✓ ACLED authenticated successfully. Token expires in {expires_in//3600} hours")
                return True
            else:
                print(f"ERROR: ACLED authentication failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"ERROR: ACLED authentication exception: {e}")
            return False
    
    def _refresh_token(self):
        """
        Refresh access token using refresh token
        """
        if not self.refresh_token:
            return self._authenticate()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        data = {
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token',
            'client_id': 'acled'
        }
        
        try:
            response = requests.post(self.REFRESH_TOKEN_URL, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token', self.refresh_token)
                expires_in = token_data.get('expires_in', 86400)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                print("✓ ACLED token refreshed successfully")
                return True
            else:
                print(f"ERROR: ACLED token refresh failed: {response.status_code}")
                return self._authenticate()  # Fall back to full authentication
                
        except Exception as e:
            print(f"ERROR: ACLED token refresh exception: {e}")
            return self._authenticate()

    def _ensure_authenticated(self):
        """
        Ensure we have a valid access token
        Refreshes if expired
        """
        if not self.access_token:
            return self._authenticate()
        
        # Check if token is expired (with 5 minute buffer)
        if datetime.now() >= self.token_expires_at - timedelta(minutes=5):
            return self._refresh_token()
        
        return True
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authorization headers for API requests
        """
        if not self._ensure_authenticated():
            return {}
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def fetch_events(self) -> List[InterventionEvent]:
        """
        Fetch recent conflict events from ACLED
        Focuses on energy-relevant conflicts
        """
        events = []
        
        if not self.username or not self.password:
            print("  ERROR: ACLED credentials required")
            return events
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)
        
        # Query ACLED for each region
        for region_id, region_info in self.ENERGY_REGIONS.items():
            try:
                # Build API request parameters
                params = {
                    'format': 'json',
                    'country': '|OR:'.join(region_info['countries']),
                    'event_date': f'{start_date.strftime("%Y-%m-%d")}|{end_date.strftime("%Y-%m-%d")}',
                    'event_date_where': 'BETWEEN',
                    'limit': 1000  # Limit per region to avoid rate limits
                }
                
                # Add fatalities filter if configured
                if not self.include_all_events:
                    params['fatalities'] = f'>={self.fatalities_threshold}'
                
                # Make authenticated request
                response = requests.get(
                    self.ACLED_API_URL,
                    params=params,
                    headers=self._get_auth_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data and isinstance(data['data'], list):
                        for event_data in data['data']:
                            # Filter for energy-relevant events
                            if self._is_energy_relevant(event_data, region_info['keywords']):
                                event = self._parse_event(event_data, region_info['name'])
                                if event:
                                    events.append(event)
                    
                    print(f"  Fetched {len(data.get('data', []))} events from {region_info['name']}")
                elif response.status_code == 401:
                    print(f"  ERROR: ACLED authentication expired, refreshing...")
                    self._refresh_token()
                    # Retry once with new token
                    response = requests.get(
                        self.ACLED_API_URL,
                        params=params,
                        headers=self._get_auth_headers()
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data:
                            for event_data in data['data']:
                                if self._is_energy_relevant(event_data, region_info['keywords']):
                                    event = self._parse_event(event_data, region_info['name'])
                                    if event:
                                        events.append(event)
                else:
                    print(f"  ERROR: ACLED API returned {response.status_code}")
                    
            except Exception as e:
                print(f"  ERROR fetching ACLED data for {region_info['name']}: {e}")
        
        print(f"  Total ACLED events fetched: {len(events)}")
        return events
    
    def _is_energy_relevant(self, event_data: Dict, keywords: List[str]) -> bool:
        """
        Check if event is relevant to energy infrastructure or markets
        """
        # Check keywords in notes
        notes = str(event_data.get('notes', '')).lower()
        for keyword in keywords:
            if keyword.lower() in notes:
                return True
        
        # Check keywords in actor names
        actor1 = str(event_data.get('actor1', '')).lower()
        actor2 = str(event_data.get('actor2', '')).lower()
        for keyword in keywords:
            if keyword.lower() in actor1 or keyword.lower() in actor2:
                return True
        
        # Check if actor is energy-relevant type
        actor1_type = str(event_data.get('assoc_actor_1', '')).lower()
        actor2_type = str(event_data.get('assoc_actor_2', '')).lower()
        
        for actor_type in self.ACTOR_TYPES_ENERGY_RELEVANT:
            if actor_type.lower() in actor1_type or actor_type.lower() in actor2_type:
                return True
        
        # If not filtering strictly, include all events from these regions
        if self.include_all_events:
            return True
        
        return False
    
    def _parse_event(self, event_data: Dict, region_name: str) -> Optional[InterventionEvent]:
        """
        Parse ACLED event data into InterventionEvent
        """
        try:
            # Extract event details
            event_date = event_data.get('event_date', '')
            event_type = event_data.get('event_type', '')
            sub_event_type = event_data.get('sub_event_type', '')
            
            # Extract actors
            actor1 = event_data.get('actor1', '')
            actor2 = event_data.get('actor2', '')
            
            # Extract location
            country = event_data.get('country', '')
            location = event_data.get('location', '')
            latitude = event_data.get('latitude', '')
            longitude = event_data.get('longitude', '')
            
            # Extract fatalities
            fatalities = event_data.get('fatalities', 0)
            
            # Extract notes (contains event description)
            notes = event_data.get('notes', '')
            
            # Calculate confidence based on fatalities
            base_confidence = 0.5
            if fatalities >= 10:
                base_confidence += 0.3
            elif fatalities >= 5:
                base_confidence += 0.2
            elif fatalities > 0:
                base_confidence += 0.1
            
            # Determine signal type
            signal_type = self._determine_signal_type(event_type, sub_event_type)
            
            # Create event
            event = InterventionEvent(
                source=f"ACLED ({region_name})",
                event_type=signal_type,
                title=f"{event_type}: {actor1}" + (f" vs {actor2}" if actor2 else ""),
                description=notes,
                timestamp=self._parse_date(event_date),
                location=location,
                coordinates=(float(latitude), float(longitude)) if latitude and longitude else None,
                confidence=min(base_confidence, 1.0),
                metadata={
                    'event_type': event_type,
                    'sub_event_type': sub_event_type,
                    'actor1': actor1,
                    'actor2': actor2,
                    'country': country,
                    'fatalities': fatalities,
                    'disorder_type': event_data.get('disorder_type', ''),
                    'interaction': event_data.get('interaction', ''),
                    'source': event_data.get('source', ''),
                    'notes': notes
                }
            )
            
            return event
            
        except Exception as e:
            print(f"  ERROR parsing ACLED event: {e}")
            return None
    
    def _determine_signal_type(self, event_type: str, sub_event_type: str) -> str:
        """
        Map ACLED event types to signal types
        """
        event_type_lower = event_type.lower()
        
        if 'battle' in event_type_lower or 'explosion' in event_type_lower:
            return 'military_action'
        elif 'violence against civilians' in event_type_lower:
            return 'military_action'
        elif 'riot' in event_type_lower:
            return 'tension_escalation'
        elif 'protest' in event_type_lower:
            return 'tension_escalation'
        else:
            return 'geopolitical_event'
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse date string from ACLED format
        """
        try:
            # ACLED dates are typically YYYY-MM-DD
            return datetime.strptime(date_str[:10], '%Y-%m-%d')
        except:
            return datetime.now()
