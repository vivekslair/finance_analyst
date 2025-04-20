import os
import logging
import requests
import yfinance as yf
from dotenv import load_dotenv
from datetime import datetime
import openai
import yagmail

# ==================== Load Environment ====================
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWSDATA_API_KEY")
EMAIL_SENDER="vivekslair@gmail.com"
EMAIL_RECEIVER="vivekslair@gmail.com"  # or any recipient
EMAIL_APP_PASSWORD=os.getenv("EMAIL_PASS")


# ==================== Configure Logging ====================
# Setup timestamped logging
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_folder = "logs"
os.makedirs(log_folder, exist_ok=True)
log_file_path = os.path.join(log_folder, f"execution_{timestamp}.log")

logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== Fetch Stock Data ====================
def fetch_stock_data(tickers):
    logging.info("Fetching stock data...")
    stock_data = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="7d", interval="1d", progress=False)
            if data.empty:
                logging.warning(f"No stock data for {ticker}")
            stock_data[ticker] = data
        except Exception as e:
            logging.error(f"Error fetching stock data for {ticker}: {e}")
    return stock_data

# ==================== Fetch News from Newsdata.io ====================
def fetch_newsdata(stock_name, api_key):
    logging.info(f"Fetching news for {stock_name}...")
    url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={stock_name}&country=in&language=en&category=business"
    logging.info("URL to fetch info is:",url)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success" or "results" not in data:
            logging.warning(f"No news articles found for {stock_name}")
            return f"No news articles found for {stock_name}."
        articles = data["results"][:5]
        return "\n\n".join([
            f"{i+1}. {a['title']} - {a.get('description', '')}" for i, a in enumerate(articles)
        ])
    except Exception as e:
        logging.error(f"Error fetching news for {stock_name}: {e}")
        return f"Error fetching news for {stock_name}: {e}"

# ==================== Sentiment Analysis ====================
def analyze_sentiment(stock_name, news):
    logging.info(f"Analyzing sentiment for {stock_name}...")
    try:
        prompt = f"Analyze the sentiment of the following news related to {stock_name}:\n\n{news}"

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a financial assistant specialized in stock sentiment analysis."},
                {"role": "user", "content": prompt}
            ]
        )
        sentiment = response.choices[0].message.content.strip()
        return sentiment
    except Exception as e:
        logging.error(f"Error analyzing sentiment for {stock_name}: {e}")
        return "Sentiment analysis failed."

# ==================== Generate Recommendations ====================
def make_recommendations(stock_data, sentiment_analysis):
    logging.info("Generating recommendations...")
    recommendations = []

    for ticker, data in stock_data.items():
        try:
            if data.empty or len(data) < 2:
                logging.warning(f"Insufficient data for {ticker}")
                continue

            open_price = data.iloc[0]['Open'].item()
            close_price = data.iloc[-1]['Close'].item()
            percent_change = ((close_price - open_price) / open_price) * 100
            sentiment = sentiment_analysis.get(ticker, "")

            if percent_change >= 5 and "positive" in sentiment.lower():
                recommendations.append({
                    'ticker': ticker,
                    'change': round(percent_change, 2),
                    'entry_price': round(open_price, 2),
                    'exit_price': round(close_price, 2),
                    'sentiment': sentiment
                })
        except Exception as e:
            logging.error(f"Error processing recommendation for {ticker}: {e}")
    return recommendations

# ==================== Store Recommendations ====================
def store_recommendations(recommendations):
    logging.info("Storing recommendations...")
    try:
        with open("recommendations.txt", "a") as f:
            for rec in recommendations:
                f.write(f"{datetime.now()} | {rec}\n")
    except Exception as e:
        logging.error(f"Error storing recommendations: {e}")

# ==================== Collect User Feedback ====================
def feedback_loop():
    try:
        feedback = input("How accurate was last week's recommendation? (1-5): ")
        with open("feedback.txt", "a") as f:
            f.write(f"{datetime.now()}: {feedback}\n")
        logging.info("✅ Feedback saved.")
    except Exception as e:
        logging.error(f"Error collecting feedback: {e}")

# ====================Emailing module ============================
def send_email_report(recommendations,stock_data,sentiment_analysis):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")

    try:
        if not recommendations:
            body = "No stock recommendations this week."
        else:
            body = "📊 Weekly Stock Recommendations:\n\n"
            for rec in recommendations:
                body += (
                    f"📈 {rec['ticker']}\n"
                    f" - Sentiment: {rec['sentiment']}\n"
                    f" - Change: {rec['change']}%\n"
                    f" - Entry Price: ₹{rec['entry_price']}\n"
                    f" - Exit Price: ₹{rec['exit_price']}\n\n"
                )

        # Add a detailed summary table
        body += "\n📋 Summary of All Analyzed Stocks:\n"
        body += "{:<12} {:<10} {:<15}\n".format("Ticker", "% Change", "Sentiment")
        body += "-" * 42 + "\n"

        for ticker, data in stock_data.items():
            try:
                open_price = data.iloc[0]["Open"].item()
                close_price = data.iloc[-1]["Close"].item()
                change = round(((close_price - open_price) / open_price) * 100, 2)
                sentiment = sentiment_analysis.get(ticker, "N/A")
                body += "{:<12} {:<10} {:<15}\n".format(ticker, f"{change}%", sentiment[:50])
            except Exception as e:
                logger.warning(f"Could not calculate summary for {ticker}: {e}")

        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
        yag.send(
            to=EMAIL_USER,  # or os.getenv("EMAIL_RECEIVER") if you want a different receiver
            subject="📊 Your Weekly Stock Picks (Indian Market)",
            contents=body
        )
        logger.info("✅ Email sent successfully.")
        print("📧 Email sent to:", EMAIL_USER)

    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        print("❌ Failed to send email.")


# ==================== Main Execution ====================
def main():
    tickers = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'AXISBANK.NS', 'SBIN.NS']
    
    stock_data = fetch_stock_data(tickers)

    sentiment_analysis = {}
    for ticker in tickers:
        news = fetch_newsdata(ticker, NEWS_API_KEY)
        sentiment = analyze_sentiment(ticker, news)
        sentiment_analysis[ticker] = sentiment

    recommendations = make_recommendations(stock_data, sentiment_analysis)
    store_recommendations(recommendations)

    send_email_report(recommendations,stock_data,sentiment_analysis)

    for rec in recommendations:
        print(f"\n📈 {rec['ticker']} Recommendation:\n"
              f"Change: {rec['change']}%\n"
              f"Entry Price: ₹{rec['entry_price']}\n"
              f"Exit Price: ₹{rec['exit_price']}\n"
              f"Sentiment: {rec['sentiment']}\n")

    feedback_loop()

if __name__ == "__main__":
    main()
