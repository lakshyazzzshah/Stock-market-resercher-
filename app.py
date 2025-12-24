import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
import feedparser

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro AI Stock Scanner", layout="wide")

# --- 1. TOP STOCKS LIST (For the Auto-Scanner) ---
TOP_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LICI.NS", "LT.NS", "AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS",
    "TATAMOTORS.NS", "ADANIENT.NS", "WIPRO.NS", "NTPC.NS", "POWERGRID.NS",
    "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS", "ZOMATO.NS"
]

# --- 2. PASSWORD PROTECTION ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def check_password():
    if st.session_state["password_correct"]:
        return True
    
    # Sidebar Password Input
    password = st.sidebar.text_input("🔑 Enter Password", type="password")
    if password == "12345":
        st.session_state["password_correct"] = True
        st.rerun()
    return False

# --- 3. MATH & INDICATORS ---
def calculate_rsi_series(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    # Fix division by zero
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_google_news(ticker):
    clean_name = ticker.replace(".NS", "").replace(".BO", "")
    rss_url = f"https://news.google.com/rss/search?q={clean_name}+stock+news+india&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries[:3]

# --- 4. THE SCANNER ENGINE (This finds the Buy/Sell stocks) ---
@st.cache_data(ttl=600) # Update every 10 mins
def scan_market():
    # Download data for all 30 stocks at once
    data = yf.download(TOP_STOCKS, period="3mo", progress=False)
    
    # Fix for yfinance MultiIndex issue
    if isinstance(data.columns, pd.MultiIndex):
        # If 'Close' is a level, select it. 
        try:
            close_data = data['Close']
        except KeyError:
            # Fallback if structure is different
            close_data = data.xs('Close', level=0, axis=1)
    else:
        close_data = data['Close']

    buy_list = []
    sell_list = []
    
    for ticker in TOP_STOCKS:
        try:
            # Get the price history for this single stock
            prices = close_data[ticker].dropna()
            if len(prices) < 50: continue
            
            current_price = prices.iloc[-1]
            rsi = calculate_rsi_series(prices).iloc[-1]
            
            # SCANNER LOGIC
            if rsi < 35: # Oversold (Buy Signal)
                buy_list.append({"Stock": ticker, "Price": f"₹{current_price:.1f}", "RSI": f"{rsi:.1f}"})
            elif rsi > 65: # Overbought (Sell Signal)
                sell_list.append({"Stock": ticker, "Price": f"₹{current_price:.1f}", "RSI": f"{rsi:.1f}"})
                
        except Exception:
            continue
            
    return pd.DataFrame(buy_list), pd.DataFrame(sell_list)

# --- 5. MAIN APP UI ---
if check_password():
    st.title("⚡ Pro AI Stock Scanner")

    # --- SECTION A: DASHBOARD (SUGGESTIONS) ---
    st.write("### 🤖 Market Opportunities (Top 30 Stocks)")
    
    with st.spinner("Scanning the market..."):
        try:
            buys, sells = scan_market()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🟢 Suggested BUYS (Cheap)")
                if not buys.empty:
                    st.dataframe(buys, hide_index=True, use_container_width=True)
                else:
                    st.info("No strong 'Buy' signals right now.")
            
            with col2:
                st.subheader("🔴 Suggested SELLS (Expensive)")
                if not sells.empty:
                    st.dataframe(sells, hide_index=True, use_container_width=True)
                else:
                    st.success("No strong 'Sell' signals right now.")
        except Exception as e:
            st.error(f"Scanner Error: {e}")

    st.divider()

    # --- SECTION B: DEEP DIVE (CHARTS) ---
    st.sidebar.header("🔎 Research Settings")
    
    # Mode Selection
    search_mode = st.sidebar.radio("Search Mode:", ["Select from Top 30", "Search Any Stock"])
    
    if search_mode == "Select from Top 30":
        selected_stock = st.sidebar.selectbox("Choose Stock:", TOP_STOCKS)
    else:
        user_input = st.sidebar.text_input("Enter Symbol (e.g. ZOMATO.NS)", "ZOMATO.NS")
        selected_stock = user_input.upper().strip()
        
    # Timeframe
    interval_map = {"1 Day": "1d", "1 Week": "1wk", "15 Mins": "15m"}
    time_sel = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))
    
    if st.sidebar.button("Analyze Stock"):
        st.header(f"📊 Analysis: {selected_stock}")
        
        try:
            # Fetch Data
            period = "5d" if interval_map[time_sel] == "15m" else "1y"
            stock = yf.Ticker(selected_stock)
            df = stock.history(period=period, interval=interval_map[time_sel])
            
            if not df.empty:
                # Fix yfinance MultiIndex column issue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                # Add Indicators
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df['RSI'] = calculate_rsi_series(df['Close'])
                df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
                
                # Plot Chart
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
                
                if interval_map[time_sel] == "1d":
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange'), name="50 SMA"))
                else:
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='purple'), name="20 EMA"))
                
                st.plotly_chart(fig, use_container_width=True)
                
                # AI Signal Card
                curr_rsi = df['RSI'].iloc[-1]
                curr_price = df['Close'].iloc[-1]
                
                signal_col = "blue"
                signal_txt = "NEUTRAL"
                
                if curr_rsi < 35:
                    signal_col = "green"
                    signal_txt = "BUY (Oversold)"
                elif curr_rsi > 65:
                    signal_col = "red"
                    signal_txt = "SELL (Overbought)"
                    
                st.markdown(f"""
                <div style="padding:15px; border-radius:10px; background:rgba(0,0,0,0.3); border-left: 8px solid {signal_col};">
                    <h3>AI Signal: <span style="color:{signal_col}">{signal_txt}</span></h3>
                    <p>RSI Strength: {curr_rsi:.1f}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # News
                st.subheader("📰 Latest News")
                news = get_google_news(selected_stock)
                if news:
                    for n in news:
                        st.markdown(f"- [{n.title}]({n.link})")
                        st.caption(n.get("published", "Recent"))
                else:
                    st.info("No news found.")
                    
            else:
                st.error("Stock not found. Check the symbol.")
                
        except Exception as e:
            st.error(f"Error loading data: {e}")
