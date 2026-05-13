"""
GDELT event database adapter for intervention signal system
"""
import requests
from typing import List, Dict, Any
from datetime import datetime, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_feed_adapter import BaseFeedAdapter, InterventionEvent


class GDELTAdapter(BaseFeedAdapter):
    """Adapter for GDELT Event Database API"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.feed_type = "api"
        self.event_codes = config.get('event_codes', [])
        self.params = config.get('params', {})

    def fetch_events(self) -> List[InterventionEvent]:
        """Fetch events from GDELT API"""
        try:
            params = {
                'query': self.params.get('query', ''),
                'format': 'json',
                'mode': 'artlist',
                'maxrecords': 50
            }

            response = requests.get(self.url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'articles' not in data:
                return []

            events = []
            for article in data['articles'][:50]:  # Limit to 50 articles
                try:
                    event = InterventionEvent(
                        source=self.name,
                        event_type=self._classify_gdelt_event(article),
                        title=article.get('title', ''),
                        description=article.get('seendate', '') + ': ' + article.get('url', ''),
                        timestamp=self._parse_gdelt_date(article.get('seendate', '')),
                        confidence=0.7,  # GDELT is generally reliable
                        metadata={
                            'url': article.get('url', ''),
                            'domain': article.get('domain', ''),
                            'language': article.get('language', ''),
                            'tone': article.get('tone', 0),
                            'event_code': article.get('eventcode', '')
                        }
                    )

                    if self.is_event_relevant(event):
                        events.append(event)

                except Exception as e:
                    print(f"Error processing GDELT article: {e}")
                    continue

            return events

        except Exception as e:
            print(f"Error fetching GDELT data: {e}")
            return []

    def _classify_gdelt_event(self, article: Dict[str, Any]) -> str:
        """Classify event based on GDELT event codes and content"""
        event_code = article.get('eventcode', '')
        tone = article.get('tone', 0)

        # Check event codes
        if event_code in self.event_codes:
            return 'military_conflict'

        # Check tone (negative tone often indicates conflict)
        if tone < -2:
            return 'conflict'

        # Check title
        title = article.get('title', '').lower()
        if 'conflict' in title or 'war' in title or 'attack' in title:
            return 'conflict'

        return 'general'

    def _parse_gdelt_date(self, date_str: str) -> datetime:
        """Parse GDELT date format (YYYYMMDDHHMMSS)"""
        try:
            # GDELT format: YYYYMMDDHHMMSS
            if len(date_str) >= 14:
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                hour = int(date_str[8:10]) if len(date_str) >= 10 else 0
                minute = int(date_str[10:12]) if len(date_str) >= 12 else 0
                second = int(date_str[12:14]) if len(date_str) >= 14 else 0

                return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        except Exception as e:
            print(f"Error parsing GDELT date: {e}")

        return datetime.now(timezone.utc)
