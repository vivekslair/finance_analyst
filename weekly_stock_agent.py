import os
import yfinance as yf
import pandas as pd
import yagmail
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
import logging
from datetime import datetime

# Load environment variables from .env
load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Create logs directory if it doesn't exist
if not os.path.exists("logs"):
    os.makedirs("logs")

# Setup logging configuration
log_filename = f"logs/stock_agent_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,  # You can change the level to DEBUG for more verbose logging
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# === STEP 1: Fetch stock data (NSE Stocks)
def get_nifty_100_stocks():
    logging.info("Fetching Nifty 100 stock list.")
    # Nifty 100 stocks from Yahoo NSE tickers (manually maintained here for now)
    return ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'LT.NS', 'KOTAKBANK.NS', 'HINDUNILVR.NS', 'SBIN.NS', 'AXISBANK.NS']

# === STEP 2: Analyze last week's return and estimate potential
def analyze_returns(tickers):
    recommendations = []
    for ticker in tickers:
        logging.info(f"Downloading stock data for {ticker}")
        data = yf.download(ticker, period="7d", interval="1d", progress=False)
        
        if data.empty or len(data) < 5:
            logging.warning(f"Insufficient data for {ticker}. Skipping.")
            continue

        last_monday_price = data.iloc[0]['Open'].item()
        friday_price = data.iloc[-1]['Close'].item()
        percent_change = ((friday_price - last_monday_price) / last_monday_price) * 100
        if isinstance(percent_change, pd.Series):
            percent_change = percent_change.item()

        #logging.info(f"{ticker} percent change is: {percent_change:.2f}%")

        if percent_change >= 5:
            recommendations.append({
                'ticker': ticker,
                'change': round(percent_change, 2),
                'entry_price': round(last_monday_price, 2),
                'exit_price': round(friday_price, 2)
            })

    logging.info(f"Found {len(recommendations)} stock(s) meeting the criteria.")
    return sorted(recommendations, key=lambda x: -x['change'])[:2]  # Top 2

# === STEP 3: Send Email
def send_email(recommendations):
    if not recommendations:
        body = "No stock met the 5% return criteria last week."
        logging.info("No stocks met the return criteria. Sending email with no recommendations.")
    else:
        body = "📈 Weekly Stock Picks for This Week:\n\n"
        for stock in recommendations:
            body += (
                f"✅ {stock['ticker']}\n"
                f"   - Entry Price: ₹{stock['entry_price']}\n"
                f"   - Estimated Exit Price: ₹{stock['exit_price']}\n"
                f"   - Estimated Return: {stock['change']}%\n\n"
            )
        body += "Sell by: Friday, 2PM IST"
        logging.info("Stocks meeting criteria found, sending email.")

    try:
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
        yag.send(
            to=EMAIL_USER,
            subject="📊 Your Weekly Stock Picks (Indian Market)",
            contents=body
        )
        logging.info("✅ Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")

# === STEP 4: Full Agent Pipeline
def run_stock_agent():
    logging.info("🚀 Running Weekly Stock Agent...")
    stocks = get_nifty_100_stocks()
    picks = analyze_returns(stocks)
    send_email(picks)

# === STEP 5: Schedule every Monday 10AM IST
def start_scheduler():
    scheduler = BlockingScheduler(timezone='Asia/Kolkata')
    scheduler.add_job(run_stock_agent, 'cron', day_of_week='mon', hour=10, minute=0)
    logging.info("⏰ Scheduler started. Waiting for Monday 10AM IST...")
    scheduler.start()

# === Entry point
if __name__ == "__main__":
    logging.info("Starting Weekly Stock Agent.")
    run_stock_agent()  # For immediate test
    # Uncomment below to enable weekly scheduler
    # start_scheduler()