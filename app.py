import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
import feedparser

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro Stock AI", layout="wide")

# --- 1. SESSION STATE (For Watchlist & Password) ---
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = ["RELIANCE.NS", "TCS.NS"] 

if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

# --- 2. TOP STOCKS LIST ---
TOP_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LICI.NS", "LT.NS", "AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS",
    "TATAMOTORS.NS", "ADANIENT.NS", "WIPRO.NS", "NTPC.NS", "POWERGRID.NS",
    "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS", "ZOMATO.NS"
]

# --- 3. HELPER FUNCTIONS ---
def check_password():
    if st.session_state["password_correct"]:
        return True
    password = st.sidebar.text_input("🔑 Enter Password", type="password")
    if password == "12345":
        st.session_state["password_correct"] = True
        st.rerun()
    return False

def calculate_rsi_series(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    # Safety: Add 1e-10 to avoid division by zero
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_google_news(ticker):
    clean_name = ticker.replace(".NS", "").replace(".BO", "")
    rss_url = f"https://news.google.com/rss/search?q={clean_name}+stock+news+india&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries[:3]

def get_fundamentals(ticker):
    """Fetches company health data (Market Cap, P/E, etc.)"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "Market Cap": info.get("marketCap", "N/A"),
            "P/E Ratio": info.get("trailingPE", "N/A"),
            "52W High": info.get("fiftyTwoWeekHigh", "N/A"),
            "Sector": info.get("sector", "Unknown"),
        }
    except:
        return None

# --- 4. SCANNER ENGINE ---
@st.cache_data(ttl=600)
def scan_market():
    # Download data for all stocks at once
    data = yf.download(TOP_STOCKS, period="3mo", progress=False)
    
    # Fix for yfinance MultiIndex issue
    if isinstance(data.columns, pd.MultiIndex):
        try: close_data = data['Close']
        except KeyError: close_data = data.xs('Close', level=0, axis=1)
    else:
        close_data = data['Close']

    buy_list = []
    sell_list = []
    
    for ticker in TOP_STOCKS:
        try:
            prices = close_data[ticker].dropna()
            if len(prices) < 50: continue
            current_price = prices.iloc[-1]
            rsi = calculate_rsi_series(prices).iloc[-1]
            
            if rsi < 35:
                buy_list.append({"Stock": ticker, "Price": f"₹{current_price:.1f}", "RSI": f"{rsi:.1f}"})
            elif rsi > 65:
                sell_list.append({"Stock": ticker, "Price": f"₹{current_price:.1f}", "RSI": f"{rsi:.1f}"})
        except Exception:
            continue     
    return pd.DataFrame(buy_list), pd.DataFrame(sell_list)

# --- 5. MAIN APP UI ---
if check_password():
    st.title("⚡ Pro Stock AI: Ultimate Edition")

    # --- SIDEBAR: WATCHLIST ---
    st.sidebar.divider()
    st.sidebar.header("⭐ My Watchlist")
    
    if st.session_state["watchlist"]:
        # Fetch live data for watchlist
        wl_data = yf.download(st.session_state["watchlist"], period="5d", progress=False)['Close']
        
        # Handle single stock case
        if isinstance(wl_data, pd.Series):
             wl_data = wl_data.to_frame(name=st.session_state["watchlist"][0])

        for stock in st.session_state["watchlist"]:
            try:
                if stock in wl_data.columns:
                    price = wl_data[stock].iloc[-1]
                    # Mini card layout
                    col_a, col_b = st.sidebar.columns([3, 1])
                    col_a.metric(stock, f"₹{price:,.1f}")
                    if col_b.button("❌", key=f"del_{stock}"):
                        st.session_state["watchlist"].remove(stock)
                        st.rerun()
                else:
                     st.sidebar.error(f"Error: {stock}")
            except Exception:
                st.sidebar.write(f"{stock} (Loading...)")
    else:
        st.sidebar.info("Watchlist is empty.")

    st.sidebar.divider()

    # --- SECTION A: AUTO SCANNER ---
    with st.expander("📊 OPEN MARKET SCANNER (Top 30 Stocks)", expanded=True):
        buys, sells = scan_market()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🟢 AI Suggested BUYS")
            if not buys.empty: st.dataframe(buys, hide_index=True, use_container_width=True)
            else: st.info("No Buy signals right now.")
        with c2:
            st.subheader("🔴 AI Suggested SELLS")
            if not sells.empty: st.dataframe(sells, hide_index=True, use_container_width=True)
            else: st.success("No Sell signals right now.")

    st.divider()

    # --- SECTION B: DEEP DIVE ---
    st.sidebar.header("🔎 Research Settings")
    
    search_mode = st.sidebar.radio("Search Mode:", ["Select from Top 30", "Search Any Stock"])
    
    if search_mode == "Select from Top 30":
        selected_stock = st.sidebar.selectbox("Choose Stock:", TOP_STOCKS)
    else:
        user_input = st.sidebar.text_input("Enter Symbol (e.g. ZOMATO.NS)", "ZOMATO.NS")
        selected_stock = user_input.upper().strip()
        
    interval_map = {"1 Day": "1d", "1 Week": "1wk", "15 Mins": "15m"}
    time_sel = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))
    
    if st.sidebar.button("Analyze Stock"):
        st.header(f"📊 Analysis: {selected_stock}")
        
        # ADD TO WATCHLIST BUTTON
        c_add, c_msg = st.columns([1, 4])
        if c_add.button("⭐ Add to Watchlist"):
            if selected_stock not in st.session_state["watchlist"]:
                st.session_state["watchlist"].append(selected_stock)
                st.success(f"Added {selected_stock}!")
                st.rerun()
            else:
                st.warning("Already in watchlist.")

        try:
            # 1. SHOW FUNDAMENTALS (New Feature!)
            st.subheader("🏢 Company Health")
            fund_data = get_fundamentals(selected_stock)
            if fund_data:
                f1, f2, f3, f4 = st.columns(4)
                
                # Format Market Cap to Crores
                mcap = fund_data["Market Cap"]
                mcap_fmt = f"₹{mcap/10000000:,.0f} Cr" if isinstance(mcap, (int, float)) else "N/A"
                
                f1.metric("Market Cap", mcap_fmt)
                f2.metric("P/E Ratio", f"{fund_data['P/E Ratio']}")
                f3.metric("52W High", f"₹{fund_data['52W High']}")
                f4.metric("Sector", f"{fund_data['Sector']}")
            else:
                st.warning("Fundamental data not available.")

            st.divider()

            # 2. FETCH CHART DATA
            period = "5d" if interval_map[time_sel] == "15m" else "1y"
            stock = yf.Ticker(selected_stock)
            df = stock.history(period=period, interval=interval_map[time_sel])
            
            if not df.empty:
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
                
                # 3. NEWS
                st.subheader("📰 Latest News")
                news = get_google_news(selected_stock)
                if news:
                    for n in news:
                        st.markdown(f"- [{n.title}]({n.link})")
                        st.caption(n.get("published", "Recent"))
            else:
                st.error("Stock not found. Check symbol.")
        except Exception as e:
            st.error(f"Error: {e}")
