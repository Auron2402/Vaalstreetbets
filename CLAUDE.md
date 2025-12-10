# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vaalstreetbets is a Python application for analyzing Path of Exile (PoE) currency exchange markets using the official GGG API. The system fetches hourly historical currency exchange data and identifies:
- Markets with wide historical price spreads (volatility indicators)
- Triangular trading path inefficiencies
- High-liquidity markets with potential trading opportunities

**Important**: This tool analyzes **historical trade data**, not real-time order books. It identifies patterns and volatility that may indicate future opportunities, not executable arbitrage trades.

## Architecture

### Core Components

**Authentication Flow** ([auth_handler.py](auth_handler.py))
- Handles OAuth2 client credentials flow with GGG's API
- Requires CLIENT_ID, CLIENT_SECRET from [config.py](config.py)
- Saves access token to token.json for subsequent API calls
- Scope: `service:cxapi`

**API Client** ([api_client.py](api_client.py))
- `TradeAPIClient` class manages authenticated requests to `https://api.pathofexile.com`
- Loads access token from token.json
- `get_currency_exchange_markets()` fetches hourly historical data with realm and timestamp parameters
- `fetch_hourly_data()` implements caching layer: checks local cache before making API calls
- Handles rate limiting with automatic retry-after delays
- Auto-creates cache directory (`data_exports/` by default)

**Market Analyzer** ([arbitrage.py](arbitrage.py))
- `MarketAnalyzer` processes historical market data for a specific league
- Converts raw API market ratios into min/max historical price ranges
- Stores bidirectional price data to enable triangular path analysis
- Market processing: `lowest_ratio` = minimum historical price, `highest_ratio` = maximum historical price
- **Spread Analysis**: Identifies currency pairs with wide historical price ranges (volatility)
- **Triangular Inefficiency Analysis**: Finds A → B → C → A paths where historical prices suggested market inefficiencies
- Volume statistics tracked in Chaos and Divine orbs with percentile rankings for liquidity assessment

**Trend Analyzer** ([trend_analyzer.py](trend_analyzer.py))
- `TrendAnalyzer` analyzes patterns across multiple hours of historical data
- **Persistent Markets**: Identifies markets with consistently high spreads over time
- **Trending Markets**: Detects markets where spreads are widening (increasing volatility)
- **Historical Comparison**: Compares current hour against historical averages
- Calculates persistence ratios, trend slopes, and statistical metrics
- Provides context for whether current opportunities are unusual or typical

**Main Application** ([main.py](main.py))
- Entry point that orchestrates the workflow
- Configuration: `hours_back`, `league`, `testing` mode, `enable_trend_analysis`, `trend_hours`
- Executes both single-hour snapshot and multi-hour trend analysis
- Uses `TradeAPIClient.fetch_hourly_data()` for automatic caching
- Fetches historical data automatically when trend analysis is enabled

### Data Flow

**Single-Hour Analysis:**
1. Authentication (one-time): [auth_handler.py](auth_handler.py) → token.json
2. Market data fetch: [main.py](main.py) → [api_client.py](api_client.py).fetch_hourly_data() → checks cache → API (if needed) → cached JSON
3. Processing: Raw market data → [arbitrage.py](arbitrage.py) → min/max historical price ranges
4. Analysis: Price data → spread/inefficiency calculations → ranked volatility patterns

**Multi-Hour Trend Analysis:**
1. Fetch N hours of historical data via [api_client.py](api_client.py).fetch_hourly_data() (automatic caching)
2. Create `TrendAnalyzer` with all hourly data
3. Calculate persistence ratios, trends, and statistical metrics
4. Compare current hour against historical patterns
5. Display persistent markets, trending markets, and unusual opportunities

## Development Commands

### Initial Setup

```bash
# First-time authentication (creates token.json)
python auth_handler.py
```

You must configure [config.py](config.py) with your GGG OAuth credentials before running this.

### Running the Application

```bash
# Run with current configuration
python main.py
```

Configuration is set at the top of [main.py](main.py):
- `hours_back`: Number of hours back from current hour to fetch data (default: 1)
- `league`: PoE league name (e.g., "Keepers", "Standard")
- `testing`: Set to `True` to use `data_exports/currency_example.json` instead of API
- `enable_trend_analysis`: Set to `True` to enable multi-hour trend analysis (default: True)
- `trend_hours`: Number of historical hours to analyze for trends (default: 24)

### Testing

To test without API calls, set `testing = True` in [main.py](main.py) and ensure `data_exports/currency_example.json` exists.

## Important Implementation Details

### API Considerations

