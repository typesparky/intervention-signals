"""
Intervention Signal System - Unified Orchestrator
Combines RSS feeds, OSINT data, and prediction market analysis
"""
import sys
import yaml
import logging
import argparse
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Import adapters
from rss_adapter import RSSAdapter
from gdelt_adapter import GDELTAdapter
from adsb_adapter import ADSBAdapter
from firms_adapter import FIRMSAdapter
from acled_adapter import ACLEDAdapter
from ais_adapter import AISAdapter

# Import core modules
from event_storage import EventStorage
from signal_generator import SignalGenerator
from signal_analyzer import SignalAnalyzer
from arbitrage_integrator import ArbitrageIntegrator


class InterventionOrchestrator:
    """Main orchestrator for the unified intervention signal system"""
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = False
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.storage = EventStorage("data/events.db")
        self.signal_generator = SignalGenerator(self.config['signal_thresholds'])
        self.signal_analyzer = SignalAnalyzer(self.config.get('osint_boosters', {}))
        self.arbitrage = ArbitrageIntegrator(self.config.get('prediction_markets', {}))
        
        # Initialize adapters
        self.adapters = self._initialize_adapters()
        
        self.logger.info(f"Initialized {len(self.adapters)} adapters")
        for name, adapter in self.adapters.items():
            self.logger.info(f"  - {name}: {adapter.__class__.__name__}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(self.config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/orchestrator.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all configured data adapters"""
        adapters = {}
        
        # RSS Feeds
        if 'bbc_world' in self.config:
            adapters['bbc_world'] = RSSAdapter(self.config['bbc_world'])
        
        if 'aljazeera_world' in self.config:
            adapters['aljazeera_world'] = RSSAdapter(self.config['aljazeera_world'])
        
        # API Sources
        if 'gdelt_events' in self.config:
            adapters['gdelt'] = GDELTAdapter(self.config['gdelt_events'])
        
        if 'adsb_exchange' in self.config:
            adapters['adsb'] = ADSBAdapter(self.config['adsb_exchange'])
        
        # OSINT Sources
        if 'nasa_firms' in self.config:
            adapters['firms'] = FIRMSAdapter(self.config['nasa_firms'])
        
        if 'acled' in self.config:
            adapters['acled'] = ACLEDAdapter(self.config['acled'])
        
        if 'ais_maritime' in self.config:
            adapters['ais'] = AISAdapter(self.config['ais_maritime'])
        
        return adapters
    
    def run_cycle(self) -> Dict[str, Any]:
        """Run a single monitoring cycle"""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting cycle at {datetime.now()}")
        
        cycle_start = datetime.now()
        results = {
            'events_fetched': 0,
            'events_stored': 0,
            'signals_generated': 0,
            'high_confidence': 0,
            'arbitrage_opportunities': 0
        }
        
        # Step 1: Fetch events from all sources
        self.logger.info("Step 1: Fetching events from all sources")
        all_events = []
        
        for source_id, adapter in self.adapters.items():
            try:
                self.logger.info(f"  Fetching from {source_id}")
                events = adapter.fetch_events()
                all_events.extend(events)
                results['events_fetched'] += len(events)
                self.logger.info(f"    Fetched {len(events)} events from {source_id}")
            except Exception as e:
                self.logger.error(f"  Error fetching from {source_id}: {e}")
        
        self.logger.info(f"  Total events fetched: {results['events_fetched']}")
        
        # Step 2: Store events in database
        self.logger.info("Step 2: Storing events in database")
        for event in all_events:
            try:
                if self.storage.add_event(event):
                    results['events_stored'] += 1
            except Exception as e:
                self.logger.error(f"  Error storing event: {e}")
        
        self.logger.info(f"  Stored {results['events_stored']} new events")
        
        # Step 3: Generate intervention signals
        self.logger.info("Step 3: Generating intervention signals")
        signals = self.signal_generator.generate_signals(all_events)
        results['signals_generated'] = len(signals)
        
        # Store signals in database
        for signal in signals:
            try:
                self.storage.add_signal(signal)
            except Exception as e:
                self.logger.error(f"  Error storing signal: {e}")
        
        self.logger.info(f"  Generated {len(signals)} signals")
        
        # Step 4: Analyze with OSINT data
        self.logger.info("Step 4: Analyzing with OSINT data")
        enhanced_signals = self.signal_analyzer.analyze_with_osint(signals)
        self.logger.info(f"  Enhanced {len(enhanced_signals)} signals with OSINT")
        
        # Step 5: Check for high-confidence alerts
        self.logger.info("Step 5: Checking for high-confidence alerts")
        alert_threshold = self.config['signal_thresholds'].get('alert_threshold', 0.8)
        high_confidence = [s for s in enhanced_signals if s.confidence >= alert_threshold]
        results['high_confidence'] = len(high_confidence)
        
        if high_confidence:
            self.logger.info(f"\n  HIGH-CONFIDENCE ALERTS ({len(high_confidence)}):")
            for signal in high_confidence:
                self.logger.info(f"    [{signal.event_type.upper()}] {signal.title}")
                self.logger.info(f"      Confidence: {signal.confidence:.2f} | Source: {signal.source}")
        else:
            self.logger.info("  No high-confidence alerts")
        
        # Step 6: Check prediction markets
        if self.config.get('prediction_markets', {}).get('enabled', False):
            self.logger.info("Step 6: Checking prediction markets")
            opportunities = self.arbitrage.find_opportunities(enhanced_signals)
            results['arbitrage_opportunities'] = len(opportunities)
            
            if opportunities:
                self.logger.info(f"  Found {len(opportunities)} arbitrage opportunities")
                for opp in opportunities[:5]:  # Show top 5
                    self.logger.info(f"    - {opp['market']}: {opp['signal']}")
                    self.logger.info(f"      Spread: {opp['spread']:.2f} | Confidence: {opp['confidence']:.2f}")
            else:
                self.logger.info("  No arbitrage opportunities found")
        
        # Calculate cycle duration
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        self.logger.info(f"\nCycle completed in {cycle_duration:.2f} seconds")
        self.logger.info(f"  Events: {results['events_fetched']} fetched, {results['events_stored']} stored")
        self.logger.info(f"  Signals: {results['signals_generated']} generated, {results['high_confidence']} high-confidence")
        if self.config.get('prediction_markets', {}).get('enabled', False):
            self.logger.info(f"  Arbitrage: {results['arbitrage_opportunities']} opportunities")
        
        return results
    
    def run_continuous(self, interval: int = 300):
        """Run continuous monitoring with specified interval (seconds)"""
        self.running = True
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"Starting continuous monitoring (interval: {interval}s)")
        
        while self.running:
            try:
                self.run_cycle()
                
                # Wait for next interval
                for i in range(interval):
                    if not self.running:
                        break
                    import time
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in monitoring cycle: {e}")
                import time
                time.sleep(60)  # Wait 1 minute before retry
        
        self.logger.info("Continuous monitoring stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def show_status(self):
        """Display system status"""
        print("\n" + "=" * 60)
        print("INTERVENTION SIGNAL SYSTEM STATUS")
        print("=" * 60)
        print(f"Status: {'Running' if self.running else 'Stopped'}")
        print(f"Active Adapters: {len(self.adapters)}")
        print(f"Last Update: {datetime.now()}")
        
        # Database statistics
        stats = self.storage.get_statistics()
        print("\nDatabase Statistics:")
        print(f"  Total events: {stats.get('total_events', 0)}")
        print(f"  By source: {stats.get('by_source', {})}")
        print(f"  High priority: {stats.get('high_priority', 0)}")
        print(f"  Unprocessed: {stats.get('unprocessed', 0)}")
        print(f"  Last 24h: {stats.get('last_24h', 0)}")
        
        # Signal statistics
        signal_stats = self.storage.get_signal_statistics(hours=24)
        print("\nSignal Summary (24h):")
        print(f"  Total signals: {signal_stats.get('total', 0)}")
        print(f"  High confidence: {signal_stats.get('high_confidence', 0)}")
        print(f"  By type: {signal_stats.get('by_type', {})}")
    
    def show_alerts(self, hours: int = 24):
        """Display recent high-confidence alerts"""
        alert_threshold = self.config['signal_thresholds'].get('alert_threshold', 0.8)
        signals = self.storage.get_recent_signals(hours=hours)
        
        high_conf = [s for s in signals if s.get('confidence', 0) >= alert_threshold]
        
        print(f"\nHigh-Confidence Alerts (last {hours} hours):")
        print("=" * 60)
        
        if not high_conf:
            print("No high-confidence alerts found")
            return
        
        for i, signal in enumerate(high_conf, 1):
            print(f"\n{i}. [{signal.get('event_type', 'UNKNOWN').upper()}] {signal.get('title', 'N/A')}")
            print(f"   Confidence: {signal.get('confidence', 0):.2f}")
            print(f"   Source: {signal.get('source', 'N/A')}")
            print(f"   Time: {signal.get('timestamp', 'N/A')}")
            if 'osint_boost' in signal:
                print(f"   OSINT Boost: +{signal['osint_boost']:.2f} ({signal.get('osint_source', 'N/A')})")
    
    def cleanup(self, days: int = 30):
        """Clean up old events and signals"""
        cutoff = datetime.now() - timedelta(days=days)
        events_deleted = self.storage.cleanup_old_events(cutoff)
        signals_deleted = self.storage.cleanup_old_signals(cutoff)
        
        print(f"Cleaned up {events_deleted} events and {signals_deleted} signals older than {days} days")


def main():
    parser = argparse.ArgumentParser(description='Intervention Signal System')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--interval', type=int, default=300, help='Continuous monitoring interval (seconds)')
    parser.add_argument('--status', action='store_true', help='Show system status')
    parser.add_argument('--alerts', type=int, default=24, help='Show alerts from last N hours')
    parser.add_argument('--cleanup', type=int, help='Delete events older than N days')
    parser.add_argument('--config', default='config/sources.yaml', help='Config file path')
    
    args = parser.parse_args()
    
    try:
        orchestrator = InterventionOrchestrator(args.config)
        
        if args.status:
            orchestrator.show_status()
        elif args.cleanup:
            orchestrator.cleanup(args.cleanup)
        elif args.alerts != 24:
            orchestrator.show_alerts(args.alerts)
        elif args.once:
            orchestrator.run_cycle()
        else:
            orchestrator.run_continuous(args.interval)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
