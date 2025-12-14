# Discord Webhook Setup Guide

This guide explains how to configure Discord notifications for VaalStreetBets market analysis results.

## Step 1: Create a Discord Webhook

1. Open your Discord server
2. Right-click on the channel where you want to receive notifications
3. Select **Edit Channel**
4. Go to **Integrations** → **Webhooks**
5. Click **New Webhook** or **Create Webhook**
6. (Optional) Customize the webhook name and avatar
7. Click **Copy Webhook URL**

The webhook URL will look like:
```
https://discord.com/api/webhooks/1234567890/AbCdEfGhIjKlMnOpQrStUvWxYz
```

## Step 2: Configure VaalStreetBets

1. Open `config.py` in your text editor
2. Find the **DISCORD WEBHOOK CONFIGURATION** section
3. Update the following settings:

```python
# Enable Discord notifications
DISCORD_WEBHOOK_ENABLED = True

# Paste your webhook URL here
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE"

# Configure which notifications to send
DISCORD_SEND_SPREAD_OPPORTUNITIES = True  # Spread analysis results
DISCORD_SEND_TRIANGULAR_TRADES = True     # Triangular trade results
DISCORD_SEND_PERSISTENT_MARKETS = True    # Persistent markets (trend analysis)
DISCORD_SEND_TRENDING_MARKETS = True      # Trending markets
DISCORD_SEND_CURRENT_VS_HISTORICAL = True # Current vs historical comparison
```

4. Save the file

## Step 3: Run the Analysis

Simply run the application as normal:
```bash
python main.py
```

The results will be:
- **Printed to the console** (as always)
- **Sent to your Discord channel** (if enabled)

## What Gets Sent to Discord

The Discord notifications include:

### 📊 Spread Opportunities
- Top markets with highest volatility
- Spread percentages
- Liquidity percentiles

### 🔺 Triangular Trades
- Top 3 triangular arbitrage opportunities
- Path and inefficiency percentages
- Profit estimates

### ⏱️ Persistent Markets
- Markets with consistent spreads over time
- Persistence ratios
- Average spreads

### 📈 Trending Markets
- Markets with increasing volatility
- Trend strength indicators
- Current spreads

## Troubleshooting

**No messages appearing in Discord:**
- Check that `DISCORD_WEBHOOK_ENABLED = True`
- Verify your webhook URL is correct
- Check console for error messages like "Failed to send Discord notification"

**Rate limiting:**
- Discord webhooks have rate limits (30 requests per minute)
- The tool sends 1 message per analysis section
- Normal usage should not hit rate limits

**Webhook deleted/invalid:**
- If you delete the webhook in Discord, you'll need to create a new one
- Update the `DISCORD_WEBHOOK_URL` in config.py with the new URL

## Disabling Discord Notifications

To temporarily disable Discord notifications without removing your webhook URL:

```python
DISCORD_WEBHOOK_ENABLED = False
```

To disable specific notification types, set them to `False`:
```python
DISCORD_SEND_TRIANGULAR_TRADES = False  # Don't send triangular trades
```

## Security Note

**IMPORTANT:** Never commit your `config.py` file with the webhook URL to a public repository! The webhook URL should be treated like a password. Anyone with access to it can send messages to your Discord channel.

Your `config.py` is already in `.gitignore` to prevent accidental commits.
