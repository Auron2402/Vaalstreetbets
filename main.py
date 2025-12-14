from api_client import TradeAPIClient
from arbitrage import MarketAnalyzer
from trend_analyzer import TrendAnalyzer
from discord_notifier import DiscordNotifier
import config
import json
import time

# Load configuration from config.py
# You can override these values here if needed for testing
hours_back = config.HOURS_BACK
league = config.LEAGUE
testing = config.TESTING
poe_version = config.POE_VERSION
enable_trend_analysis = config.ENABLE_TREND_ANALYSIS
trend_hours = config.TREND_HOURS

# Initialize Discord notifier
discord = DiscordNotifier()

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
            current_analyzer.display_market_stats(top_n=config.SINGLE_HOUR_TOP_N)

            # Get spread opportunities
            spread_opps = current_analyzer.get_top_spread_opportunities(
                top_n=config.SINGLE_HOUR_TOP_N,
                hide_zero_volume=config.SINGLE_HOUR_HIDE_ZERO_VOLUME
            )

            # Get triangular trades
            triangular_opps = current_analyzer.get_top_triangular_inefficiencies(
                top_n=config.SINGLE_HOUR_TOP_N,
                hide_zero_volume=config.SINGLE_HOUR_HIDE_ZERO_VOLUME,
                min_percentile=config.SINGLE_HOUR_TRIANGULAR_MIN_PERCENTILE
            )

            # Send Discord notifications for single-hour analysis
            if config.DISCORD_SEND_SPREAD_OPPORTUNITIES and spread_opps:
                discord.send_spread_opportunities(spread_opps, league, current_analyzer.base_currency, top_n=config.SINGLE_HOUR_TOP_N)

            if config.DISCORD_SEND_TRIANGULAR_TRADES and triangular_opps:
                discord.send_triangular_trades(triangular_opps, league, current_analyzer.base_currency, top_n=config.SINGLE_HOUR_TOP_N)

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

                # Get persistent markets
                persistent_markets = trend_analyzer.get_persistent_spread_markets(
                    min_spread=config.PERSISTENT_MIN_SPREAD,
                    persistence_threshold=config.PERSISTENT_PERSISTENCE_THRESHOLD,
                    min_avg_volume=config.PERSISTENT_MIN_AVG_VOLUME,
                    top_n=config.PERSISTENT_TOP_N
                )

                # Display persistent markets
                trend_analyzer.display_persistent_markets(
                    min_spread=config.PERSISTENT_MIN_SPREAD,
                    persistence_threshold=config.PERSISTENT_PERSISTENCE_THRESHOLD,
                    min_avg_volume=config.PERSISTENT_MIN_AVG_VOLUME,
                    top_n=config.PERSISTENT_TOP_N
                )

                # Get trending markets
                trending_markets = trend_analyzer.get_trending_markets(
                    lookback_hours=min(config.TRENDING_LOOKBACK_HOURS, len(hourly_data_list)),
                    min_avg_volume=config.TRENDING_MIN_AVG_VOLUME,
                    top_n=config.TRENDING_TOP_N
                )

                # Display trending markets (widening spreads)
                trend_analyzer.display_trending_markets(
                    lookback_hours=min(config.TRENDING_LOOKBACK_HOURS, len(hourly_data_list)),
                    min_avg_volume=config.TRENDING_MIN_AVG_VOLUME,
                    top_n=config.TRENDING_TOP_N
                )

                # Compare current hour with historical average
                trend_analyzer.display_current_vs_historical(
                    current_analyzer,
                    top_n=config.CURRENT_VS_HISTORICAL_TOP_N
                )

                # Send Discord notifications for trend analysis
                if config.DISCORD_SEND_PERSISTENT_MARKETS and persistent_markets:
                    discord.send_persistent_markets(persistent_markets, league, trend_analyzer.base_currency, trend_hours, top_n=config.PERSISTENT_TOP_N)

                if config.DISCORD_SEND_TRENDING_MARKETS and trending_markets:
                    discord.send_trending_markets(trending_markets, league, trend_analyzer.base_currency, config.TRENDING_LOOKBACK_HOURS, top_n=config.TRENDING_TOP_N)

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
