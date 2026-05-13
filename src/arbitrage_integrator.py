"""
Integration module for connecting intervention signals with arbitrage system
"""
import sys
sys.path.insert(0, '/root/prediction_market_tools')

from typing import List, Dict, Any
import requests


class ArbitrageIntegrator:
    """Integrate intervention signals with prediction market arbitrage"""

    def __init__(self):
        self.polymarket_api = "https://gamma-api.polymarket.com/markets"

    def find_arbitrage_opportunities(
        self,
        intervention_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities related to intervention events
        """
        opportunities = []

        # Get current markets
        markets = self._fetch_markets()

        # Group markets by event type
        event_type_markets = self._group_markets_by_event_type(markets)

        # For each intervention event, find arbitrage opportunities
        for event in intervention_events:
            event_type = event.get('event_type', 'general')

            # Get related markets
            related_markets = event_type_markets.get(event_type, [])

            # Find arbitrage between related markets
            arbitrage_opps = self._find_cross_market_arbitrage(related_markets)

            # Correlate with intervention signal
            for opp in arbitrage_opps:
                opp['intervention_event'] = event
                opp['signal_boost'] = event.get('confidence', 0.5)

            opportunities.extend(arbitrage_opps)

        # Sort by profitability and signal boost
        opportunities.sort(
            key=lambda x: (
                x.get('profit_percent', 0) * (1 + x.get('signal_boost', 0)),
                x.get('liquidity', 0)
            ),
            reverse=True
        )

        return opportunities[:20]  # Top 20

    def _fetch_markets(self) -> List[Dict[str, Any]]:
        """Fetch markets from Polymarket"""
        try:
            params = {"limit": 200, "closed": "false", "active": "true"}
            resp = requests.get(self.polymarket_api, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []

    def _group_markets_by_event_type(
        self,
        markets: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group markets by event type based on keywords"""
        groups = {
            'military_operation': [],
            'conflict': [],
            'diplomatic': [],
            'escalation': [],
            'general': []
        }

        keyword_map = {
            'military_operation': ['military', 'defense', 'deployment', 'exercise'],
            'conflict': ['war', 'attack', 'conflict', 'clash', 'strike'],
            'diplomatic': ['diplomatic', 'sanction', 'talks', 'meeting', 'summit'],
            'escalation': ['escalation', 'tension', 'crisis', 'emergency']
        }

        for market in markets:
            question = market.get('question', '').lower()

            matched = False
            for event_type, keywords in keyword_map.items():
                if any(kw in question for kw in keywords):
                    groups[event_type].append(market)
                    matched = True
                    break

            if not matched:
                groups['general'].append(market)

        return groups

    def _find_cross_market_arbitrage(
        self,
        markets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities between related markets"""
        import json

        opportunities = []

        for i, market_a in enumerate(markets):
            for market_b in markets[i+1:]:
                # Check if markets are similar enough
                similarity = self._calculate_similarity(
                    market_a.get('question', ''),
                    market_b.get('question', '')
                )

                if similarity < 0.4:  # Minimum similarity threshold
                    continue

                # Calculate arbitrage
                arbitrage = self._calculate_arbitrage(market_a, market_b)

                if arbitrage and arbitrage['profit'] > 0:
                    opportunities.append(arbitrage)

        return opportunities

    def _calculate_similarity(self, question_a: str, question_b: str) -> float:
        """Calculate similarity between two market questions"""
        import re

        # Normalize
        q1 = re.sub(r'[^\w\s]', '', question_a.lower()).split()
        q2 = re.sub(r'[^\w\s]', '', question_b.lower()).split()

        # Jaccard similarity
        set1, set2 = set(q1), set(q2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0

    def _calculate_arbitrage(
        self,
        market_a: Dict[str, Any],
        market_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate arbitrage opportunity between two markets"""
        import json

        try:
            # Parse prices
            prices_a = json.loads(market_a.get('outcomePrices', '[]'))
            prices_b = json.loads(market_b.get('outcomePrices', '[]'))

            yes_a = float(prices_a[0]) if len(prices_a) > 0 else 0.5
            no_a = float(prices_a[1]) if len(prices_a) > 1 else 0.5
            yes_b = float(prices_b[0]) if len(prices_b) > 0 else 0.5
            no_b = float(prices_b[1]) if len(prices_b) > 1 else 0.5

            # Convert from cents if needed
            if yes_a > 1: yes_a /= 100
            if no_a > 1: no_a /= 100
            if yes_b > 1: yes_b /= 100
            if no_b > 1: no_b /= 100

            # Calculate arbitrage opportunities
            # Option 1: Buy YES on A, NO on B
            cost1 = yes_a + no_b
            if cost1 < 1.0:
                profit = (1.0 - cost1) * 100
                profit_pct = (1.0 - cost1) / cost1 * 100

                return {
                    'market_a_id': market_a.get('id'),
                    'market_b_id': market_b.get('id'),
                    'market_a_question': market_a.get('question'),
                    'market_b_question': market_b.get('question'),
                    'strategy': 'YES_A + NO_B',
                    'yes_price': yes_a,
                    'no_price': no_b,
                    'cost': cost1,
                    'profit': profit,
                    'profit_percent': profit_pct,
                    'liquidity': min(
                        float(market_a.get('liquidity', 0)),
                        float(market_b.get('liquidity', 0))
                    )
                }

            # Option 2: Buy NO on A, YES on B
            cost2 = no_a + yes_b
            if cost2 < 1.0:
                profit = (1.0 - cost2) * 100
                profit_pct = (1.0 - cost2) / cost2 * 100

                return {
                    'market_a_id': market_a.get('id'),
                    'market_b_id': market_b.get('id'),
                    'market_a_question': market_a.get('question'),
                    'market_b_question': market_b.get('question'),
                    'strategy': 'NO_A + YES_B',
                    'yes_price': yes_b,
                    'no_price': no_a,
                    'cost': cost2,
                    'profit': profit,
                    'profit_percent': profit_pct,
                    'liquidity': min(
                        float(market_a.get('liquidity', 0)),
                        float(market_b.get('liquidity', 0))
                    )
                }

            return None

        except Exception as e:
            print(f"Error calculating arbitrage: {e}")
            return None
