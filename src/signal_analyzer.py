"""
Signal analyzer - correlates intervention events with prediction markets
"""
import requests
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_feed_adapter import InterventionEvent
import sys
sys.path.insert(0, '/root/prediction_market_tools')


class SignalAnalyzer:
    """Analyzes intervention events and correlates with prediction markets"""

    def __init__(self, polymarket_api_url: str = None):
        self.polymarket_api = polymarket_api_url or "https://gamma-api.polymarket.com/markets"
        self.market_cache = {}
        self.cache_expiry = None

    def analyze_events(self, events: List[InterventionEvent]) -> Dict[str, Any]:
        """Analyze events and find related markets"""
        # Refresh market cache if needed
        if self.market_cache is None or self._is_cache_expired():
            self._refresh_market_cache()

        analysis = {
            'timestamp': datetime.now().isoformat(),
            'total_events': len(events),
            'high_confidence_events': 0,
            'related_markets': [],
            'signal_strength': 0.0,
            'top_opportunities': []
        }

        for event in events:
            # Find related markets
            related = self._find_related_markets(event)

            if related:
                event.related_markets = related
                analysis['related_markets'].extend(related)

                # Calculate signal strength for this event
                event_signal = self._calculate_signal_strength(event, related)
                event.signal_strength = event_signal

                if event.confidence > 0.7:
                    analysis['high_confidence_events'] += 1

                if event_signal > 0.6:
                    analysis['top_opportunities'].append({
                        'event': event.to_dict(),
                        'signal_strength': event_signal,
                        'related_markets': [m for m in related[:3]]  # Top 3 markets
                    })

        # Calculate overall signal strength
        if analysis['related_markets']:
            analysis['signal_strength'] = self._calculate_overall_signal_strength(analysis['related_markets'])

        return analysis

    def _refresh_market_cache(self):
        """Refresh market data cache"""
        try:
            params = {"limit": 200, "closed": "false", "active": "true"}
            resp = requests.get(self.polymarket_api, params=params, timeout=30)
            resp.raise_for_status()
            self.market_cache = resp.json()
            self.cache_expiry = datetime.now() + timedelta(minutes=5)
            print(f"Refreshed market cache: {len(self.market_cache)} markets")
        except Exception as e:
            print(f"Error refreshing market cache: {e}")

    def _is_cache_expired(self) -> bool:
        """Check if cache is expired"""
        return self.cache_expiry and datetime.now() > self.cache_expiry

    def _find_related_markets(self, event: InterventionEvent) -> List[Dict[str, Any]]:
        """Find markets related to an intervention event"""
        if not self.market_cache:
            return []

        related = []

        # Extract keywords from event
        event_keywords = self._extract_keywords(event.title + " " + event.description)

        for market in self.market_cache:
            market_question = market.get('question', '')
            market_desc = market.get('description', '')
            market_tags = market.get('tags', [])
            market_question_lower = market_question.lower()

            # Check for keyword matches
            relevance_score = self._calculate_relevance(
                event_keywords,
                market_question + " " + market_desc,
                market_tags
            )

            if relevance_score > 0.3:  # Threshold for relevance
                # Parse market prices
                prices_str = market.get('outcomePrices', '[]')
                try:
                    prices_list = json.loads(prices_str)
                    yes_price = float(prices_list[0]) if len(prices_list) > 0 else 0.5
                    no_price = float(prices_list[1]) if len(prices_list) > 1 else 0.5

                    # Convert from cents if needed
                    if yes_price > 1:
                        yes_price /= 100
                    if no_price > 1:
                        no_price /= 100

                    related.append({
                        'market_id': market.get('id', ''),
                        'question': market_question,
                        'yes_price': yes_price,
                        'no_price': no_price,
                        'liquidity': float(market.get('liquidity', 0)),
                        'volume': float(market.get('volume', 0)),
                        'relevance_score': relevance_score,
                        'tags': market_tags
                    })
                except Exception as e:
                    continue

        # Sort by relevance and liquidity
        related.sort(key=lambda x: (x['relevance_score'], x['liquidity']), reverse=True)

        return related[:10]  # Top 10 related markets

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from event text"""
        # Common geopolitical/military keywords
        key_terms = [
            # Military
            'military', 'army', 'navy', 'air force', 'marine', 'troop', 'soldier',
            'weapon', 'missile', 'airstrike', 'bomb', 'attack', 'conflict', 'war',
            'defense', 'security', 'deployment', 'exercise', 'operation',

            # Geopolitical
            'escalation', 'tension', 'diplomatic', 'sanction', 'embargo',
            'border', 'territory', 'sovereignty', 'regime', 'government',
            'revolution', 'coup', 'protest', 'riot', 'civil war',

            # Locations (regions/countries)
            'ukraine', 'russia', 'china', 'taiwan', 'korea', 'north korea',
            'south korea', 'iran', 'iraq', 'syria', 'afghanistan', 'israel',
            'palestine', 'yemen', 'saudi arabia', 'turkey', 'egypt',
            'middle east', 'europe', 'asia', 'africa', 'baltic', 'black sea',

            # Events
            'intervention', 'invasion', 'offensive', 'advance', 'retreat',
            ' ceasefire', 'truce', 'treaty', 'agreement', 'negotiation',
            'crisis', 'emergency', 'threat', 'warning', 'alert'
        ]

        text_lower = text.lower()
        found_keywords = []

        for keyword in key_terms:
            if keyword in text_lower:
                found_keywords.append(keyword)

        return found_keywords

    def _calculate_relevance(
        self,
        event_keywords: List[str],
        market_text: str,
        market_tags: List[str]
    ) -> float:
        """Calculate relevance score between event and market"""
        if not event_keywords:
            return 0.0

        market_text_lower = market_text.lower()
        tags_str = ' '.join(market_tags).lower()

        matched_keywords = 0
        for keyword in event_keywords:
            if keyword in market_text_lower or keyword in tags_str:
                matched_keywords += 1

        # Calculate score based on keyword matches
        score = matched_keywords / len(event_keywords)

        # Boost score if tags match
        if market_tags:
            tag_matches = sum(1 for tag in market_tags if tag.lower() in ' '.join(event_keywords))
            if tag_matches > 0:
                score += 0.2

        return min(score, 1.0)

    def _calculate_signal_strength(
        self,
        event: InterventionEvent,
        related_markets: List[Dict[str, Any]]
    ) -> float:
        """Calculate signal strength for an event"""
        if not related_markets:
            return 0.0

        # Base score from event confidence
        signal = event.confidence * 0.3

        # Add relevance score
        avg_relevance = sum(m['relevance_score'] for m in related_markets) / len(related_markets)
        signal += avg_relevance * 0.3

        # Add market liquidity factor
        total_liquidity = sum(m['liquidity'] for m in related_markets)
        liquidity_factor = min(total_liquidity / 10000, 1.0)  # Cap at 10k liquidity
        signal += liquidity_factor * 0.2

        # Add volume factor
        total_volume = sum(m['volume'] for m in related_markets)
        volume_factor = min(total_volume / 50000, 1.0)  # Cap at 50k volume
        signal += volume_factor * 0.2

        return min(signal, 1.0)

    def _calculate_overall_signal_strength(self, all_markets: List[Dict[str, Any]]) -> float:
        """Calculate overall signal strength across all markets"""
        if not all_markets:
            return 0.0

        # Average relevance
        avg_relevance = sum(m['relevance_score'] for m in all_markets) / len(all_markets)

        # Total liquidity
        total_liquidity = sum(m['liquidity'] for m in all_markets)
        liquidity_score = min(total_liquidity / 50000, 1.0)

        # Number of markets
        market_count_score = min(len(all_markets) / 20, 1.0)

        # Weighted average
        overall = (avg_relevance * 0.4 + liquidity_score * 0.4 + market_count_score * 0.2)

        return overall
