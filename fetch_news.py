import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Configure logging with RotatingFileHandler and StreamHandler
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# File handler for logging to a file with rotation
file_handler = RotatingFileHandler('fetch_news.log', maxBytes=5*1024*1024, backupCount=2)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Stream handler for logging to the console
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Add both handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Load environment variables from .env file
load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# News API credentials
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
NEWS_API_ENDPOINT = 'https://newsapi.org/v2/everything'

def is_relevant_article(article: dict, keyword: str) -> bool:
    """
    Determine if the article is relevant based on the presence of the keyword in the title, description, or content.
    
    Args:
        article (dict): The article data.
        keyword (str): The keyword to check for relevance.

    Returns:
        bool: True if relevant, False otherwise.
    """
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    content = article.get('content', '').lower()
    keyword = keyword.lower()
    
    # Check if keyword appears in the title
    if keyword in title:
        return True
    
    # Check if keyword appears more than once in description or content
    keyword_count = description.count(keyword) + content.count(keyword)
    return keyword_count >= 2  # Adjust the threshold as needed

def fetch_latest_news(query: str) -> str:
    """
    Fetch the latest news article for the given query using qInTitle to ensure relevance,
    and perform additional filtering to confirm relevance.

    Args:
        query (str): The search query (e.g., 'Bitcoin', 'Ethereum').

    Returns:
        str: The title and description of the latest news article.
    """
    params = {
        'qInTitle': query,  # Use qInTitle instead of q
        'sortBy': 'publishedAt',
        'language': 'en',
        'apiKey': NEWS_API_KEY,
        'pageSize': 5  # Fetch multiple articles to increase chances of relevance
        # 'sources': trusted_sources  # Removed to avoid invalid sources
    }
    try:
        response = requests.get(NEWS_API_ENDPOINT, params=params)
        response.raise_for_status()  # Raises HTTPError for bad responses
        data = response.json()
        articles = data.get('articles')
        if articles:
            for article in articles:
                if is_relevant_article(article, query):
                    title = article.get('title')
                    description = article.get('description')
                    return f"{title}: {description}"
            return "No sufficiently relevant articles found."
        else:
            return "No articles found."
    except requests.exceptions.HTTPError as http_err:
        # Log HTTP errors with detailed information
        try:
            error_info = response.json()
            logger.error(f"HTTP error occurred for {query}: {error_info}")
        except ValueError:
            # If response is not JSON
            logger.error(f"HTTP error occurred for {query}: {http_err}")
        return f"Error fetching news for {query}: {http_err}"
    except requests.exceptions.RequestException as req_err:
        # Log other request-related errors
        logger.error(f"Request exception for {query}: {req_err}")
        return f"Error fetching news for {query}: {req_err}"

def insert_news(table: str, news: str):
    """
    Insert a news item into the specified Supabase table.

    Args:
        table (str): The table name ('btc_news' or 'eth_news').
        news (str): The news content to insert.
    """
    data = {
        'news': news,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    try:
        response = supabase.table(table).insert(data).execute()
        if not response.error:
            logger.info(f"Successfully inserted news into {table}.")
        else:
            logger.error(f"Failed to insert news into {table}: {response.error}")
    except Exception as e:
        logger.error(f"Exception occurred while inserting into {table}: {e}")

def main():
    # Define precise queries
    btc_query = 'Bitcoin'  # You can further refine the query if needed
    eth_query = 'Ethereum'  # You can further refine the query if needed
    
    # Fetch latest BTC news
    btc_news = fetch_latest_news(btc_query)
    logger.info(f"Fetched BTC News: {btc_news}")
    insert_news('btc_news', btc_news)

    # Fetch latest ETH news
    eth_news = fetch_latest_news(eth_query)
    logger.info(f"Fetched ETH News: {eth_news}")
    insert_news('eth_news', eth_news)

if __name__ == "__main__":
    main()
