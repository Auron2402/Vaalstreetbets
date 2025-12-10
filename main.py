from api_client import TradeAPIClient
from arbitrage import MarketAnalyzer
from trend_analyzer import TrendAnalyzer
import json
import time

# Configuration
hours_back = 1  # Change this to fetch data from previous hours
league = "Standard" # Set current league
testing = False
poe_version = 2 # 1 = poe1, 2 = poe2 (duh)

# Trend Analysis Configuration
enable_trend_analysis = True  # Set to True to analyze multiple hours
trend_hours = 24  # Number of hours to analyze for trends (max 24 recommended)


def main():
    """
    Main function to analyze Path of Exile currency markets.
    Provides both single-hour snapshot and multi-hour trend analysis.
    """
    # set correct realm
    if poe_version == 1:
        realm = None
    elif poe_version == 2:
        realm = "poe2"
    
    # Initialize the client
    # Make sure you have a valid token.json file by running auth_handler.py
    try:
        client = TradeAPIClient()
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    # Calculate timestamps
    current_hour = int(time.time() // 3600 * 3600)
    target_timestamp = current_hour - (hours_back * 3600)

    # === SINGLE HOUR ANALYSIS (Current/Latest Hour) ===
    print("="*80)
    print("CURRENT HOUR SNAPSHOT ANALYSIS")
    print("="*80)

    current_markets = None

    if testing:
        # Load from sample file if testing
        with open("data_exports/currency_example.json", "r") as f:
            current_markets = json.load(f)
        print("Loaded sample currency exchange markets for testing.")
    else:
        # Fetch current hour data using API client's caching method
        current_markets = client.fetch_hourly_data(target_timestamp, realm=realm)

        if current_markets:
            print(f"Successfully loaded data for timestamp {target_timestamp}")
            print(f"Next Change ID: {current_markets.get('next_change_id')}")
            print(f"Number of Markets: {len(current_markets.get('markets', []))}")

    if current_markets:
        try:
            # Analyze current hour
            current_analyzer = MarketAnalyzer(current_markets, league=league, realm=realm)
            current_analyzer.display_market_stats(top_n=5)
            current_analyzer.get_top_spread_opportunities(top_n=10)
            current_analyzer.get_top_triangular_inefficiencies(top_n=10)

        except Exception as e:
            print(f"Error analyzing current market data: {e}")
    else:
        print("Could not load or fetch currency exchange markets. Cannot perform analysis.")
        return

    # === MULTI-HOUR TREND ANALYSIS ===
    if enable_trend_analysis and not testing:
        print(f"\n{'='*80}")
        print(f"MULTI-HOUR TREND ANALYSIS")
        print(f"{'='*80}")

        try:
            # Fetch data for multiple hours
            hourly_data_list = []
            timestamps = []

            print(f"\nFetching {trend_hours} hours of historical data...")
            for i in range(trend_hours, 0, -1):
                ts = target_timestamp - (i * 3600)
                timestamps.append(ts)

                data = client.fetch_hourly_data(ts, realm=realm)
                if data:
                    hourly_data_list.append(data)
                else:
                    print(f"Warning: Could not fetch data for hour {i} hours ago (timestamp: {ts})")

            # Add current hour to the end
            hourly_data_list.append(current_markets)

            if len(hourly_data_list) >= 2:
                print(f"\nSuccessfully loaded {len(hourly_data_list)} hours of data")

                # Create trend analyzer
                trend_analyzer = TrendAnalyzer(hourly_data_list, league=league, realm=realm)

                # Display persistent markets
                trend_analyzer.display_persistent_markets(
                    min_spread=0.02,  # 2% minimum spread
                    persistence_threshold=0.5,  # Must appear in 50% of hours
                    min_avg_volume=1000,  # Minimum 1000 base currency equivalent volume
                    top_n=10
                )

                # Display trending markets (widening spreads)
                trend_analyzer.display_trending_markets(
                    lookback_hours=min(6, len(hourly_data_list)),
                    min_avg_volume=1000,  # Minimum 1000 base currency equivalent volume
                    top_n=10
                )

                # Compare current hour with historical average
                trend_analyzer.display_current_vs_historical(
                    current_analyzer,
                    top_n=10
                )

            else:
                print(f"\nInsufficient data for trend analysis (need at least 2 hours, got {len(hourly_data_list)})")

        except Exception as e:
            print(f"Error during trend analysis: {e}")
            import traceback
            traceback.print_exc()
    elif enable_trend_analysis and testing:
        print("\nNote: Trend analysis is disabled in testing mode (only one sample file available)")

    print(f"\n{'='*80}")
    print("Analysis complete!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
