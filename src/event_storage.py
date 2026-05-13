#!/usr/bin/env python3
"""
Event Storage - SQLite database for storing geopolitical/military events
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class EventStorage:
    """SQLite database for storing events"""
    
    def __init__(self, db_path: str = '/root/intervention_signal_system/data/events.db'):
        self.db_path = db_path
        self.conn = None
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                url TEXT,
                published TEXT,
                fetched_at TEXT NOT NULL,
                priority_score REAL DEFAULT 0.5,
                event_type TEXT,
                signal_score REAL DEFAULT 0.0,
                processed BOOLEAN DEFAULT FALSE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                signal_type TEXT,
                confidence REAL,
                sources_involved TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_published ON events(published)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_signal_score ON events(signal_score)')
        
        self.conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
        
    def store_event(self, event: Dict) -> int:
        """Store a single event, returns event ID"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (source, title, summary, url, published, 
                               fetched_at, priority_score, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event['source'],
            event['title'],
            event['summary'],
            event['url'],
            event['published'],
            event['fetched_at'],
            event['priority_score'],
            event.get('type', 'unknown')
        ))
        
        event_id = cursor.lastrowid
        self.conn.commit()
        
        return event_id
        
    def store_events(self, events: List[Dict]) -> List[int]:
        """Store multiple events, returns list of event IDs"""
        event_ids = []
        
        for event in events:
            # Check for duplicates based on URL and title
            if not self._is_duplicate(event):
                event_id = self.store_event(event)
                event_ids.append(event_id)
            else:
                logger.debug(f"Duplicate event skipped: {event['title']}")
                
        return event_ids
        
    def _is_duplicate(self, event: Dict) -> bool:
        """Check if event already exists in database"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT id FROM events 
            WHERE url = ? OR (source = ? AND title = ?)
            LIMIT 1
        ''', (event['url'], event['source'], event['title']))
        
        return cursor.fetchone() is not None
        
    def get_unprocessed_events(self, limit: int = 100) -> List[Dict]:
        """Get events that haven't been processed for signal generation"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM events 
            WHERE processed = FALSE 
            ORDER BY priority_score DESC, published DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    def mark_processed(self, event_ids: List[int]):
        """Mark events as processed"""
        cursor = self.conn.cursor()
        
        for event_id in event_ids:
            cursor.execute('UPDATE events SET processed = TRUE WHERE id = ?', (event_id,))
            
        self.conn.commit()
        logger.info(f"Marked {len(event_ids)} events as processed")
        
    def update_signal_score(self, event_id: int, signal_score: float):
        """Update signal score for an event"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            UPDATE events SET signal_score = ? WHERE id = ?
        ''', (signal_score, event_id))
        
        self.conn.commit()
        
    def store_signal(self, signal: Dict):
        """Store a generated signal"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals (event_id, signal_type, confidence, sources_involved)
            VALUES (?, ?, ?, ?)
        ''', (
            signal.get('event_id'),
            signal.get('signal_type', 'intervention'),
            signal.get('confidence', 0.0),
            json.dumps(signal.get('sources_involved', []))
        ))
        
        self.conn.commit()
        
    def get_recent_events(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get events from the last N hours"""
        cursor = self.conn.cursor()
        
        cutoff = datetime.now(timezone.utc).replace(
            hour=datetime.now(timezone.utc).hour - hours
        ).isoformat()
        
        cursor.execute('''
            SELECT * FROM events 
            WHERE published > ? OR fetched_at > ?
            ORDER BY signal_score DESC, published DESC
            LIMIT ?
        ''', (cutoff, cutoff, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    def get_high_priority_events(self, min_score: float = 0.7, limit: int = 20) -> List[Dict]:
        """Get events with high signal scores"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM events 
            WHERE signal_score >= ?
            ORDER BY signal_score DESC, published DESC
            LIMIT ?
        ''', (min_score, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    def get_statistics(self, hours: int = 24) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total events
        cursor.execute('SELECT COUNT(*) FROM events')
        stats['total_events'] = cursor.fetchone()[0]
        
        # Events by source
        cursor.execute('''
            SELECT source, COUNT(*) as count 
            FROM events 
            GROUP BY source 
            ORDER BY count DESC
        ''')
        stats['by_source'] = {row['source']: row['count'] for row in cursor.fetchall()}
        
        # High priority events
        cursor.execute('SELECT COUNT(*) FROM events WHERE signal_score >= 0.7')
        stats['high_priority'] = cursor.fetchone()[0]
        
        # Unprocessed events
        cursor.execute('SELECT COUNT(*) FROM events WHERE processed = FALSE')
        stats['unprocessed'] = cursor.fetchone()[0]
        
        # Recent activity (last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        cursor.execute('SELECT COUNT(*) FROM events WHERE published > ? OR fetched_at > ?', 
                      (cutoff, cutoff))
        stats['last_24h'] = cursor.fetchone()[0]
        
        return stats
        
    def cleanup_old_events(self, days: int = 30):
        """Remove events older than N days"""
        cursor = self.conn.cursor()
        
        cutoff = datetime.now(timezone.utc).replace(
            day=datetime.now(timezone.utc).day - days
        ).isoformat()
        
        cursor.execute('DELETE FROM events WHERE published < ? AND signal_score < 0.5', 
                      (cutoff,))
        
        deleted = cursor.rowcount
        self.conn.commit()
        
        logger.info(f"Cleaned up {deleted} old events")
        return deleted
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


if __name__ == '__main__':
    # Test the storage
    storage = EventStorage()
    
    # Test statistics
    stats = storage.get_statistics()
    print("Database Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    storage.close()
