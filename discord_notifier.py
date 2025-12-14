"""
Discord webhook integration for sending market analysis results.
"""

import requests
import json
from config import DISCORD_WEBHOOK_URL, DISCORD_WEBHOOK_ENABLED


class DiscordNotifier:
    """Handles sending messages to Discord via webhooks."""

    def __init__(self, webhook_url=None, enabled=None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL (uses config if not provided)
            enabled: Whether notifications are enabled (uses config if not provided)
        """
        self.webhook_url = webhook_url if webhook_url is not None else DISCORD_WEBHOOK_URL
        self.enabled = enabled if enabled is not None else DISCORD_WEBHOOK_ENABLED

        if self.enabled and not self.webhook_url:
            print("Warning: Discord notifications enabled but no webhook URL configured!")
            self.enabled = False

    def send_message(self, content=None, embeds=None):
        """
        Send a message to Discord.

        Args:
            content: Plain text message (max 2000 characters)
            embeds: List of embed objects (max 10 embeds)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        if not content and not embeds:
            return False

        payload = {}
        if content:
            # Discord has a 2000 character limit for content
            payload["content"] = content[:2000]
        if embeds:
            payload["embeds"] = embeds[:10]  # Max 10 embeds

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to send Discord notification: {e}")
            return False

    def create_embed(self, title, description=None, fields=None, color=0x3498db, footer=None):
        """
        Create a Discord embed object.

        Args:
            title: Embed title
            description: Embed description (optional)
            fields: List of {name, value, inline} dicts (optional)
            color: Color as hex int (default: blue)
            footer: Footer text (optional)

        Returns:
            Embed dict
        """
        embed = {"title": title, "color": color}

        if description:
            # Discord embed description limit is 4096 characters
            embed["description"] = description[:4096]

        if fields:
            # Max 25 fields, each name max 256 chars, value max 1024 chars
            embed["fields"] = []
            for field in fields[:25]:
                embed["fields"].append({
                    "name": str(field.get("name", ""))[:256],
                    "value": str(field.get("value", ""))[:1024],
                    "inline": field.get("inline", False)
                })

        if footer:
            embed["footer"] = {"text": footer[:2048]}

        return embed

    def send_spread_opportunities(self, opportunities, league, base_currency, top_n=5):
        """Send top spread opportunities to Discord."""
        if not self.enabled or not opportunities:
            return False

        fields = []
        for i, opp in enumerate(opportunities[:top_n], 1):
            pair = opp['pair']
            spread = opp['spread']
            percentile = opp.get('percentile', 0)
            min_price = opp.get('min_price', 0)
            max_price = opp.get('max_price', 0)
            base_vol = opp.get('base_volume', 0)
            divine_vol = opp.get('divine_volume', 0)

            # Format prices for readability
            if min_price < 0.001:
                price_range = f"{min_price:.8f} → {max_price:.8f}"
            elif min_price < 1:
                price_range = f"{min_price:.4f} → {max_price:.4f}"
            else:
                price_range = f"{min_price:,.2f} → {max_price:,.2f}"

            # Build volume display
            volume_parts = []
            if base_vol > 0:
                volume_parts.append(f"{base_vol:,.0f} {base_currency.capitalize()}")
            if divine_vol > 0:
                volume_parts.append(f"{divine_vol:,.0f} Divine")
            volume_text = " | ".join(volume_parts) if volume_parts else "No volume data"

            value = (
                f"```\n"
                f"Spread:    {spread:.2%}\n"
                f"Price:     {price_range}\n"
                f"Liquidity: {percentile:.0f}th percentile\n"
                f"Volume:    {volume_text}\n"
                f"```"
            )

            fields.append({
                "name": f"#{i} • {pair.upper()}",
                "value": value,
                "inline": False
            })

        embed = self.create_embed(
            title=f"📊 Top Spread Opportunities",
            description=f"**League:** {league}\n**Base Currency:** {base_currency.capitalize()}\n\nMarkets with highest historical volatility",
            fields=fields,
            color=0x2ecc71,  # Green
            footer="VaalStreetBets • Historical data analysis"
        )

        return self.send_message(embeds=[embed])

    def send_triangular_trades(self, opportunities, league, base_currency, top_n=10):
        """Send top triangular trade opportunities to Discord."""
        if not self.enabled or not opportunities:
            return False

        fields = []
        for i, opp in enumerate(opportunities[:top_n], 1):
            path = opp['path']
            inefficiency = opp['inefficiency']
            percentile = opp.get('volume_percentile', 0)
            base_vol = opp.get('base_volume', 0)
            divine_vol = opp.get('divine_volume', 0)

            # Build volume display
            volume_parts = []
            if base_vol > 0:
                volume_parts.append(f"{base_vol:,.0f} {base_currency.capitalize()}")
            if divine_vol > 0:
                volume_parts.append(f"{divine_vol:,.0f} Divine")
            volume_text = " | ".join(volume_parts) if volume_parts else "No volume"

            # Create step-by-step trade description
            if 'amount_a_start' in opp:
                profit = opp['amount_a_end'] - opp['amount_a_start']
                profit_pct = (profit / opp['amount_a_start']) * 100

                # Format amounts for readability
                def fmt_amt(amt):
                    if amt < 0.01:
                        return f"{amt:.6f}"
                    elif amt < 1:
                        return f"{amt:.4f}"
                    else:
                        return f"{amt:,.2f}"

                steps_text = (
                    f"```\n"
                    f"Path:     {path}\n"
                    f"Return:   {inefficiency:.2%} ({profit_pct:.1f}%)\n"
                    f"Liquidity: {percentile:.0f}th percentile\n"
                    f"\n"
                    f"Trade Steps (starting with {fmt_amt(opp['amount_a_start'])} {opp['curr_a'].upper()}):\n"
                    f"  1. {fmt_amt(opp['amount_a_start'])} {opp['curr_a'].upper()} → {fmt_amt(opp['amount_b'])} {opp['curr_b'].upper()}\n"
                    f"  2. {fmt_amt(opp['amount_b'])} {opp['curr_b'].upper()} → {fmt_amt(opp['amount_c'])} {opp['curr_c'].upper()}\n"
                    f"  3. {fmt_amt(opp['amount_c'])} {opp['curr_c'].upper()} → {fmt_amt(opp['amount_a_end'])} {opp['curr_a'].upper()}\n"
                    f"\n"
                    f"Profit:   {fmt_amt(profit)} {opp['curr_a'].upper()}\n"
                    f"Volume:   {volume_text}\n"
                    f"```"
                )
            else:
                steps_text = (
                    f"```\n"
                    f"Path:      {path}\n"
                    f"Return:    {inefficiency:.2%}\n"
                    f"Liquidity: {percentile:.0f}th percentile\n"
                    f"Volume:    {volume_text}\n"
                    f"```"
                )

            fields.append({
                "name": f"#{i} • Triangular Path",
                "value": steps_text,
                "inline": False
            })

        embed = self.create_embed(
            title=f"🔺 Top Triangular Trades",
            description=f"**League:** {league}\n**Base Currency:** {base_currency.capitalize()}\n\n⚠️ Historical price patterns - NOT executable arbitrage",
            fields=fields,
            color=0xe74c3c,  # Red
            footer="VaalStreetBets • Uses historical min prices for analysis"
        )

        return self.send_message(embeds=[embed])

    def send_persistent_markets(self, markets, league, base_currency, hours, top_n=5):
        """Send persistent high-spread markets to Discord."""
        if not self.enabled or not markets:
            return False

        fields = []
        for i, market in enumerate(markets[:top_n], 1):
            market_id = market['market_id']
            currencies = market_id.split('|')
            pair = f"{currencies[0].upper()} ↔ {currencies[1].upper()}"

            persistence = market['persistence_ratio']
            avg_spread = market['avg_spread']
            latest_spread = market.get('latest_spread', 0)
            avg_base_vol = market.get('avg_base_volume', 0)
            avg_divine_vol = market.get('avg_divine_volume', 0)

            # Build volume display
            volume_parts = []
            if avg_base_vol > 0:
                volume_parts.append(f"{avg_base_vol:,.0f} {base_currency.capitalize()}/hr")
            if avg_divine_vol > 0:
                volume_parts.append(f"{avg_divine_vol:,.0f} Divine/hr")
            volume_text = " | ".join(volume_parts) if volume_parts else "No volume"

            value = (
                f"```\n"
                f"Persistence: {persistence:.0%} ({market['hours_with_spread']}/{market['total_hours']} hours)\n"
                f"Avg Spread:  {avg_spread:.2%}\n"
                f"Latest:      {latest_spread:.2%}\n"
                f"Avg Volume:  {volume_text}\n"
                f"```"
            )

            fields.append({
                "name": f"#{i} • {pair}",
                "value": value,
                "inline": False
            })

        embed = self.create_embed(
            title=f"⏱️ Persistent Markets",
            description=f"**League:** {league}\n**Timeframe:** {hours} hours\n\nMarkets with consistently high spreads",
            fields=fields,
            color=0x9b59b6,  # Purple
            footer="VaalStreetBets • Multi-hour trend analysis"
        )

        return self.send_message(embeds=[embed])

    def send_trending_markets(self, markets, league, base_currency, lookback_hours, top_n=5):
        """Send trending (widening spread) markets to Discord."""
        if not self.enabled or not markets:
            return False

        fields = []
        for i, market in enumerate(markets[:top_n], 1):
            market_id = market['market_id']
            currencies = market_id.split('|')
            pair = f"{currencies[0].upper()} ↔ {currencies[1].upper()}"

            spread = market['latest_spread']
            avg_spread = market.get('avg_recent_spread', 0)
            trend_slope = market['trend_slope']
            spread_change = market.get('spread_change', 0)
            avg_base_vol = market.get('avg_base_volume', 0)
            avg_divine_vol = market.get('avg_divine_volume', 0)

            # Build volume display
            volume_parts = []
            if avg_base_vol > 0:
                volume_parts.append(f"{avg_base_vol:,.0f} {base_currency.capitalize()}/hr")
            if avg_divine_vol > 0:
                volume_parts.append(f"{avg_divine_vol:,.0f} Divine/hr")
            volume_text = " | ".join(volume_parts) if volume_parts else "No volume"

            # Trend indicator
            if spread_change > 0:
                trend_emoji = "📈"
            elif spread_change < 0:
                trend_emoji = "📉"
            else:
                trend_emoji = "➡️"

            value = (
                f"```\n"
                f"Current:    {spread:.2%} {trend_emoji}\n"
                f"Average:    {avg_spread:.2%}\n"
                f"Change:     {spread_change:+.2%}\n"
                f"Trend:      {trend_slope:.4f} (widening)\n"
                f"Avg Volume: {volume_text}\n"
                f"```"
            )

            fields.append({
                "name": f"#{i} • {pair}",
                "value": value,
                "inline": False
            })

        embed = self.create_embed(
            title=f"📈 Trending Markets",
            description=f"**League:** {league}\n**Lookback:** {lookback_hours} hours\n\nMarkets with increasing volatility",
            fields=fields,
            color=0xf39c12,  # Orange
            footer="VaalStreetBets • Trend analysis"
        )

        return self.send_message(embeds=[embed])

    def send_summary(self, league, base_currency, spread_count, triangular_count, persistent_count, trending_count):
        """Send a summary notification."""
        if not self.enabled:
            return False

        description = (
            f"**League:** {league}\n"
            f"**Base Currency:** {base_currency.capitalize()}\n\n"
            f"```\n"
            f"Spread Opportunities: {spread_count}\n"
            f"Triangular Trades:    {triangular_count}\n"
            f"Persistent Markets:   {persistent_count}\n"
            f"Trending Markets:     {trending_count}\n"
            f"```"
        )

        embed = self.create_embed(
            title=f"✅ Market Analysis Complete",
            description=description,
            color=0x3498db,  # Blue
            footer="VaalStreetBets • Analysis complete"
        )

        return self.send_message(embeds=[embed])
