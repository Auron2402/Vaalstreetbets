import requests
import time
import json
import os

# --- Configuration ---
from config import USER_AGENT

# Set Definitions
BASE_API_URL = "https://api.pathofexile.com"


class TradeAPIClient:
    def __init__(self, token_file="token.json", cache_dir="data_exports"):
        self.token_file = token_file
        self.cache_dir = cache_dir
        self.access_token = self._load_token()

        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT,
        }

    def _load_token(self):
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
                return token_data['access_token']
        except (FileNotFoundError, KeyError):
            raise Exception("Token file not found or invalid. Please run auth_handler.py first.")

    def get_currency_exchange_markets(self, realm=None, id=None):
        """
        Fetches currency exchange markets from the API.
        :param realm: The realm to fetch data from (e.g., 'xbox', 'sony'). Defaults to 'pc'.
        :param id: A unix timestamp to fetch data from a specific time.
        :return: The JSON response from the API.
        """
        url = f"{BASE_API_URL}/currency-exchange"
        if realm:
            url += f"/{realm}"
        if id:
            url += f"/{id}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An API error occurred: {e}")
            if e.response and e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 60))
                print(f"Rate limited. Waiting for {retry_after} seconds.")
                time.sleep(retry_after)
            return None

    def fetch_hourly_data(self, timestamp, realm=None):
        """
        Fetch or load cached market data for a specific hour.
        Implements caching to avoid redundant API calls.

        Args:
            timestamp: Unix timestamp for the hour
            realm: Optional realm (e.g., 'xbox', 'sony'). Defaults to PC.

        Returns:
            Market data dictionary or None
        """
        # Generate cache filename
        realm_suffix = f"_{realm}" if realm else ""
        filename = os.path.join(self.cache_dir, f"currency_exchange_markets{realm_suffix}_{timestamp}.json")

        # Check if cached data exists
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError):
                print(f"Could not read cached data for timestamp {timestamp}")

        # Fetch from API
        print(f"Fetching data for timestamp {timestamp}...")
        exchange_markets = self.get_currency_exchange_markets(realm=realm, id=timestamp)

        if exchange_markets:
            # Save to cache
            try:
                with open(filename, "w") as f:
                    json.dump(exchange_markets, f, indent=4)
                print(f"Saved market data to {filename}")
            except IOError as e:
                print(f"Warning: Could not cache data to {filename}: {e}")
            return exchange_markets

        return None
