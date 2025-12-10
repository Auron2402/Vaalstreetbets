import itertools
import statistics
from bisect import bisect_left
from config import (
    MIN_SPREAD_THRESHOLD,
    TRIANGULAR_BASE_INVESTMENT,
    DEFAULT_DIVINE_CHAOS_RATIO,
    DEFAULT_DIVINE_EXALTED_RATIO
)

class MarketAnalyzer:
    def _format_number(self, num, precision=8, use_comma=False):
        """Formats a number to a string, removing trailing zeros, with specified precision."""
        fmt_str = f"{{:,.{precision}f}}" if use_comma else f"{{:.{precision}f}}"
        formatted_num = fmt_str.format(num)
        
        if '.' in formatted_num:
            formatted_num = formatted_num.rstrip('0').rstrip('.')
        
        return formatted_num

    def __init__(self, market_data, league, realm=None, debug=False, quiet=False):
        self.league = league
        self.realm = realm
        self.debug = debug
        self.quiet = quiet
        # Determine base currency: PoE2 uses exalted, PoE1 uses chaos
        self.base_currency = 'exalted' if realm == 'poe2' else 'chaos'
        self.base_currency_display = self.base_currency.capitalize()  # For UI consistency
        self.markets = self._process_markets(market_data)
        self._calculate_divine_base_ratio()
        self._perform_initial_calculations()

    def _calculate_divine_base_ratio(self):
        """
        Calculate the Divine to base currency exchange rate from market data.
        Base currency is Chaos for PoE1 or Exalted for PoE2.
        This is used to normalize Divine volumes to base currency equivalents for filtering.
        """
        # Check if there's a direct divine|base_currency market
        if 'divine' in self.markets and self.base_currency in self.markets['divine']:
            # Get the median price from min and max
            # This represents how many base currency you get for 1 divine
            min_price = self.markets['divine'][self.base_currency]['min_price']
            max_price = self.markets['divine'][self.base_currency]['max_price']
            self.divine_to_base_ratio = (min_price + max_price) / 2
            if not self.quiet:
                base_name = self.base_currency.title()
                print(f"Using Divine to {base_name} ratio: 1 Divine ≈ "
                      f"{self.divine_to_base_ratio:.0f} {base_name}")
        else:
            # Fallback: typical Divine ratios
            self.divine_to_base_ratio = DEFAULT_DIVINE_CHAOS_RATIO if self.base_currency == 'chaos' else DEFAULT_DIVINE_EXALTED_RATIO
            if not self.quiet:
                base_name = self.base_currency.title()
                print(f"Using Divine to {base_name} ratio (fallback): 1 Divine ≈ "
                      f"{self.divine_to_base_ratio:.0f} {base_name}")

    def _get_volume_percentile(self, volume, volume_list):
        """
        Calculate the percentile rank of a volume within a sorted volume list.

        Args:
            volume: The volume value to rank
            volume_list: Sorted list of volume values

        Returns:
            Percentile rank (0-100), or 0 if volume is zero or list is empty
        """
        if not volume_list or volume <= 0:
            return 0
        rank = bisect_left(volume_list, volume)
        return (rank / len(volume_list)) * 100

    def _calculate_currency_stats(self, market_data_list, volume_key):
        """
        Helper method to calculate statistics for a given currency type.

        Args:
            market_data_list: List of market data dictionaries
            volume_key: Key to access volume (e.g., 'base_volume' or 'divine_volume')

        Returns:
            Dictionary with mean, median, and top markets, or None if no data
        """
        markets_with_volume = [m for m in market_data_list if m[volume_key] > 0]
        if not markets_with_volume:
            return None

        markets_with_volume.sort(key=lambda x: x[volume_key], reverse=True)
        volumes = [m[volume_key] for m in markets_with_volume]

        return {
            'mean': statistics.mean(volumes) if volumes else 0,
            'median': statistics.median(volumes) if volumes else 0,
            'top_markets': markets_with_volume
        }

    def _perform_initial_calculations(self):
        market_data_list = []
        self.market_base_volumes = []  # Chaos for PoE1, Exalted for PoE2
        self.market_divine_volumes = []
        processed_pairs = set()

        for currency_a, trades in self.markets.items():
            for currency_b, data in trades.items():
                market_pair = tuple(sorted((currency_a, currency_b)))
                if market_pair in processed_pairs:
                    continue
                processed_pairs.add(market_pair)

                volume_traded = data.get('volume', {})
                base_volume = volume_traded.get(self.base_currency, 0)
                divine_volume = volume_traded.get('divine', 0)

                if base_volume > 0:
                    self.market_base_volumes.append(base_volume)

                if divine_volume > 0:
                    self.market_divine_volumes.append(divine_volume)

                if base_volume > 0 or divine_volume > 0:
                    market_id = f"{currency_a}|{currency_b}"
                    market_data_list.append({
                        'market_id': market_id,
                        'base_volume': base_volume,
                        'divine_volume': divine_volume,
                        'volume_traded': volume_traded
                    })

        self.market_base_volumes.sort()
        self.market_divine_volumes.sort()

        # Calculate stats using helper method
        self.base_stats = self._calculate_currency_stats(market_data_list, 'base_volume')
        self.divine_stats = self._calculate_currency_stats(market_data_list, 'divine_volume')

    def _process_markets(self, market_data):
        """
        Processes the raw market data to create a more usable structure for calculations.
        It extracts buy and sell prices for each currency pair.
        """
        processed_markets = {}
        skipped_counts = {'wrong_league': 0, 'invalid_id': 0, 'missing_ratios': 0, 'zero_ratio': 0}

        for market in market_data.get('markets', []):
            if market.get('league') != self.league:
                skipped_counts['wrong_league'] += 1
                continue

            market_id = market.get('market_id')
            if not market_id or '|' not in market_id:
                if self.debug:
                    print(f"Skipping invalid market_id: {market_id}")
                skipped_counts['invalid_id'] += 1
                continue

            currency_a, currency_b = market_id.split('|')

            # Ensure we have data for both currencies in the ratios
            if currency_a not in market.get('lowest_ratio', {}) or \
               currency_b not in market.get('lowest_ratio', {}) or \
               currency_a not in market.get('highest_ratio', {}) or \
               currency_b not in market.get('highest_ratio', {}):
                if self.debug:
                    print(f"Skipping {market_id}: missing ratio data")
                skipped_counts['missing_ratios'] += 1
                continue

            # Avoid division by zero
            if market['lowest_ratio'][currency_a] == 0 or market['highest_ratio'][currency_a] == 0:
                if self.debug:
                    print(f"Skipping {market_id}: zero ratio value")
                skipped_counts['zero_ratio'] += 1
                continue

            # lowest_ratio: The lowest exchange rate at which trades executed during this hour
            # When converting to price: this gives us the MAXIMUM value (better for selling)
            # Ratio is A:B, so the price in B is B/A.
            max_historical_price_for_a = market['lowest_ratio'][currency_b] / market['lowest_ratio'][currency_a]

            # highest_ratio: The highest exchange rate at which trades executed during this hour
            # When converting to price: this gives us the MINIMUM value (worse for selling, better for buying)
            # Ratio is A:B, so the price in B is B/A.
            min_historical_price_for_a = market['highest_ratio'][currency_b] / market['highest_ratio'][currency_a]

            volume_traded = market.get('volume_traded', {})

            if currency_a not in processed_markets:
                processed_markets[currency_a] = {}
            if currency_b not in processed_markets:
                processed_markets[currency_b] = {}

            # Store from the perspective of trading currency_a
            # 'max_price' = highest historical price, 'min_price' = lowest historical price
            processed_markets[currency_a][currency_b] = {'max_price': max_historical_price_for_a, 'min_price': min_historical_price_for_a, 'volume': volume_traded}
            # Store the inverse perspective for triangular path analysis
            processed_markets[currency_b][currency_a] = {'max_price': 1 / min_historical_price_for_a, 'min_price': 1 / max_historical_price_for_a, 'volume': volume_traded}

        if self.debug:
            print(f"\nMarket Processing Summary:")
            print(f"  Total markets processed: {len(processed_markets)}")
            print(f"  Skipped - wrong league: {skipped_counts['wrong_league']}")
            print(f"  Skipped - invalid ID: {skipped_counts['invalid_id']}")
            print(f"  Skipped - missing ratios: {skipped_counts['missing_ratios']}")
            print(f"  Skipped - zero ratios: {skipped_counts['zero_ratio']}")

        return processed_markets

    def get_top_spread_opportunities(self, top_n=10, hide_zero_volume=True):
        """
        Identifies currency pairs with the widest historical price spreads.
        A wide spread indicates volatility and potential market-making opportunities.
        These are historical spreads from completed trades, not executable arbitrage.
        """
        print(f"\n{'='*80}")
        print("HISTORICAL PRICE SPREAD ANALYSIS (Single Hour)")
        print("Markets with widest volatility in the analyzed hour")
        print(f"{'='*80}")
        opportunities = []
        processed_pairs = set()
        for currency_a, trades in self.markets.items():
            for currency_b, prices in trades.items():
                market_pair = tuple(sorted((currency_a, currency_b)))
                if market_pair in processed_pairs:
                    continue
                
                processed_pairs.add(market_pair)

                # Calculate spread width: difference between historical high and low prices
                # A wide spread indicates high volatility in this market during the hour
                # prices['max_price'] is the highest price traded for currency_a in currency_b
                # prices['min_price'] is the lowest price traded for currency_a in currency_b
                # Spread = how much higher the max was compared to the min
                if prices['min_price'] > 0: # Avoid division by zero
                    spread_width = (prices['max_price'] / prices['min_price']) - 1
                    if spread_width > MIN_SPREAD_THRESHOLD:
                        market_pair = f"{currency_a} <-> {currency_b}"

                        # Calculate potential value in base currency if this spread persists
                        base_value_str = ""
                        try:
                            # Estimate value based on TRIANGULAR_BASE_INVESTMENT units traded at this spread width
                            if currency_b == self.base_currency:
                                potential_value = TRIANGULAR_BASE_INVESTMENT * spread_width
                                base_value_str = f" (Historical spread: {potential_value:.2f} {self.base_currency.capitalize()} on {TRIANGULAR_BASE_INVESTMENT} {self.base_currency.capitalize()} volume)"
                            # If we can relate currency_b to base currency, estimate the value
                            elif self.base_currency in self.markets[currency_b]:
                                price_b_in_base = self.markets[currency_b][self.base_currency]['min_price']
                                potential_value = TRIANGULAR_BASE_INVESTMENT * price_b_in_base * spread_width
                                base_value_str = f" (Historical spread: ~{potential_value:.2f} {self.base_currency.capitalize()} on {TRIANGULAR_BASE_INVESTMENT} {currency_b} volume)"
                        except (KeyError, ZeroDivisionError):
                            pass # Can't calculate base value, so we skip it.

                        volume_data = prices.get('volume', {})
                        base_volume = volume_data.get(self.base_currency, 0)
                        divine_volume = volume_data.get('divine', 0)

                        if hide_zero_volume and base_volume == 0 and divine_volume == 0:
                            continue

                        # Calculate percentiles for both currencies using helper method
                        base_percentile = self._get_volume_percentile(base_volume, self.market_base_volumes)
                        divine_percentile = self._get_volume_percentile(divine_volume, self.market_divine_volumes)

                        # Use the higher percentile as the overall liquidity indicator
                        volume_percentile = max(base_percentile, divine_percentile)

                        opportunities.append((spread_width, market_pair, prices['min_price'], prices['max_price'], base_value_str, volume_percentile, base_volume, divine_volume))

        opportunities.sort(key=lambda x: x[0], reverse=True)

        if not opportunities:
            print("\nNo markets found with spreads meeting criteria.")
            return

        for i, (spread, pair, min_price, max_price, base_value, percentile, base_vol, divine_vol) in enumerate(opportunities[:top_n]):
            currencies = pair.split(' <-> ')
            print(f"\n{i+1}. {currencies[0].upper()} <-> {currencies[1].upper()}")
            print(f"   Spread Width: {spread:.2%}")
            print(f"   Price Range: {self._format_number(min_price)} to {self._format_number(max_price)}")
            if base_value:
                print(f"   {base_value.strip()}")
            print(f"   Liquidity: {percentile:.0f}th percentile")
            if base_vol > 0 or divine_vol > 0:
                volume_parts = []
                if base_vol > 0:
                    volume_parts.append(f"{base_vol:,} {self.base_currency.capitalize()}")
                if divine_vol > 0:
                    volume_parts.append(f"{divine_vol:,} Divine")
                print(f"   Volume: {' | '.join(volume_parts)}")

    def get_top_triangular_inefficiencies(self, top_n=10, hide_zero_volume=True, min_percentile=10):
        """
        Identifies triangular trading paths with historical price inefficiencies.
        These patterns (A -> B -> C -> A) show where historical prices suggested
        market inefficiencies. This is historical analysis, not executable arbitrage.

        Args:
            top_n: Number of top opportunities to display
            hide_zero_volume: Skip paths where any leg has zero volume
            min_percentile: Minimum volume percentile for any leg (default 10th percentile)
        """
        print(f"\n{'='*80}")
        print("TRIANGULAR MARKET INEFFICIENCY ANALYSIS (Single Hour)")
        print("Paths where historical prices suggested trading opportunities")
        print("NOTE: Uses best historical prices (min prices). These are NOT executable.")
        print("      Extreme values indicate volatility or data issues, not real arbitrage.")
        if min_percentile > 0:
            print(f"Filtering: All legs must have >{min_percentile}th percentile volume")
        print(f"{'='*80}")
        opportunities = []
        currencies = list(self.markets.keys())
        
        # Iterate through all unique combinations of 3 currencies
        # Only start from base currency to eliminate duplicate cycles
        # (base->divine->X and divine->X->base would be the same cycle)
        for curr_a, curr_b, curr_c in itertools.permutations(currencies, 3):
            # Filter: only analyze paths starting from base currency
            if curr_a != self.base_currency:
                continue

            try:
                # Path: A -> B -> C -> A
                # Using minimum historical prices (most favorable path for analysis)
                # Start with 1 unit of curr_a
                price_ab = self.markets[curr_a][curr_b]['min_price']
                price_bc = self.markets[curr_b][curr_c]['min_price']
                price_ca = self.markets[curr_c][curr_a]['min_price']

                # 1. Trade A for B at historical min price
                amount_b = 1 * price_ab
                # 2. Trade B for C at historical min price
                amount_c = amount_b * price_bc
                # 3. Trade C for A at historical min price
                final_amount_a = amount_c * price_ca

                inefficiency_ratio = final_amount_a - 1

                if inefficiency_ratio > 0:
                    # Get volumes for both base currency and Divine
                    base_volume_ab = self.markets[curr_a][curr_b].get('volume', {}).get(self.base_currency, 0)
                    base_volume_bc = self.markets[curr_b][curr_c].get('volume', {}).get(self.base_currency, 0)
                    base_volume_ca = self.markets[curr_c][curr_a].get('volume', {}).get(self.base_currency, 0)

                    divine_volume_ab = self.markets[curr_a][curr_b].get('volume', {}).get('divine', 0)
                    divine_volume_bc = self.markets[curr_b][curr_c].get('volume', {}).get('divine', 0)
                    divine_volume_ca = self.markets[curr_c][curr_a].get('volume', {}).get('divine', 0)

                    # Check if all legs have at least one of the currencies traded
                    has_volume_ab = base_volume_ab > 0 or divine_volume_ab > 0
                    has_volume_bc = base_volume_bc > 0 or divine_volume_bc > 0
                    has_volume_ca = base_volume_ca > 0 or divine_volume_ca > 0

                    if hide_zero_volume and not (has_volume_ab and has_volume_bc and has_volume_ca):
                        continue

                    # Calculate percentiles for each leg using helper method
                    base_p_ab = self._get_volume_percentile(base_volume_ab, self.market_base_volumes)
                    divine_p_ab = self._get_volume_percentile(divine_volume_ab, self.market_divine_volumes)
                    percentile_ab = max(base_p_ab, divine_p_ab)

                    base_p_bc = self._get_volume_percentile(base_volume_bc, self.market_base_volumes)
                    divine_p_bc = self._get_volume_percentile(divine_volume_bc, self.market_divine_volumes)
                    percentile_bc = max(base_p_bc, divine_p_bc)

                    base_p_ca = self._get_volume_percentile(base_volume_ca, self.market_base_volumes)
                    divine_p_ca = self._get_volume_percentile(divine_volume_ca, self.market_divine_volumes)
                    percentile_ca = max(base_p_ca, divine_p_ca)

                    lowest_leg_percentile = min(percentile_ab, percentile_bc, percentile_ca)

                    # Filter out paths where the minimum leg percentile is too low (illiquid)
                    if lowest_leg_percentile < min_percentile:
                        continue

                    # Calculate historical inefficiency value in base currency if possible
                    base_value_str = ""
                    if curr_a == self.base_currency:
                        historical_value = TRIANGULAR_BASE_INVESTMENT * inefficiency_ratio
                        base_value_str = f" (Historical inefficiency: {historical_value:.2f} {self.base_currency.capitalize()} per {TRIANGULAR_BASE_INVESTMENT} invested)"

                    steps_str = f"Historical Rates: {self._format_number(price_ab)}, {self._format_number(price_bc)}, {self._format_number(price_ca)}"

                    # Calculate total volumes across all legs (take max for each currency)
                    total_base_vol = max(base_volume_ab, base_volume_bc, base_volume_ca)
                    total_divine_vol = max(divine_volume_ab, divine_volume_bc, divine_volume_ca)

                    opportunities.append({
                        'inefficiency': inefficiency_ratio,
                        'path': f"{curr_a} -> {curr_b} -> {curr_c} -> {curr_a}",
                        'base_value': base_value_str,
                        'steps': steps_str,
                        'volume_percentile': lowest_leg_percentile,
                        'base_volume': total_base_vol,
                        'divine_volume': total_divine_vol
                    })

            except KeyError:
                # This path is not possible if a market between any pair doesn't exist
                continue

        # Sort by inefficiency ratio and get the top N
        opportunities.sort(key=lambda x: x['inefficiency'], reverse=True)

        if not opportunities:
            print("\nNo triangular paths found meeting criteria.")
            return

        for i, opp in enumerate(opportunities[:top_n]):
            print(f"\n{i+1}. Path: {opp['path']}")
            print(f"   Inefficiency: {opp['inefficiency']:.2%}")
            if opp['base_value']:
                print(f"   {opp['base_value'].strip()}")
            print(f"   {opp['steps']}")
            print(f"   Min Liquidity: {opp['volume_percentile']:.0f}th percentile")

            # Display actual volumes
            if opp['base_volume'] > 0 or opp['divine_volume'] > 0:
                volume_parts = []
                if opp['base_volume'] > 0:
                    volume_parts.append(f"{opp['base_volume']:,} {self.base_currency.capitalize()}")
                if opp['divine_volume'] > 0:
                    volume_parts.append(f"{opp['divine_volume']:,} Divine")
                print(f"   Max Volume per Leg: {' | '.join(volume_parts)}")

    def display_market_stats(self, top_n=5):
        """
        Displays pre-calculated market statistics based on trading volume.
        """
        print(f"\n{'='*80}")
        print("MARKET VOLUME STATISTICS (Single Hour)")
        print("Top markets by trading activity")
        print(f"{'='*80}")

        if not self.base_stats and not self.divine_stats:
            print("No market volume data available.")
            return

        # --- Base Currency Stats ---
        if self.base_stats:
            print(f"\n{self.base_currency.capitalize()} Orb Volume Statistics:")
            print(f"   Mean: {self._format_number(self.base_stats['mean'], precision=2, use_comma=True)} {self.base_currency.capitalize()}")
            print(f"   Median: {self._format_number(self.base_stats['median'], precision=2, use_comma=True)} {self.base_currency.capitalize()}")

            print(f"\nTop {top_n} Markets by {self.base_currency.capitalize()} Volume:")
            for i, market in enumerate(self.base_stats['top_markets'][:top_n]):
                currencies = market['market_id'].split('|')
                other_currency = next((c for c in currencies if c != self.base_currency), None)

                print(f"\n{i+1}. {currencies[0].upper()} <-> {currencies[1].upper()}")
                print(f"   {self.base_currency.capitalize()} Volume: {market['base_volume']:,}")
                if other_currency and other_currency in market['volume_traded']:
                    other_volume = market['volume_traded'][other_currency]
                    print(f"   {other_currency.replace('-', ' ').title()} Volume: {other_volume:,}")
        
        # --- Divine Stats ---
        if self.divine_stats:
            print("\nDivine Orb Volume Statistics:")
            print(f"   Mean: {self._format_number(self.divine_stats['mean'], precision=2, use_comma=True)} Divine")
            print(f"   Median: {self._format_number(self.divine_stats['median'], precision=2, use_comma=True)} Divine")

            print(f"\nTop {top_n} Markets by Divine Volume:")
            for i, market in enumerate(self.divine_stats['top_markets'][:top_n]):
                currencies = market['market_id'].split('|')
                other_currency = next((c for c in currencies if c != 'divine'), None)

                print(f"\n{i+1}. {currencies[0].upper()} <-> {currencies[1].upper()}")
                print(f"   Divine Volume: {market['divine_volume']:,}")
                if other_currency and other_currency in market['volume_traded']:
                    other_volume = market['volume_traded'][other_currency]
                    print(f"   {other_currency.replace('-', ' ').title()} Volume: {other_volume:,}")