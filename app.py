import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
import feedparser
import gspread
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro Stock AI", layout="wide")

# --- 1. GOOGLE SHEETS DATABASE CONNECTION ---
def get_client():
    """Connects to Google Sheets using the modern method"""
    try:
        # Create a dictionary from the secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # FIX: Ensure private key has correct newlines
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        # Connect using gspread directly (Modern Way)
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

def init_db():
    """Loads data from the database"""
    try:
        client = get_client()
        if not client: return None
        
        # Open the Sheet
        sheet = client.open("Stock_App_DB").sheet1
        
        # Try to fetch existing data
        data = sheet.get_all_records()
        if not data:
            return None
        return data[0] # Return the first row
    except Exception as e:
        # If the sheet is empty, that's okay (new user)
        # We don't want to show an error for empty sheets
        return None

def save_db(balance, watchlist, portfolio):
    """Saves data to the database"""
    try:
        client = get_client()
        if not client: return
        
        sheet = client.open("Stock_App_DB").sheet1
        
        # Prepare data row
        row = [balance, json.dumps(watchlist), json.dumps(portfolio)]
        
        # Clear and update
        sheet.clear()
        sheet.append_row(["Balance", "Watchlist", "Portfolio"]) # Header
        sheet.append_row(row) # Data
    except Exception as e:
        st.error(f"Save Failed: {e}")

# --- 2. INITIALIZE SESSION STATE ---
if "db_loaded" not in st.session_state:
    db_data = init_db()
    
    if db_data:
        # Load from Cloud
        st.session_state["balance"] = float(db_data["Balance"])
        st.session_state["watchlist"] = json.loads(db_data["Watchlist"])
        st.session_state["portfolio"] = json.loads(db_data["Portfolio"])
        st.toast("☁️ Data Loaded from Cloud!")
    else:
        # New User Default
        st.session_state["balance"] = 1000000.0
        st.session_state["watchlist"] = ["RELIANCE.NS", "TCS.NS"]
        st.session_state["portfolio"] = {}
        # Save default to create the row immediately
        save_db(1000000.0, ["RELIANCE.NS", "TCS.NS"], {})
    
    st.session_state["db_loaded"] = True

if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if "selected_ticker" not in st.session_state:
    st.session_state["selected_ticker"] = "RELIANCE.NS"

# --- 3. HELPER FUNCTIONS ---
def save_state():
    save_db(st.session_state["balance"], st.session_state["watchlist"], st.session_state["portfolio"])

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
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_google_news(ticker):
    clean_name = ticker.replace(".NS", "").replace(".BO", "")
    rss_url = f"https://news.google.com/rss/search?q={clean_name}+stock+news+india&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries[:3]

def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "Market Cap": info.get("marketCap", "N/A"),
            "P/E Ratio": info.get("trailingPE", "N/A"),
            "52W High": info.get("fiftyTwoWeekHigh", "N/A"),
            "Sector": info.get("sector", "Unknown"),
            "Business Summary": info.get("longBusinessSummary", "No summary available.")[:300] + "..."
        }
    except:
        return None