- **Historical Data Only**: API returns hourly digests of **completed trades**, not real-time order books
- **Not Executable**: The data shows what prices trades executed at in the past, not current bid/ask spreads
- **Use Case**: This is for identifying volatile markets to monitor, not for executing trades directly
- **Timestamp Handling**: Unix timestamps must be truncated to the hour (`time.time() // 3600 * 3600`)
- **Realms**: Default is PoE1 PC; can specify 'xbox', 'sony', or 'poe2'
- **Rate Limiting**: Client automatically handles 429 responses with Retry-After headers
- **Data Availability**: Old history may be removed by GGG at any time

### Market Data Structure

Market ratios from API represent historical trade ranges:
- `lowest_ratio`: Lowest exchange rate at which trades executed during the hour
- `highest_ratio`: Highest exchange rate at which trades executed during the hour
- Formula: Price of A in B = `ratio[B] / ratio[A]`

[arbitrage.py](arbitrage.py:109-117) converts these ratios into min/max historical price ranges and stores both forward and inverse perspectives for triangular path analysis.

**Critical Understanding**: These are **historical price ranges**, not current executable prices. A wide range indicates volatility/spread during that hour.

### Volume Analysis

The market analyzer pre-calculates volume statistics during initialization ([arbitrage.py](arbitrage.py:21-80)):
- Chaos and Divine volume statistics (mean, median)
- Sorted volume arrays for percentile calculations using binary search
- Volume percentiles indicate market liquidity (higher = more liquid)
- Higher liquidity + wide spreads = better candidates for monitoring

### Currency Pair Processing

Markets are processed bidirectionally to avoid duplicate analysis and enable triangular paths:
- Each unique pair (A, B) is processed once using set tracking
- Both A→B and B→A historical price ranges are stored with inverse relationships
- Zero-volume markets can be filtered to focus on liquid opportunities

## What This Tool Does vs. Doesn't Do

### ✅ What It Does:
- Identifies markets with high historical volatility (wide price spreads)
- Ranks markets by liquidity using volume percentiles
- Finds triangular paths where historical prices suggested inefficiencies
- **Analyzes trends across multiple hours** to identify persistent patterns
- Detects markets with widening spreads (increasing volatility)
- Compares current opportunities against historical averages
- Provides a **screening tool** to identify which markets to monitor

### ❌ What It Doesn't Do:
- Provide executable arbitrage opportunities (data is historical)
- Show current market prices (no real-time order book)
- Guarantee that patterns will persist into future hours
- Execute trades automatically

### 💡 Recommended Use:
Use this tool to identify volatile currency pairs with good liquidity, then monitor those markets in real-time for actual trading opportunities.

## Configuration

**config.py** (gitignored) must contain:
```python
CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_secret'
REDIRECT_URI = 'your_redirect_uri'  # Must match GGG registration
USER_AGENT = 'OAuth appname/version (contact: email)'
```

**token.json** (gitignored) is auto-generated by [auth_handler.py](auth_handler.py) and contains the OAuth access token.

## File Organization

- `data_exports/`: Cached hourly market data JSONs (filename: `currency_exchange_markets_{timestamp}.json`)
- `docs/`: API documentation ([testdocs.md](docs/testdocs.md))
- `__pycache__/`: Python bytecode cache (gitignored)

## Trend Analysis Features

### Persistent Markets
Shows markets that consistently exhibit wide spreads across multiple hours. Parameters:
- `min_spread`: Minimum spread threshold (default 2%)
- `persistence_threshold`: Fraction of hours that must show the spread (default 50%)
- `min_avg_volume`: Minimum average volume in Chaos equivalents (default 1000)

Example: A market showing 3%+ spread in 18 out of 24 hours has a 75% persistence ratio.

**Volume Normalization**: Divine volumes are automatically converted to Chaos equivalents using the market exchange rate calculated from the chaos|divine market. This ensures fair comparison between Chaos-based and Divine-based markets.

**Throughput Analysis**: Markets are filtered by actual trading volume to exclude illiquid pairs. Volume metrics include:
- Average volume per hour (shown separately for Chaos and Divine)
- Total volume across all hours
- Volume consistency (% of hours with activity)
- Latest volume with trend indicator (↑/↓)

### Trending Markets
Identifies markets where spreads are actively widening (increasing volatility). Uses linear regression on recent hours to calculate trend slope. Positive slope indicates growing volatility. Also filters by minimum average volume (in Chaos equivalents, default 1000) to focus on liquid markets. Divine volumes are automatically normalized to Chaos equivalents for filtering.

### Historical Comparison
Compares current hour's opportunities against multi-hour averages:
- Shows percentile ranking of current spread vs. historical distribution
- Flags unusual volatility (current spread significantly above average)
- Helps distinguish between normal fluctuation and genuine anomalies

### Statistical Metrics
For each market across time, calculates:
- Mean and median spreads
- Standard deviation (volatility of volatility)
- Minimum and maximum spreads observed
- Average volume for liquidity assessment
- Volume consistency (how often the market has trades)
- Total throughput (sum of all volume across hours)
