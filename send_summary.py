import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
import openai
import logging
from logging.handlers import RotatingFileHandler
from tenacity import retry, stop_after_attempt, wait_fixed

# ================================
# 1. Configure Logging
# ================================

# Create a custom logger
logger = logging.getLogger('send_summary')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = RotatingFileHandler('send_summary.log', maxBytes=5*1024*1024, backupCount=2)
console_handler = logging.StreamHandler()

# Create formatters and add them to handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ================================
# 2. Load Environment Variables
# ================================

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# OpenAI credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Gmail SMTP credentials
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
GMAIL_RECIPIENT_EMAIL = os.getenv('GMAIL_RECIPIENT_EMAIL')

# Validate Environment Variables
required_vars = [
    'SUPABASE_URL', 'SUPABASE_KEY',
    'OPENAI_API_KEY',
    'GMAIL_USER', 'GMAIL_APP_PASSWORD',
    'GMAIL_RECIPIENT_EMAIL'
]

missing_vars = [var for var in required_vars if os.getenv(var) is None]
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    exit(1)

# ================================
# 3. Initialize Clients
# ================================

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI client
from openai import OpenAI

openai_client = OpenAI(
    api_key=OPENAI_API_KEY  # You can omit this if it's already set in environment variables
)

# ================================
# 4. Define Helper Functions
# ================================

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def fetch_latest_entry(table: str, column: str) -> dict:
    """
    Fetch the latest entry for a specific column from a given Supabase table based on 'created_at'.

    Args:
        table (str): The table name.
        column (str): The column to fetch.

    Returns:
        dict: The latest record containing the specified column.
    """
    try:
        response = supabase.table(table).select(column).order("created_at", desc=True).limit(1).execute()

        # Debugging: Log the raw response
        logger.debug(f"Response from {table}: {response}")

        # Access the data
        data = response.data
        if data:
            return data[0]
        else:
            logger.warning(f"No data found in table {table}.")
            return {}
    except Exception as e:
        logger.error(f"Exception while fetching from {table}: {e}")
        raise  # To trigger retry

def generate_summary(prompt: str) -> str:
    """
    Generate a summary using OpenAI GPT-3.5 with the updated SDK.

    Args:
        prompt (str): The prompt for GPT-3.5.

    Returns:
        str: The generated summary.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes information concisely."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,  # Approximately 100 words
            temperature=0.5,
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return "Summary generation failed."

def send_email(subject: str, body: str) -> bool:
    """
    Send an email using Gmail's SMTP server.

    Args:
        subject (str): The email subject.
        body (str): The email body.

    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_RECIPIENT_EMAIL
        msg['Subject'] = subject

        # Attach the body with MIMEText
        msg.attach(MIMEText(body, 'plain'))

        # Connect to Gmail's SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure the connection
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        text = msg.as_string()
        server.sendmail(GMAIL_USER, GMAIL_RECIPIENT_EMAIL, text)
        server.quit()
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Exception while sending email: {e}")
        return False

def compose_email(btc_summary: str, eth_summary: str) -> str:
    """
    Compose the email body with BTC and ETH summaries.

    Args:
        btc_summary (str): BTC summary.
        eth_summary (str): ETH summary.

    Returns:
        str: The complete email body.
    """
    email_body = (
        f"**Bitcoin (BTC) Summary:**\n{btc_summary}\n\n"
        f"**Ethereum (ETH) Summary:**\n{eth_summary}"
    )
    return email_body

# ================================
# 5. Main Execution Flow
# ================================

def main():
    # Fetch latest BTC price and news
    btc_price_entry = fetch_latest_entry('btc_prices', 'prices')
    btc_news_entry = fetch_latest_entry('btc_news', 'news')

    # Fetch latest ETH price and news
    eth_price_entry = fetch_latest_entry('eth_prices', 'prices')
    eth_news_entry = fetch_latest_entry('eth_news', 'news')

    # Check if all necessary data is available
    if not btc_price_entry or not btc_news_entry:
        logger.error("Incomplete BTC data. Aborting email composition.")
        return
    if not eth_price_entry or not eth_news_entry:
        logger.error("Incomplete ETH data. Aborting email composition.")
        return

    # Extract the relevant data
    btc_price = btc_price_entry.get('prices', 'N/A')
    btc_news = btc_news_entry.get('news', 'N/A')

    eth_price = eth_price_entry.get('prices', 'N/A')
    eth_news = eth_news_entry.get('news', 'N/A')

    # Prepare prompts for GPT-3.5
    btc_prompt = (
        f"Provide a concise 100-word analysis based on the following Bitcoin price and news:\n"
        f"Price: ${btc_price}\n"
        f"News: {btc_news}"
    )

    eth_prompt = (
        f"Provide a concise 100-word analysis based on the following Ethereum price and news:\n"
        f"Price: ${eth_price}\n"
        f"News: {eth_news}"
    )

    # Generate summaries
    btc_summary = generate_summary(btc_prompt)
    eth_summary = generate_summary(eth_prompt)

    # Compose email
    email_subject = f"Crypto Update - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    email_body = compose_email(btc_summary, eth_summary)

    # Send email
    send_email(email_subject, email_body)

if __name__ == "__main__":
    main()
