import os
from datetime import datetime
import requests
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_API_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_API_KEY in the .env file.")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

def fetch_crypto_price(crypto_id: str) -> float:
    """
    Fetches the current price of the specified cryptocurrency in USD using CoinGecko API.

    :param crypto_id: The CoinGecko ID of the cryptocurrency (e.g., 'bitcoin', 'ethereum')
    :return: Current price in USD
    """
    url = 'https://api.coingecko.com/api/v3/simple/price'
    params = {
        'ids': crypto_id,
        'vs_currencies': 'usd'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        price = data[crypto_id]['usd']
        return price
    except requests.RequestException as e:
        print(f"Error fetching {crypto_id} price: {e}")
        return None

def store_price(table_name: str, price: float):
    """
    Stores the given price in the specified Supabase table.

    :param table_name: Name of the Supabase table ('btc_prices' or 'eth_prices')
    :param price: The cryptocurrency price to store
    """
    if price is None:
        print(f"Price is None. Skipping insertion into {table_name}.")
        return

    try:
        data = {
            'prices': price,
            'created_at': datetime.utcnow().isoformat()
        }
        response = supabase.table(table_name).insert(data).execute()
        if response.status_code == 201:
            print(f"Successfully inserted price into {table_name}: {price}")
        else:
            print(f"Failed to insert price into {table_name}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error inserting into {table_name}: {e}")

def main():
    # Fetch prices
    btc_price = fetch_crypto_price('bitcoin')
    eth_price = fetch_crypto_price('ethereum')

    # Store prices in Supabase
    store_price('btc_prices', btc_price)
    store_price('eth_prices', eth_price)

if __name__ == "__main__":
    main()
