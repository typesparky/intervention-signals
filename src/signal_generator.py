#!/usr/bin/env python3
"""
Signal Generator - Analyze events and generate intervention signals
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generate intervention signals from geopolitical/military events"""
    
    def _default_thresholds(self) -> Dict:
        """Default signal generation thresholds"""
        return {
            'keyword_match_score': 0.7,
            'multiple_sources_bonus': 0.2,
            'priority_weight': {'high': 1.0, 'medium': 0.7, 'low': 0.4},
            'alert_threshold': 0.8,
            'time_window_minutes': 60  # Time window for correlating events
        }
    
    def __init__(self, db_path: str = '/root/intervention_signal_system/data/events.db', 
                 thresholds: Dict = None):
        self.db_path = db_path
        self.thresholds = thresholds or self._default_thresholds()
    
    def generate_signals(self) -> List[Dict]:
        """Generate intervention signals from unprocessed events"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get unprocessed events
        cursor.execute('''
            SELECT * FROM events 
            WHERE processed = FALSE 
            ORDER BY priority_score DESC, published DESC
            LIMIT 200
        ''')
        
        events = [dict(row) for row in cursor.fetchall()]
        
        if not events:
            logger.info("No unprocessed events to analyze")
            conn.close()
            return []
        
        logger.info(f"Analyzing {len(events)} events for signals")
        
        # Group events by time windows
        time_groups = self._group_by_time(events)
        
        # Generate signals for each time group
        signals = []
        event_ids_to_mark = []
        
        for timestamp, group_events in time_groups.items():
            group_signals = self._analyze_event_group(group_events)
            signals.extend(group_signals)
            event_ids_to_mark.extend([e['id'] for e in group_events])
        
        # Store high-confidence signals
        for signal in signals:
            if signal['confidence'] >= self.thresholds['alert_threshold']:
                self._store_signal(conn, signal)
        
        # Mark events as processed
        if event_ids_to_mark:
            cursor.executemany(
                'UPDATE events SET processed = TRUE, signal_score = ? WHERE id = ?',
                [(s['confidence'], eid) for s, eid in zip(signals, event_ids_to_mark)]
            )
            conn.commit()
        
        conn.close()
        
        logger.info(f"Generated {len(signals)} signals, stored {len([s for s in signals if s['confidence'] >= self.thresholds['alert_threshold']])}")
        
        return signals
    
    def _group_by_time(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by time windows for correlation analysis"""
        groups = defaultdict(list)
        window_minutes = self.thresholds['time_window_minutes']
        
        for event in events:
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(event['published'].replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except:
                timestamp = datetime.now(timezone.utc)
            
            # Round to nearest window
            window_start = timestamp - timedelta(
                minutes=timestamp.minute % window_minutes,
                seconds=timestamp.second,
                microseconds=timestamp.microsecond
            )
            window_key = window_start.isoformat()
            
            groups[window_key].append(event)
        
        return dict(groups)
    
    def _analyze_event_group(self, events: List[Dict]) -> List[Dict]:
        """Analyze a group of events within a time window"""
        if not events:
            return []
        
        signals = []
        
        # Calculate base scores for each event
        for event in events:
            signal = {
                'event_id': event['id'],
                'signal_type': self._determine_signal_type(event),
                'confidence': self._calculate_confidence(event, events),
                'sources_involved': [e['source'] for e in events],
                'title': event['title'],
                'summary': event['summary'],
                'url': event['url'],
                'published': event['published'],
                'source': event['source']
            }
            signals.append(signal)
        
        return signals
    
    def _determine_signal_type(self, event: Dict) -> str:
        """Determine the type of intervention signal"""
        title = event['title'].lower()
        summary = event['summary'].lower()
        combined = title + ' ' + summary
        
        # Military action keywords
        military_keywords = [
            'airstrike', 'strike', 'attack', 'bombing', 'missile', 
            'combat', 'firefight', 'assault', 'invasion'
        ]
        if any(kw in combined for kw in military_keywords):
            return 'military_action'
        
        # Deployment keywords
        deployment_keywords = [
            'deploy', 'troop', 'forces', 'dispatch', 'send', 'movement'
        ]
        if any(kw in combined for kw in deployment_keywords):
            return 'force_deployment'
        
        # Tension/escalation keywords
        tension_keywords = [
            'escalate', 'tension', 'standoff', 'conflict', 'clash', 
            'skirmish', 'border', 'confrontation'
        ]
        if any(kw in combined for kw in tension_keywords):
            return 'tension_escalation'
        
        # Exercise/drill keywords
        exercise_keywords = [
            'exercise', 'drill', 'training', 'maneuver', 'simulation'
        ]
        if any(kw in combined for kw in exercise_keywords):
            return 'military_exercise'
        
        # Diplomatic keywords
        diplomatic_keywords = [
            'summit', 'meeting', 'talks', 'negotiation', 'agreement', 'deal'
        ]
        if any(kw in combined for kw in diplomatic_keywords):
            return 'diplomatic_activity'
        
        return 'geopolitical_event'
    
    def _calculate_confidence(self, event: Dict, all_events: List[Dict]) -> float:
        """Calculate confidence score for an event"""
        score = 0.0
        
        # 1. Base score from source priority
        priority_scores = self.thresholds['priority_weight']
        source_priority = event.get('priority_score', 0.5)
        score += source_priority * 0.4
        
        # 2. Keyword matching bonus
        title = event['title'].lower()
        summary = event['summary'].lower()
        combined = title + ' ' + summary
        
        # High-impact keywords
        high_impact_keywords = [
            'airstrike', 'strike', 'attack', 'bombing', 'casualties',
            'deployment', 'invasion', 'escalation', 'emergency'
        ]
        
        keyword_matches = sum(1 for kw in high_impact_keywords if kw in combined)
        if keyword_matches > 0:
            score += min(keyword_matches * 0.15, 0.3)
        
        # 3. Multiple sources bonus (corroboration)
        unique_sources = set(e['source'] for e in all_events)
        if len(unique_sources) > 1:
            score += self.thresholds['multiple_sources_bonus'] * min(len(unique_sources), 3)
        
        # 4. Recency bonus (more recent = higher score)
        try:
            published = datetime.fromisoformat(event['published'].replace('Z', '+00:00'))
            hours_ago = (datetime.now(timezone.utc) - published).total_seconds() / 3600
            if hours_ago < 1:
                score += 0.1
            elif hours_ago < 6:
                score += 0.05
        except:
            pass
        
        # 5. Signal type adjustment
        signal_type = self._determine_signal_type(event)
        type_bonuses = {
            'military_action': 0.15,
            'force_deployment': 0.12,
            'tension_escalation': 0.10,
            'military_exercise': 0.05,
            'diplomatic_activity': 0.05,
            'geopolitical_event': 0.0
        }
        score += type_bonuses.get(signal_type, 0.0)
        
        # Ensure score is between 0 and 1
        return min(max(score, 0.0), 1.0)
    
    def _store_signal(self, conn: sqlite3.Connection, signal: Dict):
        """Store a signal in the database"""
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals (event_id, signal_type, confidence, sources_involved)
            VALUES (?, ?, ?, ?)
        ''', (
            signal['event_id'],
            signal['signal_type'],
            signal['confidence'],
            json.dumps(signal['sources_involved'])
        ))
        
        conn.commit()
    
    def get_alert_signals(self, min_hours: int = 6) -> List[Dict]:
        """Get high-confidence signals from the last N hours"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=min_hours)
        cutoff_str = cutoff.isoformat()
        
        cursor.execute('''
            SELECT s.*, e.title, e.summary, e.url, e.published, e.source
            FROM signals s
            JOIN events e ON s.event_id = e.id
            WHERE s.created_at > ? AND s.confidence >= ?
            ORDER BY s.confidence DESC, s.created_at DESC
        ''', (cutoff_str, self.thresholds['alert_threshold']))
        
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return signals
    
    def get_signal_summary(self, hours: int = 24) -> Dict:
        """Get a summary of recent signals"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        summary = {
            'period_hours': hours,
            'total_signals': 0,
            'high_confidence': 0,
            'by_type': defaultdict(int),
            'by_source': defaultdict(int)
        }
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        cursor.execute('''
            SELECT s.*, e.source
            FROM signals s
            JOIN events e ON s.event_id = e.id
            WHERE s.created_at > ?
        ''', (cutoff_str,))
        
        for row in cursor.fetchall():
            summary['total_signals'] += 1
            signal = dict(row)
            
            if signal['confidence'] >= self.thresholds['alert_threshold']:
                summary['high_confidence'] += 1
            
            summary['by_type'][signal['signal_type']] += 1
            summary['by_source'][signal['source']] += 1
        
        conn.close()
        
        # Convert defaultdicts to regular dicts
        summary['by_type'] = dict(summary['by_type'])
        summary['by_source'] = dict(summary['by_source'])
        
        return summary


if __name__ == '__main__':
    # Test signal generation
    generator = SignalGenerator()
    
    # Generate signals
    signals = generator.generate_signals()
    print(f"\nGenerated {len(signals)} signals")
    
    # Get high-confidence alerts
    alerts = generator.get_alert_signals(min_hours=6)
    print(f"\nHigh-confidence alerts (last 6 hours): {len(alerts)}")
    for alert in alerts[:5]:
        print(f"  - [{alert['signal_type']}] {alert['title']} (confidence: {alert['confidence']:.2f})")
    
    # Get summary
    summary = generator.get_signal_summary(hours=24)
    print(f"\n24-hour summary:")
    print(f"  Total signals: {summary['total_signals']}")
    print(f"  High confidence: {summary['high_confidence']}")
    print(f"  By type: {summary['by_type']}")
