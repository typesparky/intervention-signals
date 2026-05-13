"""
RSS feed adapter for intervention signal system
"""
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_feed_adapter import BaseFeedAdapter, InterventionEvent


class RSSFeedAdapter(BaseFeedAdapter):
    """Adapter for RSS/Atom feeds"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.feed_type = "rss"

    def fetch_events(self) -> List[InterventionEvent]:
        """Fetch and parse RSS feed entries"""
        try:
            feed = feedparser.parse(self.url)

            if feed.bozo:
                print(f"Warning: Feed parse error for {self.name}: {feed.bozo_exception}")

            events = []

            for entry in feed.entries:
                # Parse timestamp
                timestamp = self._parse_timestamp(entry)

                # Extract content
                title = entry.get('title', '')
                description = entry.get('description', '')
                summary = entry.get('summary', '')
                content = entry.get('content', [{}])[0].get('value', '')

                # Use the most descriptive content
                full_description = description or summary or content

                # Determine event type based on keywords
                event_type = self._classify_event(title + full_description)

                # Create event
                event = InterventionEvent(
                    source=self.name,
                    event_type=event_type,
                    title=title,
                    description=full_description,
                    timestamp=timestamp,
                    confidence=self._calculate_confidence(title, full_description),
                    metadata={
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'author': entry.get('author', ''),
                        'tags': [tag.get('term') for tag in entry.get('tags', [])]
                    }
                )

                if self.is_event_relevant(event):
                    events.append(event)

            return events

        except Exception as e:
            print(f"Error fetching RSS feed from {self.name}: {e}")
            return []

    def _parse_timestamp(self, entry) -> datetime:
        """Parse timestamp from feed entry"""
        timestamp_fields = ['published_parsed', 'updated_parsed']

        for field in timestamp_fields:
            if field in entry and entry[field]:
                try:
                    return datetime(*entry[field][:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue

        return datetime.now(timezone.utc)

    def _classify_event(self, text: str) -> str:
        """Classify event type based on content"""
        text_lower = text.lower()

        # Military operations
        military_keywords = ['military operation', 'deployment', 'exercise', 'drill']
        if any(kw in text_lower for kw in military_keywords):
            return 'military_operation'

        # Conflict/Attack
        conflict_keywords = ['attack', 'strike', 'airstrike', 'clash', 'fire', 'explosion']
        if any(kw in text_lower for kw in conflict_keywords):
            return 'conflict'

        # Diplomatic
        diplomatic_keywords = ['diplomatic', 'sanctions', 'talks', 'meeting', 'summit']
        if any(kw in text_lower for kw in diplomatic_keywords):
            return 'diplomatic'

        # Escalation
        escalation_keywords = ['escalation', 'tension', 'crisis', 'emergency']
        if any(kw in text_lower for kw in escalation_keywords):
            return 'escalation'

        return 'general'

    def _calculate_confidence(self, title: str, description: str) -> float:
        """Calculate confidence score for the event"""
        score = 0.5  # Base score

        # Higher confidence for longer titles/descriptions
        if len(title) > 20:
            score += 0.1

        if len(description) > 100:
            score += 0.1

        # Check for authoritative sources in description
        if 'official' in description.lower() or 'confirmed' in description.lower():
            score += 0.15

        return min(score, 1.0)
