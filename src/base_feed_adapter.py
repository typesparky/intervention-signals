"""
Base feed adapter for intervention signal system
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class InterventionEvent:
    """Represents a detected intervention signal"""
    def __init__(
        self,
        source: str,
        event_type: str,
        title: str,
        description: str,
        timestamp: datetime,
        location: Optional[str] = None,
        coordinates: Optional[tuple] = None,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.source = source
        self.event_type = event_type
        self.title = title
        self.description = description
        self.timestamp = timestamp
        self.location = location
        self.coordinates = coordinates  # (lat, lon)
        self.confidence = confidence  # 0.0 to 1.0
        self.metadata = metadata or {}
        self.related_markets = []  # Will be populated by signal analyzer

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'source': self.source,
            'event_type': self.event_type,
            'title': self.title,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'location': self.location,
            'coordinates': self.coordinates,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'related_markets': self.related_markets
        }

    def __repr__(self):
        return f"InterventionEvent({self.source}, {self.event_type}, {self.title[:30]}...)"


class BaseFeedAdapter(ABC):
    """Abstract base class for all feed adapters"""

    def __init__(self, config: Dict[str, Any]):
        self.name = config.get('name', 'Unknown')
        self.url = config.get('url')
        self.update_interval = config.get('update_interval', 300)
        self.priority = config.get('priority', 'medium')
        self.last_fetch = None
        self.keywords = config.get('keywords', [])

    @abstractmethod
    def fetch_events(self) -> List[InterventionEvent]:
        """Fetch and parse events from the feed source"""
        pass

    def is_event_relevant(self, event: InterventionEvent) -> bool:
        """Check if event matches keyword criteria"""
        if not self.keywords:
            return True

        text = f"{event.title} {event.description}".lower()
        return any(keyword.lower() in text for keyword in self.keywords)

    def deduplicate_events(
        self,
        events: List[InterventionEvent],
        seen_hashes: set
    ) -> List[InterventionEvent]:
        """Remove duplicate events based on content hash"""
        new_events = []
        for event in events:
            # Create a hash based on title, description, and source
            content = f"{event.source}:{event.title}:{event.description}"
            event_hash = hash(content)

            if event_hash not in seen_hashes:
                seen_hashes.add(event_hash)
                new_events.append(event)

        return new_events