# --- 4. SCANNER ENGINE ---
@st.cache_data(ttl=600)
def scan_market():
    TOP_STOCKS = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LICI.NS", "LT.NS", "AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS",
        "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS",
        "TATAMOTORS.NS", "ADANIENT.NS", "WIPRO.NS", "NTPC.NS", "POWERGRID.NS",
        "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS", "ZOMATO.NS"
    ]
    data = yf.download(TOP_STOCKS, period="3mo", progress=False)
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
    st.title("⚡ Pro Stock AI: Cloud Edition ☁️")

    # --- SIDEBAR: PORTFOLIO & WATCHLIST ---
    st.sidebar.divider()
    
    # PORTFOLIO
    st.sidebar.header("💼 My Portfolio")
    st.sidebar.metric("Virtual Balance", f"₹{st.session_state['balance']:,.0f}")
    if st.session_state["portfolio"]:
        st.sidebar.success(f"Holdings: {len(st.session_state['portfolio'])} Stocks")
    else:
        st.sidebar.info("No active trades.")
        
    st.sidebar.divider()
    
    # WATCHLIST
    st.sidebar.header("⭐ Watchlist")
    if st.session_state["watchlist"]:
        wl_data = yf.download(st.session_state["watchlist"], period="5d", progress=False)['Close']
        if isinstance(wl_data, pd.Series): wl_data = wl_data.to_frame(name=st.session_state["watchlist"][0])

        for stock in st.session_state["watchlist"]:
            try:
                if stock in wl_data.columns:
                    price = wl_data[stock].iloc[-1]
                    c1, c2, c3 = st.sidebar.columns([3, 2, 1])
                    c1.markdown(f"**{stock}**\n₹{price:,.1f}")
                    if c2.button("📊", key=f"view_{stock}"):
                        st.session_state["selected_ticker"] = stock
                        st.rerun()
                    if c3.button("❌", key=f"del_{stock}"):
                        st.session_state["watchlist"].remove(stock)
                        save_state() # SAVE TO DB
                        st.rerun()
                    st.sidebar.divider()
            except Exception: pass
    else:
        st.sidebar.info("Empty Watchlist")

    # --- SECTION A: AUTO SCANNER ---
    with st.expander("📊 OPEN MARKET SCANNER (Top 30 Stocks)", expanded=False):
        buys, sells = scan_market()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🟢 Suggested BUYS")
            if not buys.empty: st.dataframe(buys, hide_index=True, use_container_width=True)
            else: st.info("No Buy signals.")
        with c2:
            st.subheader("🔴 Suggested SELLS")
            if not sells.empty: st.dataframe(sells, hide_index=True, use_container_width=True)
            else: st.success("No Sell signals.")

    # --- SECTION B: RESEARCH & ANALYSIS ---
    st.divider()
    
    # Search Bar
    col_search, col_time = st.columns([3, 1])
    with col_search:
        user_input = st.text_input("🔍 Search Stock (e.g., TATASTEEL.NS)", st.session_state["selected_ticker"])
        if user_input != st.session_state["selected_ticker"]:
            st.session_state["selected_ticker"] = user_input.upper().strip()
    
    with col_time:
        interval_map = {"1 Day": "1d", "1 Week": "1wk", "15 Mins": "15m"}
        time_sel = st.selectbox("Timeframe", list(interval_map.keys()))

    current_stock = st.session_state["selected_ticker"]
    
    # Add to Watchlist Button
    if st.button("⭐ Add Current Stock to Watchlist"):
        if current_stock not in st.session_state["watchlist"]:
            st.session_state["watchlist"].append(current_stock)
            save_state() # SAVE TO DB
            st.success(f"Added {current_stock}!")
            st.rerun()

    # --- MAIN TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Chart & Techs", "🏢 Fundamentals", "💼 Paper Trading", "🆚 Compare"])

    # --- TAB 1: CHART ---
    with tab1:
        try:
            period = "5d" if interval_map[time_sel] == "15m" else "1y"
            stock = yf.Ticker(current_stock)
            df = stock.history(period=period, interval=interval_map[time_sel])
            
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['RSI'] = calculate_rsi_series(df['Close'])
                df['Support'] = df['Low'].rolling(window=20).min()
                df['Resistance'] = df['High'].rolling(window=20).max()

                show_sr = st.checkbox("Show Auto-Support & Resistance Lines", value=True)
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
                
                if interval_map[time_sel] == "1d":
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange'), name="50 SMA"))
                else:
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='purple'), name="20 EMA"))
                
                if show_sr:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Support'], line=dict(color='green', dash='dot'), name="Support"))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Resistance'], line=dict(color='red', dash='dot'), name="Resistance"))

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, title=f"{current_stock} Analysis")
                st.plotly_chart(fig, use_container_width=True)

                csv = df.to_csv().encode('utf-8')
                st.download_button("📥 Download Data as CSV", csv, f"{current_stock}_data.csv", "text/csv")
            else:
                st.error("Stock not found.")
        except Exception as e:
            st.error(f"Chart Error: {e}")

    # --- TAB 2: FUNDAMENTALS ---
    with tab2:
        fund_data = get_fundamentals(current_stock)
        if fund_data:
            c1, c2, c3, c4 = st.columns(4)
            mcap = fund_data["Market Cap"]
            mcap_fmt = f"₹{mcap/10000000:,.0f} Cr" if isinstance(mcap, (int, float)) else "N/A"
            c1.metric("Market Cap", mcap_fmt)
            c2.metric("P/E Ratio", f"{fund_data['P/E Ratio']}")
            c3.metric("52W High", f"₹{fund_data['52W High']}")
            c4.metric("Sector", f"{fund_data['Sector']}")
            st.write("### Business Summary")
            st.write(fund_data["Business Summary"])
            st.write("### 📰 Latest News")
            news = get_google_news(current_stock)
            for n in news:
                st.write(f"**[{n.title}]({n.link})**")
        else:
            st.warning("Fundamental data not available.")

    # --- TAB 3: TRADING (SAVES TO DB) ---
    with tab3:
        st.subheader(f"💼 Paper Trading: {current_stock}")
        st.write(f"**Available Cash:** ₹{st.session_state['balance']:,.2f}")
        
        try:
            live_price = yf.Ticker(current_stock).history(period="1d")['Close'].iloc[-1]
            st.metric("Current Market Price", f"₹{live_price:,.2f}")
            col_buy, col_sell = st.columns(2)
            
            with col_buy:
                buy_qty = st.number_input("Buy Quantity", min_value=1, value=10, key="b_qty")
                cost = buy_qty * live_price
                if st.button(f"🟢 BUY {buy_qty} Qty"):
                    if st.session_state['balance'] >= cost:
                        st.session_state['balance'] -= cost
                        if current_stock in st.session_state['portfolio']:
                            old_qty = st.session_state['portfolio'][current_stock]['qty']
                            old_avg = st.session_state['portfolio'][current_stock]['avg_price']
                            new_avg = ((old_qty * old_avg) + cost) / (old_qty + buy_qty)
                            st.session_state['portfolio'][current_stock] = {'qty': old_qty + buy_qty, 'avg_price': new_avg}
                        else:
                            st.session_state['portfolio'][current_stock] = {'qty': buy_qty, 'avg_price': live_price}
                        
                        save_state() # SAVE TO DB
                        st.success(f"Bought {buy_qty} shares!")
                        st.rerun()
                    else:
                        st.error("Insufficient Funds!")

            with col_sell:
                sell_qty = st.number_input("Sell Quantity", min_value=1, value=10, key="s_qty")
                if st.button(f"🔴 SELL {sell_qty} Qty"):
                    if current_stock in st.session_state['portfolio'] and st.session_state['portfolio'][current_stock]['qty'] >= sell_qty:
                        revenue = sell_qty * live_price
                        st.session_state['balance'] += revenue
                        remaining = st.session_state['portfolio'][current_stock]['qty'] - sell_qty
                        if remaining == 0:
                            del st.session_state['portfolio'][current_stock]
                        else:
                            st.session_state['portfolio'][current_stock]['qty'] = remaining
                        
                        save_state() # SAVE TO DB
                        st.success(f"Sold {sell_qty} shares!")
                        st.rerun()
                    else:
                        st.error("Not enough shares.")

            st.divider()
            st.subheader("Your Holdings")
            if st.session_state['portfolio']:
                p_data = []
                total_val = 0
                for t, data in st.session_state['portfolio'].items():
                    curr = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]
                    val = data['qty'] * curr
                    p_loss = (curr - data['avg_price']) * data['qty']
                    total_val += val
                    p_data.append({
                        "Stock": t, "Qty": data['qty'], "Avg Buy": f"₹{data['avg_price']:.1f}",
                        "Current": f"₹{curr:.1f}", "Current Value": f"₹{val:.1f}", "P/L": f"₹{p_loss:.1f}"
                    })
                st.dataframe(pd.DataFrame(p_data))
                st.metric("Total Portfolio Value", f"₹{total_val:,.2f}")

        except Exception as e:
            st.error("Could not fetch live price.")

    # --- TAB 4: COMPARE ---
    with tab4:
        st.subheader("🆚 Stock Comparison Tool")
        TOP_STOCKS = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LICI.NS", "LT.NS", "AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS",
        "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS",
        "TATAMOTORS.NS", "ADANIENT.NS", "WIPRO.NS", "NTPC.NS", "POWERGRID.NS",
        "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS", "ZOMATO.NS"
        ]
        compare_stock = st.selectbox("Compare With:", TOP_STOCKS)
        if st.button("Compare Performance"):
            try:
                c_data = yf.download([current_stock, compare_stock], period="1y", progress=False)['Close']
                c_data = c_data / c_data.iloc[0] * 100
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(x=c_data.index, y=c_data[current_stock], name=current_stock))
                fig_comp.add_trace(go.Scatter(x=c_data.index, y=c_data[compare_stock], name=compare_stock))
                st.plotly_chart(fig_comp, use_container_width=True)
            except Exception as e:
                st.error(f"Comparison Error: {e}")