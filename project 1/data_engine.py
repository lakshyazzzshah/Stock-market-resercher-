import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_stock_data(ticker_symbol, period="1y"):
    """
    Fetches historical stock data for the given ticker.
    Appends .NS if not present (assuming NSE preference).
    """
    if not ticker_symbol.endswith(".NS") and not ticker_symbol.endswith(".BO"):
        ticker_symbol = f"{ticker_symbol}.NS"
    
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period=period)
        
        if df.empty:
            return None, None
            
        # Get basic info
        info = stock.info
        return df, info
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None

def get_stock_news(ticker_symbol):
    """
    Fetches recent news using yfinance's built-in news provider.
    """
    if not ticker_symbol.endswith(".NS") and not ticker_symbol.endswith(".BO"):
        ticker_symbol = f"{ticker_symbol}.NS"
        
    try:
        stock = yf.Ticker(ticker_symbol)
        news = stock.news
        return news
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []