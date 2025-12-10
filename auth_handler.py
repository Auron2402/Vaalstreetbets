import requests
import json

# --- Configuration ---
from config import CLIENT_ID, CLIENT_SECRET, USER_AGENT

# GGG's OAuth2 endpoints
TOKEN_URL = 'https://www.pathofexile.com/oauth/token'

def get_access_token_client_credentials():
    """
    Gets an access token using the Client Credentials grant and saves it to a file.
    """
    headers = {
        'User-Agent': USER_AGENT
    }
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials',
        'scope': 'service:cxapi'
    }

    print("Requesting access token using Client Credentials grant...")
    try:
        response = requests.post(TOKEN_URL, data=payload, headers=headers)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
        
        token = response.json()
        print("Successfully obtained access token!")
        
        with open("token.json", "w") as f:
            json.dump(token, f)
        print("Token saved to token.json")
        return token
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if e.response is not None:
            print(f"Error details: {e.response.text}")
        return None


if __name__ == '__main__':
    get_access_token_client_credentials()
