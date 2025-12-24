import pandas as pd
import numpy as np
from textblob import TextBlob
import requests
import json

# --- Technical Analysis ---

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, slow=26, fast=12, signal=9):
    exp1 = data['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_moving_averages(data):
    data['SMA_50'] = data['Close'].rolling(window=50).mean()
    data['SMA_200'] = data['Close'].rolling(window=200).mean()
    return data

def get_technical_signals(data):
    """
    Returns a dictionary of technical signals based on the latest data.
    """
    if len(data) < 200:
        return {
            "rsi": 50, "macd": 0, "macd_signal": 0, "price": data.iloc[-1]['Close'],
            "sma_50": 0, "sma_200": 0, "bullish_signal": False, "bearish_signal": False,
            "overbought": False, "reason": "Insufficient Data"
        }
        
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    
    signals = {
        "rsi": latest.get('RSI', 50),
        "macd": latest.get('MACD', 0),
        "macd_signal": latest.get('MACD_Signal', 0),
        "price": latest.get('Close', 0),
        "sma_50": latest.get('SMA_50', 0),
        "sma_200": latest.get('SMA_200', 0),
        "bullish_signal": False,
        "bearish_signal": False,
        "overbought": False,
        "oversold": False
    }
    
    # Logic defined in prompt
    if signals['rsi'] < 30 and signals['price'] > signals['sma_200']:
        signals['bullish_signal'] = True
        signals['reason'] = "Oversold (RSI < 30) in an Uptrend (Price > 200 SMA)"
    elif signals['rsi'] > 70:
        signals['overbought'] = True
        signals['reason'] = "RSI indicates Overbought conditions (> 70)"
    elif signals['macd'] > signals['macd_signal'] and prev['MACD'] <= prev['MACD_Signal']:
        signals['bullish_signal'] = True
        signals['reason'] = "MACD Bullish Crossover"
    elif signals['macd'] < signals['macd_signal'] and prev['MACD'] >= prev['MACD_Signal']:
        signals['bearish_signal'] = True
        signals['reason'] = "MACD Bearish Crossover"
    else:
        signals['reason'] = "Neutral / No clear Setup"
        
    return signals

# --- News & Sentiment Analysis ---

def analyze_news_sentiment(news_items):
    """
    Analyzes a list of news dictionaries.
    Returns average polarity and a summary of sentiments.
    """
    if not news_items:
        return 0, "No news found"
    
    total_polarity = 0
    analyzed_count = 0
    
    for item in news_items:
        title = item.get('title', '')
        if title:
            blob = TextBlob(title)
            total_polarity += blob.sentiment.polarity
            analyzed_count += 1
            
    avg_polarity = total_polarity / analyzed_count if analyzed_count > 0 else 0
    
    sentiment_label = "Neutral"
    if avg_polarity > 0.1:
        sentiment_label = "Positive"
    elif avg_polarity < -0.1:
        sentiment_label = "Negative"
        
    return avg_polarity, sentiment_label

# --- LLM Integration Helper ---

def generate_llm_prompt(ticker, signals, news_sentiment_label, news_items):
    """
    Creates a structured prompt that can be sent to an LLM.
    """
    # Safe list comprehension
    if not news_items:
        news_summary = "No recent news available."
    else:
        news_summary = "\n".join([f"- {item.get('title', 'No Title')}" for item in news_items[:3]])
    
    prompt = f"""
    Act as a financial analyst. Analyze the following data for {ticker}:
    
    1. Technical Indicators:
       - Price: {signals['price']:.2f}
       - RSI: {signals['rsi']:.2f}
       - MACD: {signals['macd']:.2f} vs Signal: {signals['macd_signal']:.2f}
       - 200 SMA: {signals['sma_200']:.2f}
       - Primary Signal: {signals.get('reason', 'None')}
       
    2. News Sentiment: {news_sentiment_label}
    3. Recent Headlines:
    {news_summary}
    
    Based on this, provide a 3-sentence summary of the stock's current outlook. 
    State clearly if it looks Bullish, Bearish, or Neutral, but include a disclaimer that this is not financial advice.
    """
    return prompt

def query_llm(prompt, api_url):
    """
    Sends the prompt to a custom LLM API (e.g., ngrok endpoint).
    """
    headers = {'Content-Type': 'application/json'}
    # Some APIs expect 'prompt', some 'text', some 'messages'. 
    # We send 'prompt' as a standard default for custom endpoints.
    payload = {"prompt": prompt} 
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            try:
                # Attempt to parse JSON response
                data = response.json()
                # Try to find the answer in common keys
                if isinstance(data, dict):
                    return data.get('response') or data.get('text') or data.get('content') or data.get('generated_text') or str(data)
                return str(data)
            except json.JSONDecodeError:
                # If not JSON, return raw text
                return response.text
        else:
            return f"Error: API returned status code {response.status_code}. Response: {response.text}"
            
    except requests.exceptions.MissingSchema:
        return "Error: Invalid URL. Make sure it starts with http:// or https://"
    except Exception as e:
        return f"Error connecting to API: {str(e)}"