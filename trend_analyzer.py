"""
Multi-hour trend analysis for Path of Exile currency markets.
Analyzes patterns across multiple hours to identify persistent volatility.
"""

import statistics
from collections import defaultdict
from arbitrage import MarketAnalyzer


class TrendAnalyzer:
    """
    Analyzes market trends across multiple hours of historical data.
    Identifies markets with consistently high spreads and persistent patterns.
    """

    def __init__(self, hourly_data_list, league, realm=None):
        """
        Initialize trend analyzer with multiple hours of market data.

        Args:
            hourly_data_list: List of market data dictionaries, ordered from oldest to newest
            league: PoE league name to filter data
            realm: Optional realm (None for PoE1 PC, 'poe2' for PoE2, etc.)
        """
        self.league = league
        self.realm = realm
        self.base_currency = 'exalted' if realm == 'poe2' else 'chaos'
        self.base_currency_display = self.base_currency.capitalize()  # For UI consistency
        self.hourly_data = hourly_data_list
        self.hours_analyzed = len(hourly_data_list)

        # Create MarketAnalyzer for each hour
        self.analyzers = [
            MarketAnalyzer(data, league=league, realm=realm)
            for data in hourly_data_list
        ]

        # Track patterns across hours in a unified structure
        self.market_history = defaultdict(lambda: {
            'spreads': [],
            'base_volumes': [],
            'divine_volumes': []
        })
        self.triangular_history = defaultdict(list)

        self._analyze_trends()
        self._calculate_divine_base_ratio()

    def _calculate_divine_base_ratio(self):
        """
        Calculate the average Divine to base currency exchange rate from market data.
        Base currency is Chaos for PoE1 or Exalted for PoE2.
        This is used to normalize Divine volumes to base currency equivalents for filtering.
        """
        divine_base_ratios = []

        for analyzer in self.analyzers:
            # Check if there's a direct divine|base_currency market
            if 'divine' in analyzer.markets and self.base_currency in analyzer.markets['divine']:
                # Get the median price from min and max
                # This directly represents how many base currency you get for 1 divine
                min_price = analyzer.markets['divine'][self.base_currency]['min_price']
                max_price = analyzer.markets['divine'][self.base_currency]['max_price']
                ratio = (min_price + max_price) / 2
                divine_base_ratios.append(ratio)

        # Use the median of all hourly ratios, or default based on realm
        if divine_base_ratios:
            self.divine_to_base_ratio = statistics.median(divine_base_ratios)
        else:
            # Fallback: typical Divine ratios (250 for Chaos, 30 for Exalted)
            self.divine_to_base_ratio = 250 if self.base_currency == 'chaos' else 30

        base_name = self.base_currency.title()
        print(f"Using Divine to {base_name} ratio: 1 Divine ≈ "
              f"{self.divine_to_base_ratio:.0f} {base_name}")

    def _analyze_trends(self):
        """Analyze patterns across all hours to build trend data."""
        for hour_idx, analyzer in enumerate(self.analyzers):
            # Track spread patterns for each market pair
            processed_pairs = set()
            for currency_a, trades in analyzer.markets.items():
                for currency_b, prices in trades.items():
                    market_pair = tuple(sorted((currency_a, currency_b)))
                    if market_pair in processed_pairs:
                        continue
                    processed_pairs.add(market_pair)

                    # Calculate spread width
                    if prices['max_price'] > 0:
                        spread_width = (prices['max_price'] / prices['min_price']) - 1
                        market_id = f"{market_pair[0]}|{market_pair[1]}"

                        # Track spread data
                        self.market_history[market_id]['spreads'].append({
                            'hour_index': hour_idx,
                            'spread': spread_width,
                            'min_price': prices['min_price'],
                            'max_price': prices['max_price'],
                            'volume': prices.get('volume', {})
                        })

                        # Track volumes for both currencies
                        base_volume = prices.get('volume', {}).get(self.base_currency, 0)
                        divine_volume = prices.get('volume', {}).get('divine', 0)
                        self.market_history[market_id]['base_volumes'].append(base_volume)
                        self.market_history[market_id]['divine_volumes'].append(divine_volume)

    def get_persistent_spread_markets(self, min_spread=0.02, persistence_threshold=0.5, min_avg_volume=0, top_n=10):
        """
        Identify markets with consistently wide spreads across multiple hours.

        Args:
            min_spread: Minimum spread width to consider (default 2%)
            persistence_threshold: Fraction of hours that must show the spread (default 50%)
            min_avg_volume: Minimum average volume in base currency equivalents (default 0, no filter)
                           Divine volumes are automatically converted using market exchange rate
            top_n: Number of top markets to return

        Returns:
            List of markets with persistent high spreads
        """
        persistent_markets = []

        for market_id, history in self.market_history.items():
            spread_data = history['spreads']
            if len(spread_data) < 2:  # Need at least 2 hours of data
                continue

            # Count how many hours showed spread >= min_spread
            hours_with_spread = sum(1 for d in spread_data if d['spread'] >= min_spread)
            persistence_ratio = hours_with_spread / len(spread_data)

            if persistence_ratio >= persistence_threshold:
                spreads = [d['spread'] for d in spread_data]
                base_volumes = history['base_volumes']
                divine_volumes = history['divine_volumes']

                # Calculate average volumes for both currencies
                non_zero_base = [v for v in base_volumes if v > 0]
                non_zero_divine = [v for v in divine_volumes if v > 0]
                avg_base_volume = statistics.mean(non_zero_base) if non_zero_base else 0
                avg_divine_volume = statistics.mean(non_zero_divine) if non_zero_divine else 0

                # Normalize Divine volume to base currency equivalent for fair comparison
                avg_divine_in_base = avg_divine_volume * self.divine_to_base_ratio

                # Filter by minimum volume (use the higher of base or Divine-in-base)
                max_avg_volume_in_base = max(avg_base_volume, avg_divine_in_base)
                if max_avg_volume_in_base < min_avg_volume:
                    continue

                # Calculate volume metrics for both currencies
                hours_with_base = sum(1 for v in base_volumes if v > 0)
                hours_with_divine = sum(1 for v in divine_volumes if v > 0)
                hours_with_volume = max(hours_with_base, hours_with_divine)
                volume_consistency = hours_with_volume / len(spread_data) if spread_data else 0

                # Get most recent data
                latest = spread_data[-1]

                persistent_markets.append({
                    'market_id': market_id,
                    'persistence_ratio': persistence_ratio,
                    'hours_with_spread': hours_with_spread,
                    'total_hours': len(spread_data),
                    'avg_spread': statistics.mean(spreads),
                    'median_spread': statistics.median(spreads),
                    'max_spread': max(spreads),
                    'min_spread': min(spreads),
                    'std_dev': statistics.stdev(spreads) if len(spreads) > 1 else 0,
                    'avg_base_volume': avg_base_volume,
                    'avg_divine_volume': avg_divine_volume,
                    'total_base_volume': sum(base_volumes),
                    'total_divine_volume': sum(divine_volumes),
                    'hours_with_volume': hours_with_volume,
                    'volume_consistency': volume_consistency,
                    'latest_spread': latest['spread'],
                    'latest_min_price': latest['min_price'],
                    'latest_max_price': latest['max_price'],
                    'latest_base_volume': base_volumes[-1] if base_volumes else 0,
                    'latest_divine_volume': divine_volumes[-1] if divine_volumes else 0
                })

        # Sort by combination of persistence, spread, and volume
        # Higher weight on volume to prioritize liquid markets
        persistent_markets.sort(
            key=lambda x: (x['persistence_ratio'] * x['avg_spread'] * (1 + x['volume_consistency'])),
            reverse=True
        )

        return persistent_markets[:top_n]

    def get_trending_markets(self, lookback_hours=6, min_avg_volume=100, top_n=10):
        """
        Identify markets where spreads are widening (trending more volatile).

        Args:
            lookback_hours: Number of recent hours to analyze for trend
            min_avg_volume: Minimum average volume in base currency equivalents (default 100)
                           Divine volumes are automatically converted using market exchange rate
            top_n: Number of top trending markets to return

        Returns:
            List of markets with increasing volatility
        """
        trending_markets = []

        for market_id, history in self.market_history.items():
            spread_data = history['spreads']
            if len(spread_data) < lookback_hours:
                continue

            # Get recent spreads and volumes
            recent_spreads = [d['spread'] for d in spread_data[-lookback_hours:]]
            recent_base_volumes = history['base_volumes'][-lookback_hours:]
            recent_divine_volumes = history['divine_volumes'][-lookback_hours:]

            if len(recent_spreads) < 2:
                continue

            # Check volume filter for both currencies
            non_zero_base = [v for v in recent_base_volumes if v > 0]
            non_zero_divine = [v for v in recent_divine_volumes if v > 0]
            avg_base_volume = statistics.mean(non_zero_base) if non_zero_base else 0
            avg_divine_volume = statistics.mean(non_zero_divine) if non_zero_divine else 0

            # Normalize Divine volume to base currency equivalent for fair comparison
            avg_divine_in_base = avg_divine_volume * self.divine_to_base_ratio
            max_avg_volume_in_base = max(avg_base_volume, avg_divine_in_base)

            if max_avg_volume_in_base < min_avg_volume:
                continue

            # Calculate simple linear trend
            # Positive slope = widening spreads
            x_values = list(range(len(recent_spreads)))
            mean_x = statistics.mean(x_values)
            mean_y = statistics.mean(recent_spreads)

            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, recent_spreads))
            denominator = sum((x - mean_x) ** 2 for x in x_values)

            if denominator == 0:
                continue

            slope = numerator / denominator

            # Only include markets with positive trend (widening spreads)
            if slope > 0:
                latest = spread_data[-1]
                trending_markets.append({
                    'market_id': market_id,
                    'trend_slope': slope,
                    'latest_spread': latest['spread'],
                    'avg_recent_spread': statistics.mean(recent_spreads),
                    'spread_change': recent_spreads[-1] - recent_spreads[0],
                    'hours_analyzed': len(recent_spreads),
                    'avg_base_volume': avg_base_volume,
                    'avg_divine_volume': avg_divine_volume,
                    'latest_base_volume': recent_base_volumes[-1] if recent_base_volumes else 0,
                    'latest_divine_volume': recent_divine_volumes[-1] if recent_divine_volumes else 0
                })

        trending_markets.sort(key=lambda x: x['trend_slope'], reverse=True)
        return trending_markets[:top_n]

    def get_market_summary(self, market_id):
        """
        Get detailed summary for a specific market across all analyzed hours.

        Args:
            market_id: Market identifier (e.g., "chaos|divine")

        Returns:
            Dictionary with comprehensive market statistics
        """
        if market_id not in self.market_history:
            return None

        history = self.market_history[market_id]
        spread_data = history['spreads']
        spreads = [d['spread'] for d in spread_data]
        base_volumes = history['base_volumes']
        divine_volumes = history['divine_volumes']

        return {
            'market_id': market_id,
            'hours_tracked': len(spread_data),
            'avg_spread': statistics.mean(spreads),
            'median_spread': statistics.median(spreads),
            'max_spread': max(spreads),
            'min_spread': min(spreads),
            'std_dev': statistics.stdev(spreads) if len(spreads) > 1 else 0,
            'avg_base_volume': statistics.mean([v for v in base_volumes if v > 0]) if any(v > 0 for v in base_volumes) else 0,
            'avg_divine_volume': statistics.mean([v for v in divine_volumes if v > 0]) if any(v > 0 for v in divine_volumes) else 0,
            'spread_data': spread_data
        }

    def display_persistent_markets(self, min_spread=0.02, persistence_threshold=0.5, min_avg_volume=100, top_n=10):
        """
        Display markets with persistent high spreads in a formatted way.

        Args:
            min_spread: Minimum spread width to consider (default 2%)
            persistence_threshold: Fraction of hours that must show the spread (default 50%)
            min_avg_volume: Minimum average volume in base currency equivalents (default 100)
            top_n: Number of markets to display
        """
        base_name = self.base_currency.capitalize()
        print(f"\n{'='*80}")
        print(f"PERSISTENT VOLATILITY ANALYSIS ({self.hours_analyzed} hours analyzed)")
        print(f"Showing markets with >{min_spread:.1%} spread in >{persistence_threshold:.0%} of hours")
        print(f"Minimum average volume: {min_avg_volume:,.0f} {base_name} equivalent")
        print(f"(Using Divine/{base_name} ratio: 1 Divine ≈ {self.divine_to_base_ratio:.0f} {base_name})")
        print(f"{'='*80}")

        markets = self.get_persistent_spread_markets(min_spread, persistence_threshold, min_avg_volume, top_n)

        if not markets:
            print(f"\nNo markets found meeting criteria.")
            return

        for i, market in enumerate(markets, 1):
            currencies = market['market_id'].split('|')
            print(f"\n{i}. {currencies[0].upper()} <-> {currencies[1].upper()}")
            print(f"   Persistence: {market['hours_with_spread']}/{market['total_hours']} hours ({market['persistence_ratio']:.1%})")
            print(f"   Average Spread: {market['avg_spread']:.2%} (σ={market['std_dev']:.2%})")
            print(f"   Spread Range: {market['min_spread']:.2%} to {market['max_spread']:.2%}")
            print(f"   Latest Spread: {market['latest_spread']:.2%}")

            # Volume/throughput metrics
            print(f"   Volume Metrics:")

            # Display base currency volume if present
            if market['avg_base_volume'] > 0:
                print(f"      {base_name} Average: {market['avg_base_volume']:,.0f}/hour")
                print(f"      {base_name} Total ({self.hours_analyzed}h): {market['total_base_volume']:,.0f}")
                if market['latest_base_volume'] > 0:
                    base_trend = "↑" if market['latest_base_volume'] > market['avg_base_volume'] else "↓"
                    print(f"      {base_name} Latest: {market['latest_base_volume']:,.0f} {base_trend}")

            # Display Divine volume if present
            if market['avg_divine_volume'] > 0:
                print(f"      Divine Average: {market['avg_divine_volume']:,.0f}/hour")
                print(f"      Divine Total ({self.hours_analyzed}h): {market['total_divine_volume']:,.0f}")
                if market['latest_divine_volume'] > 0:
                    divine_trend = "↑" if market['latest_divine_volume'] > market['avg_divine_volume'] else "↓"
                    print(f"      Divine Latest: {market['latest_divine_volume']:,.0f} {divine_trend}")

            print(f"      Consistency: {market['hours_with_volume']}/{market['total_hours']} hours ({market['volume_consistency']:.1%})")

    def display_trending_markets(self, lookback_hours=6, min_avg_volume=100, top_n=10):
        """
        Display markets with increasing volatility trends.

        Args:
            lookback_hours: Number of recent hours to analyze
            min_avg_volume: Minimum average volume in base currency equivalents (default 100)
            top_n: Number of markets to display
        """
        base_name = self.base_currency.capitalize()
        print(f"\n{'='*80}")
        print(f"TRENDING VOLATILITY ANALYSIS (Last {lookback_hours} hours)")
        print(f"Markets where spreads are widening (increasing volatility)")
        print(f"Minimum average volume: {min_avg_volume:,.0f} {base_name} equivalent")
        print(f"(Using Divine/{base_name} ratio: 1 Divine ≈ {self.divine_to_base_ratio:.0f} {base_name})")
        print(f"{'='*80}")

        markets = self.get_trending_markets(lookback_hours, min_avg_volume, top_n)

        if not markets:
            print(f"\nNo trending markets found meeting criteria.")
            return

        for i, market in enumerate(markets, 1):
            currencies = market['market_id'].split('|')
            print(f"\n{i}. {currencies[0].upper()} <-> {currencies[1].upper()}")
            print(f"   Trend Strength: {market['trend_slope']:.4f} (positive = widening)")
            print(f"   Current Spread: {market['latest_spread']:.2%}")
            print(f"   Average (last {market['hours_analyzed']}h): {market['avg_recent_spread']:.2%}")
            print(f"   Change: {market['spread_change']:+.2%}")

            # Display volume for both currencies
            volume_parts = []
            if market['avg_base_volume'] > 0:
                volume_parts.append(f"{base_name}: {market['avg_base_volume']:,.0f}/hour (latest: {market['latest_base_volume']:,.0f})")
            if market['avg_divine_volume'] > 0:
                volume_parts.append(f"Divine: {market['avg_divine_volume']:,.0f}/hour (latest: {market['latest_divine_volume']:,.0f})")

            if volume_parts:
                print(f"   Volume: {' | '.join(volume_parts)}")

    def compare_with_current(self, current_analyzer):
        """
        Compare current hour's markets against historical trends.
        Identifies which current opportunities have historical backing.

        Args:
            current_analyzer: MarketAnalyzer instance for the current hour

        Returns:
            List of current opportunities with historical context
        """
        opportunities_with_context = []

        # Get current spread opportunities
        processed_pairs = set()
        for currency_a, trades in current_analyzer.markets.items():
            for currency_b, prices in trades.items():
                market_pair = tuple(sorted((currency_a, currency_b)))
                if market_pair in processed_pairs:
                    continue
                processed_pairs.add(market_pair)

                market_id = f"{market_pair[0]}|{market_pair[1]}"

                if prices['max_price'] > 0:
                    current_spread = (prices['max_price'] / prices['min_price']) - 1

                    # Get historical context
                    historical_summary = self.get_market_summary(market_id)

                    if historical_summary and current_spread > 0.001:
                        opportunities_with_context.append({
                            'market_id': market_id,
                            'current_spread': current_spread,
                            'historical_avg': historical_summary['avg_spread'],
                            'historical_max': historical_summary['max_spread'],
                            'historical_median': historical_summary['median_spread'],
                            'hours_tracked': historical_summary['hours_tracked'],
                            'vs_avg': current_spread - historical_summary['avg_spread'],
                            'percentile': self._calculate_percentile(current_spread, historical_summary['spread_data'])
                        })

        # Sort by how much current spread exceeds historical average
        opportunities_with_context.sort(key=lambda x: x['vs_avg'], reverse=True)

        return opportunities_with_context

    def _calculate_percentile(self, value, spread_data):
        """Calculate what percentile the current value is in historical data."""
        spreads = [d['spread'] for d in spread_data]
        spreads.sort()

        count_below = sum(1 for s in spreads if s < value)
        return (count_below / len(spreads)) * 100 if spreads else 0

    def display_current_vs_historical(self, current_analyzer, top_n=10):
        """
        Display current hour opportunities with historical context.

        Args:
            current_analyzer: MarketAnalyzer for current hour
            top_n: Number of opportunities to display
        """
        print(f"\n{'='*80}")
        print(f"CURRENT HOUR vs HISTORICAL AVERAGE")
        print(f"Comparing latest data against {self.hours_analyzed} hour average")
        print(f"{'='*80}")

        opportunities = self.compare_with_current(current_analyzer)

        if not opportunities:
            print("\nNo current opportunities with historical data.")
            return

        for i, opp in enumerate(opportunities[:top_n], 1):
            currencies = opp['market_id'].split('|')
            print(f"\n{i}. {currencies[0].upper()} <-> {currencies[1].upper()}")
            print(f"   Current Spread: {opp['current_spread']:.2%} (Percentile: {opp['percentile']:.0f}th)")
            print(f"   Historical Average: {opp['historical_avg']:.2%}")
            print(f"   Historical Range: {opp['historical_median']:.2%} to {opp['historical_max']:.2%}")

            if opp['vs_avg'] > 0:
                print(f"   Status: ⚠️  ABOVE AVERAGE by {opp['vs_avg']:.2%} (unusual volatility)")
            else:
                print(f"   Status: ✓ Normal (within historical range)")
