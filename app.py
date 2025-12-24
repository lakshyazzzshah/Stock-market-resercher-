import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
import feedparser

# --- 1. PASSWORD PROTECTION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == "12345": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Wrong password. Try again:", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

# --- 2. TECHNICAL INDICATORS ---
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def add_technical_indicators(data):
    # Simple Moving Averages
    data['SMA_50'] = data['Close'].rolling(window=50).mean()
    data['SMA_200'] = data['Close'].rolling(window=200).mean()
    data['RSI'] = calculate_rsi(data)
    
    # EMA (Exponential Moving Average) - Faster response for short timeframes
    data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
    return data

def get_google_news(ticker):
    clean_name = ticker.replace(".NS", "").replace(".BO", "")
    rss_url = f"https://news.google.com/rss/search?q={clean_name}+stock+news+india&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries[:5]

# --- 3. MAIN APP ---
if check_password():
    st.set_page_config(page_title="Pro Stock AI", layout="wide")
    st.title("⚡ Real-Time AI Stock Hunter")

    # --- SIDEBAR SETTINGS ---
    st.sidebar.header("🔍 Search & Time")
    ticker = st.sidebar.text_input("Stock Symbol", "RELIANCE.NS")
    
    # NEW: Interval Selection (Candle Time)
    interval_map = {
        "1 Minute (Intraday)": "1m",
        "5 Minutes (Intraday)": "5m",
        "15 Minutes (Intraday)": "15m",
        "30 Minutes": "30m",
        "1 Hour": "1h",
        "1 Day (Daily)": "1d",
        "1 Week": "1wk"
    }
    
    selected_label = st.sidebar.selectbox("Select Graph Time:", list(interval_map.keys()), index=5)
    interval = interval_map[selected_label]

    # LOGIC: If timeframe is short (minutes), we can only get max 7 days of data
    if interval in ["1m", "5m", "15m", "30m", "1h"]:
        period = "5d"  # Force short history for intraday
        st.sidebar.info("⚠️ Intraday Mode: Showing last 5 days only.")
    else:
        period = "1y"  # Long history for daily charts

    # REFRESH BUTTON
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.rerun()

    if ticker:
        try:
            # A. FETCH DATA
            stock = yf.Ticker(ticker)
            data = stock.history(period=period, interval=interval)
            
            if not data.empty:
                data = add_technical_indicators(data)
                
                # B. LIVE PRICE HEADER
                current_price = data['Close'].iloc[-1]
                prev_price = data['Close'].iloc[-2] if len(data) > 1 else current_price
                change = current_price - prev_price
                pct_change = (change / prev_price) * 100
                
                col1, col2, col3 = st.columns([1, 1, 2])
                col1.metric("Live Price", f"₹{current_price:,.2f}", f"{pct_change:.2f}%")
                
                # Market Status Label
                if pct_change > 0:
                    st.toast(f"📈 {ticker} is going UP!")
                else:
                    st.toast(f"📉 {ticker} is going DOWN!")

                # C. INTERACTIVE CHART
                fig = go.Figure()
                
                # Candles
                fig.add_trace(go.Candlestick(x=data.index,
                                open=data['Open'], high=data['High'],
                                low=data['Low'], close=data['Close'],
                                name="Price"))
                
                # Indicators (Only show SMA on Daily, EMA on Intraday)
                if interval in ["1d", "1wk"]:
                    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_50'], line=dict(color='orange', width=1), name="50 SMA"))
                    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_200'], line=dict(color='blue', width=1), name="200 SMA"))
                else:
                    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_20'], line=dict(color='purple', width=1), name="20 EMA (Fast)"))

                fig.update_layout(height=550, xaxis_rangeslider_visible=False, title=f"{ticker} - {selected_label} Chart")
                st.plotly_chart(fig, use_container_width=True)

                # D. AI SUGGESTION ENGINE
                st.subheader("🤖 AI Trading Signal")
                
                # Get latest values
                rsi = data['RSI'].iloc[-1]
                close = data['Close'].iloc[-1]
                ema_20 = data['EMA_20'].iloc[-1]
                
                # --- AI DECISION LOGIC ---
                signal = "HOLD / NEUTRAL"
                color = "blue"
                reason = "Market is choppy. No clear trend."

                # BUY LOGIC
                if rsi < 30:
                    signal = "STRONG BUY"
                    color = "green"
                    reason = "Price is Oversold (Cheap). High chance of reversal upwards."
                elif rsi < 45 and close > ema_20:
                    signal = "BUY"
                    color = "green"
                    reason = "RSI is healthy and price is above the short-term trend line."

                # SELL LOGIC
                elif rsi > 70:
                    signal = "STRONG SELL"
                    color = "red"
                    reason = "Price is Overbought (Expensive). High chance of crash."
                elif rsi > 55 and close < ema_20:
                    signal = "SELL"
                    color = "red"
                    reason = "Momentum is fading and price dropped below trend line."

                # DISPLAY SIGNAL
                st.markdown(f"""
                <div style="padding: 20px; background-color: rgba(0,0,0,0.2); border-radius: 10px; border-left: 10px solid {color};">
                    <h2 style="color: {color}; margin:0;">AI Recommendation: {signal}</h2>
                    <p style="font-size: 18px;"><b>Reason:</b> {reason}</p>
                    <p><b>Technical Data:</b> RSI: {rsi:.1f} | Price vs EMA: {'Above' if close > ema_20 else 'Below'}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.caption("⚠️ Disclaimer: This is an educational AI. Never trade blindly based on computer signals.")
                
                st.divider()

                # E. NEWS
                st.subheader("📰 Market News")
                news = get_google_news(ticker)
                if news:
                    for item in news:
                        st.markdown(f"**[{item.title}]({item.link})**")
                        st.caption(f"{item.published}")
                else:
                    st.info("No news found.")

            else:
                st.error("Data not available for this interval. Try '1 Day'.")
        except Exception as e:
            st.error(f"Error: {e}")