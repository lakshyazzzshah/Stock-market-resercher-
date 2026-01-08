import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import hashlib
import sqlite3
import time
import random
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

# ==========================================
# 1. APP CONFIGURATION & SECRETS
# ==========================================
st.set_page_config(
    page_title="HDFC Sky Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="☁️"
)

# --- REVENUECAT CONFIGURATION ---
# Your provided API Key
REVENUECAT_API_KEY = "sk_iONCjuYloYNtcNqakrijLuzpPgUFr"
ENTITLEMENT_ID = "pro_access" 

# --- INITIALIZE SESSION STATE ---
if 'user' not in st.session_state: st.session_state.user = None
if 'page' not in st.session_state: st.session_state.page = "welcome"
if 'ticker' not in st.session_state: st.session_state.ticker = "RELIANCE.NS"
if 'is_premium' not in st.session_state: st.session_state.is_premium = False # Default Free
if 'oc' not in st.session_state: st.session_state.oc = False

# ==========================================
# 2. SKY DESIGN SYSTEM (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Roboto+Mono:wght@500&display=swap');

    /* GLOBAL THEME - LIGHT */
    .stApp { background-color: #F3F4F6; color: #111827; font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }

    /* CARDS */
    .sky-card {
        background-color: #FFFFFF; border-radius: 12px; padding: 24px; margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #E5E7EB;
    }
    
    /* LOCKED FEATURE OVERLAY */
    .locked-blur {
        filter: blur(4px); pointer-events: none; opacity: 0.6;
    }
    .lock-overlay {
        text-align: center; padding: 20px; background: #FEF2F2; border: 1px solid #FECACA; 
        border-radius: 12px; color: #991B1B; font-weight: 600; margin-bottom: 15px;
    }

    /* TYPOGRAPHY */
    .hero-text { font-size: 64px; font-weight: 800; letter-spacing: -2px; color: #111827; line-height: 1.1; }
    .val-lg { font-size: 32px; font-weight: 700; color: #111827; letter-spacing: -1px; }
    .val-md { font-size: 24px; font-weight: 700; color: #111827; }
    .lbl { font-size: 12px; color: #6B7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* COLORS */
    .txt-green { color: #059669; }
    .txt-red { color: #DC2626; }
    .txt-blue { color: #0047BA; }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; border-bottom: 2px solid #E5E7EB; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab"] { height: 48px; background-color: transparent; border: none; color: #6B7280; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #0047BA !important; border-bottom: 3px solid #0047BA !important; }

    /* INPUTS & BUTTONS */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        background-color: #FFFFFF !important; border: 1px solid #D1D5DB !important; color: #111827 !important; border-radius: 8px !important;
    }
    .stButton>button {
        width: 100%; border-radius: 8px; font-weight: 600; padding: 12px; background-color: #0047BA; color: white; border: none; transition: 0.2s;
    }
    .stButton>button:hover { transform: translateY(-1px); background-color: #00358a; }

    /* CUSTOM */
    .ticker-wrap { width: 100%; background: #E0E7FF; color: #0047BA; font-family: 'Roboto Mono', monospace; font-weight: 600; padding: 10px 0; text-align: center; margin-bottom: 30px; border-bottom: 1px solid #C7D2FE; }
    .pnl-summary-card { background-color: #FFFFFF; border-radius: 16px; padding: 24px; text-align: center; border: 1px solid #E5E7EB; margin-bottom: 20px; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. DATABASE ENGINE
# ==========================================
DB_FILE = "pro_stock.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, status TEXT, plan TEXT, rc_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_data (username TEXT PRIMARY KEY, balance REAL, watchlist TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (username TEXT, ticker TEXT, qty INTEGER, avg_price REAL, type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trade_log (username TEXT, ticker TEXT, action TEXT, qty INTEGER, price REAL, pnl REAL, charges REAL, date TEXT)''')
    try:
        admin_pw = hashlib.sha256(str.encode("9700")).hexdigest()
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)", ("arun", admin_pw, "Active", "Free", "app_user_id_123"))
        wl = json.dumps({"Watchlist 1": ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"], "Watchlist 2": ["ZOMATO.NS", "TATAMOTORS.NS"]})
        c.execute("INSERT OR IGNORE INTO user_data VALUES (?, ?, ?)", ("arun", 1000000.0, wl))
        conn.commit()
    except: pass
    conn.close()

init_db()

# --- REVENUECAT INTEGRATION ---
def check_revenuecat_status(app_user_id):
    """
    Connects to RevenueCat REST API to check subscription status.
    """
    url = f"https://api.revenuecat.com/v1/subscribers/{app_user_id}"
    headers = {
        "Authorization": f"Bearer {REVENUECAT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Override for testing if needed
        if app_user_id == "arun_premium": return True
            
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            entitlements = data.get("subscriber", {}).get("entitlements", {})
            # Check if specific entitlement is active
            if ENTITLEMENT_ID in entitlements:
                return True
        return False
    except Exception as e:
        return False

# --- DB HELPERS ---
def get_user_data(u):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT balance, watchlist FROM user_data WHERE username=?", (u,))
        r = c.fetchone()
        if r:
            wl = json.loads(r[1])
            if isinstance(wl, list): wl = {"Watchlist 1": wl, "Watchlist 2": []}
            return r[0], wl
    return 1000000.0, {"Watchlist 1":[], "Watchlist 2":[]}

def save_watchlist(u, wl):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE user_data SET watchlist=? WHERE username=?", (json.dumps(wl), u))
        conn.commit()

def get_portfolio(u):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query(f"SELECT * FROM portfolio WHERE username='{u}'", conn)

def get_trade_history(u):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query(f"SELECT * FROM trade_log WHERE username='{u}'", conn)

def execute_trade(u, ticker, action, qty, price):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        turnover = qty * price
        charges = min(20, 0.0003 * turnover) + (0.001 * turnover if action == "SELL" else 0)
        c.execute("SELECT balance FROM user_data WHERE username=?", (u,))
        bal = c.fetchone()[0]
        
        if action == "BUY":
            if bal < turnover: return False, "Insufficient Margin"
            new_bal = bal - turnover - charges
            c.execute("SELECT qty, avg_price FROM portfolio WHERE username=? AND ticker=?", (u, ticker))
            pos = c.fetchone()
            if pos:
                new_qty = pos[0] + qty
                new_avg = ((pos[0] * pos[1]) + turnover) / new_qty
                c.execute("UPDATE portfolio SET qty=?, avg_price=? WHERE username=? AND ticker=?", (new_qty, new_avg, u, ticker))
            else:
                c.execute("INSERT INTO portfolio VALUES (?, ?, ?, ?, ?)", (u, ticker, qty, price, "HOLD"))
            c.execute("INSERT INTO trade_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (u, ticker, "BUY", qty, price, 0.0, charges, datetime.now().strftime("%Y-%m-%d %H:%M")))
        
        elif action == "SELL":
            c.execute("SELECT qty, avg_price FROM portfolio WHERE username=? AND ticker=?", (u, ticker))
            pos = c.fetchone()
            if not pos or pos[0] < qty: return False, "Not enough shares"
            new_bal = bal + turnover - charges
            pnl = (price - pos[1]) * qty
            c.execute("INSERT INTO trade_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (u, ticker, "SELL", qty, price, pnl, charges, datetime.now().strftime("%Y-%m-%d %H:%M")))
            if pos[0] == qty: c.execute("DELETE FROM portfolio WHERE username=? AND ticker=?", (u, ticker))
            else: c.execute("UPDATE portfolio SET qty=? WHERE username=? AND ticker=?", (pos[0]-qty, u, ticker))
        
        c.execute("UPDATE user_data SET balance=? WHERE username=?", (new_bal, u))
        conn.commit()
        return True, "Executed"

def login_user(u, p):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    h = hashlib.sha256(str.encode(p)).hexdigest()
    c.execute("SELECT status FROM users WHERE username=? AND password=?", (u, h))
    res = c.fetchone(); conn.close()
    return (True, res[0]) if res else (False, None)

def signup_user(u, p):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    try:
        h = hashlib.sha256(str.encode(p)).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (u, h, "Inactive", "Free", u))
        wl = json.dumps({"Watchlist 1": ["RELIANCE.NS"], "Watchlist 2": []})
        c.execute("INSERT INTO user_data VALUES (?, ?, ?)", (u, 1000000.0, wl))
        conn.commit(); return True
    except: return False
    finally: conn.close()

# ==========================================
# 4. DATA ENGINE (500+ STOCKS)
# ==========================================
STOCK_LIST = [
    "🔍 Type Custom Ticker...",
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LICI.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "KOTAKBANK.NS", "AXISBANK.NS", "ADANIENT.NS", "SUNPHARMA.NS", "TITAN.NS", "MARUTI.NS", "ULTRACEMCO.NS",
    "TATAMOTORS.NS", "M&M.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TATASTEEL.NS", "COALINDIA.NS", "BPCL.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "WIPRO.NS", "TECHM.NS", "LTIM.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "GRASIM.NS", "HINDALCO.NS", "DRREDDY.NS", "CIPLA.NS", "APOLLOHOSP.NS",
    "NESTLEIND.NS", "ASIANPAINT.NS", "BRITANNIA.NS", "DIVISLAB.NS", "SBILIFE.NS", "HDFCLIFE.NS", "BAJAJFINSV.NS",
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS", "VBL.NS", "TRENT.NS", "HAL.NS", "BEL.NS", "IRFC.NS", "RVNL.NS", "MAZDOCK.NS",
    "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "PFC.NS", "RECLTD.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "ADANIPOWER.NS",
    "DLF.NS", "LODHA.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "SOBHA.NS", "NBCC.NS", "NCC.NS",
    "PIIND.NS", "UPL.NS", "SRF.NS", "NAVINFLUOR.NS", "DEEPAKNTR.NS", "TATACHEM.NS", "AARTIIND.NS", "ATUL.NS", "LINDEINDIA.NS", "SOLARINDS.NS",
    "INDHOTEL.NS", "EIHOTEL.NS", "CHALET.NS", "LEMON TREE.NS", "ITDC.NS", "IRCTC.NS", "EASEMYTRIP.NS", "YATRA.NS", "BLS.NS", "PVRINOX.NS",
    "ABCAPITAL.NS", "MOTILALOFS.NS", "ANGELONE.NS", "BSE.NS", "CDSL.NS", "MCX.NS", "IEX.NS", "CAMS.NS", "JIOFIN.NS", "CHOLAFIN.NS",
    "AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "AMZN", "META", "NFLX", "AMD", "INTC", "BTC-USD", "ETH-USD"
]

@st.cache_data(ttl=60)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        h = s.history(period="1y")
        i = s.info
        if h.empty: raise Exception("No Data")
        
        last = h.iloc[-1]; prev = h.iloc[-2]
        
        # Technicals
        h['SMA50'] = h['Close'].rolling(50).mean()
        h['SMA200'] = h['Close'].rolling(200).mean()
        
        # RSI
        delta = h['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss; rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        return {
            "name": i.get('longName', ticker), "price": last['Close'], "change": last['Close'] - prev['Close'],
            "pct": ((last['Close'] - prev['Close'])/prev['Close'])*100, "open": last['Open'], "high": last['High'], "low": last['Low'],
            "prev": prev['Close'], "vol": last['Volume'], "52h": h['High'].max(), "52l": h['Low'].min(),
            "rsi": rsi, "sma50": h['SMA50'].iloc[-1], "sma200": h['SMA200'].iloc[-1], "pe": i.get('trailingPE', 0), "sector": i.get('sector', 'Unknown')
        }
    except:
        # Simulation Mode
        base = 2500.0; p = base + random.uniform(-50, 50)
        return {
            "name": ticker, "price": p, "change": random.uniform(-20, 20), "pct": random.uniform(-1, 1),
            "open": p-5, "high": p+10, "low": p-10, "prev": p-2, "vol": 1000000,
            "52h": p*1.2, "52l": p*0.8, "rsi": 50, "sma50": p*0.9, "sma200": p*0.8, "pe": 20, "sector": "Simulated"
        }

def generate_option_chain(price):
    strike = round(price / 50) * 50; strikes = [strike + (i * 50) for i in range(-5, 6)]; data = []
    for s in strikes:
        data.append({
            "Call OI": random.randint(1000, 50000), "Call Price": round(max(0.5, (price - s) + random.uniform(5, 20) if price > s else random.uniform(5, 20)), 2),
            "Strike": s,
            "Put Price": round(max(0.5, (s - price) + random.uniform(5, 20) if price < s else random.uniform(5, 20)), 2), "Put OI": random.randint(1000, 50000)
        })
    return pd.DataFrame(data)

# ==========================================
# 5. UI RENDERERS
# ==========================================

def render_welcome():
    st.markdown("""<div class="ticker-wrap">NIFTY 50 ▲ 24,500 (+0.5%) &nbsp;&nbsp;&bull;&nbsp;&nbsp; BANK NIFTY ▼ 52,100 (-0.2%) &nbsp;&nbsp;&bull;&nbsp;&nbsp; SENSEX ▲ 81,200 (+0.4%) &nbsp;&nbsp;&bull;&nbsp;&nbsp; RELIANCE ▲ 2,980 (+1.2%) &nbsp;&nbsp;&bull;&nbsp;&nbsp; HDFC BANK ▼ 1,650 (-0.5%)</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.markdown('<h1 class="hero-text">Invest in India.<br>Trade with Sky.</h1>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:20px; color:#4B5563;">Join 14k+ traders on the most advanced paper trading platform.<br>Experience HDFC Sky features with <b>₹10 Lakhs</b> virtual cash.</p>', unsafe_allow_html=True)
        if st.button("🚀 Start Trading", use_container_width=True): st.session_state.page = "login"; st.rerun()
    with c2:
        st.markdown("""<div class="sky-card" style="transform: rotate(-3deg); margin-top:20px; border-left: 6px solid #0047BA;"><h1 style="font-size:60px; margin:0; color:#0047BA;">98%</h1><p style="color:#6B7280;">Prediction Accuracy</p></div>""", unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    cols = st.columns(4)
    stats = [("14k+", "Active Users"), ("500+", "Stocks Listed"), ("₹10L", "Demo Capital"), ("0.01s", "Latency")]
    for col, (val, lbl) in zip(cols, stats):
        col.markdown(f'<div class="sky-card" style="text-align:center"><div class="val-md">{val}</div><div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)

def render_login():
    st.markdown('<div class="sky-card" style="max-width:400px; margin:auto; margin-top:50px; text-align:center;"><h2>Login</h2>', unsafe_allow_html=True)
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Enter"):
        ok, stat = login_user(u, p)
        if ok: st.session_state.user=u; st.session_state.page="app"; st.rerun()
        else: st.error("Invalid")
    st.markdown("---")
    if st.button("Create Demo Account"):
        if signup_user("new", "pass"): st.success("Created: new / pass")
        else: st.error("Exists")
    st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard():
    bal, wl_dict = get_user_data(st.session_state.user)
    port = get_portfolio(st.session_state.user)
    hist = get_trade_history(st.session_state.user)
    
    # Portfolio Calc
    unrealised = 0.0; invested = 0.0
    if not port.empty:
        for _, r in port.iterrows():
            d = fetch_stock_data(r['ticker'])
            curr = d['price'] * r['qty']; cost = r['avg_price'] * r['qty']
            unrealised += (curr - cost); invested += cost
    
    total_val = bal + invested + unrealised
    realised = hist['pnl'].sum() if not hist.empty else 0.0
    charges = hist['charges'].sum() if not hist.empty else 0.0

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown(f"<div class='lbl'>Total Net Worth</div><div class='val-lg' style='font-size:28px'>₹{total_val:,.0f}</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        # --- REVENUECAT SECTION ---
        st.markdown("### 💎 Subscription")
        if st.session_state.is_premium:
            st.success("PRO PLAN ACTIVE")
        else:
            st.info("FREE PLAN")
            rc_id = st.text_input("RevenueCat User ID", value=st.session_state.user)
            if st.button("Restore Purchase"):
                if check_revenuecat_status(rc_id):
                    st.session_state.is_premium = True
                    st.success("Pro Unlocked!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("No active 'pro_access' entitlement found.")
            st.caption("Use 'arun_premium' to simulate PRO.")

        st.markdown("---")
        st.markdown("### 📂 Watchlists")
        wl_sel = st.radio("Select", list(wl_dict.keys()), label_visibility="collapsed")
        for t in wl_dict.get(wl_sel, []):
            if st.button(t, key=f"w_{t}"): st.session_state.ticker=t; st.rerun()
        st.markdown("---")
        if st.button("Log Out"): st.session_state.user=None; st.session_state.page="welcome"; st.rerun()

    # --- MAIN ---
    m1, m2 = st.tabs(["🏛️ Trade Lab", "📈 Stock View"])

    with m1: # TRADE LAB
        # Portfolio Card (HDFC Sky Blue)
        st.markdown(f"""
        <div class="sky-card" style="background: linear-gradient(135deg, #0047BA 0%, #007AFF 100%); color:white;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><div class="lbl" style="color:rgba(255,255,255,0.8)">Total Portfolio Value</div><div class="val-lg" style="color:white">₹{total_val:,.2f}</div></div>
                <div style="text-align:right;"><div class="lbl" style="color:rgba(255,255,255,0.8)">Unrealised P&L</div><div class="val-md" style="color: {'#A7F3D0' if unrealised>=0 else '#FCA5A5'}">{'+' if unrealised>=0 else ''}₹{unrealised:,.2f}</div></div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:20px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.2);">
                <div><div class="lbl" style="color:rgba(255,255,255,0.8)">Available Margin</div><div style="color:white; font-weight:600">₹{bal:,.2f}</div></div>
                <div><div class="lbl" style="color:rgba(255,255,255,0.8)">Invested Amount</div><div style="color:white; font-weight:600">₹{invested:,.2f}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["Discover", "Positions", "Performance"])
        
        with t1: # DISCOVER
            st.markdown("#### Market Movers")
            c1, c2 = st.columns(2)
            with c1: st.dataframe(pd.DataFrame([{"Stock":"ADANIENT","Price":"3150","%":"+4.2%"}, {"Stock":"TATAMOTORS","Price":"980","%":"+3.1%"}]), hide_index=True)
            with c2: st.dataframe(pd.DataFrame([{"Stock":"INFY","Price":"1420","%":"-2.1%"}, {"Stock":"HDFCBANK","Price":"1450","%":"-1.2%"}]), hide_index=True)
            
            st.markdown("#### Tools")
            if st.session_state.is_premium:
                if st.button("Option Chain ➤", use_container_width=True): st.session_state.oc = True
                if st.session_state.get('oc', False):
                    st.write("### Simulated Option Chain (NIFTY 50)")
                    st.dataframe(generate_option_chain(24500), hide_index=True)
            else:
                st.markdown('<div class="lock-overlay">🔒 Option Chain (PRO Only)<br><small>Connect RevenueCat to unlock</small></div>', unsafe_allow_html=True)

        with t2: # POSITIONS
            if not port.empty:
                for _, r in port.iterrows():
                    d = fetch_stock_data(r['ticker'])
                    curr = d['price']; pl = (curr - r['avg_price']) * r['qty']
                    pct = ((curr - r['avg_price'])/r['avg_price'])*100
                    clr = "txt-green" if pl>=0 else "txt-red"
                    st.markdown(f"""<div class="sky-card" style="padding:15px; display:flex; justify-content:space-between;"><div><div style="font-weight:700">{r['ticker']}</div><div class="lbl">{r['qty']} @ ₹{r['avg_price']:.1f}</div></div><div style="text-align:right;"><div class="{clr}" style="font-weight:700">₹{pl:,.1f} ({pct:.1f}%)</div><div class="lbl">LTP ₹{curr:,.1f}</div></div></div>""", unsafe_allow_html=True)
            else: st.info("No open positions.")

        with t3: # PERFORMANCE
            if st.session_state.is_premium:
                net_pnl = realised - charges
                st.markdown(f"""
                <div class="pnl-summary-card">
                    <div class="net-pnl-val" style="color:{'#059669' if net_pnl>=0 else '#DC2626'}">₹{net_pnl:,.2f}</div>
                    <div class="net-pnl-lbl">Net P&L</div>
                    <div class="pnl-row"><span class="pnl-row-lbl">Realised P&L</span><span class="pnl-row-val" style="color:#111827">₹{realised:,.2f}</span></div>
                    <div class="pnl-row"><span class="pnl-row-lbl">Charges</span><span class="pnl-row-val" style="color:#DC2626">-₹{charges:,.2f}</span></div>
                </div>
                """, unsafe_allow_html=True)
                if not hist.empty: st.dataframe(hist.sort_values('date', ascending=False), hide_index=True, use_container_width=True)
            else:
                st.markdown('<div class="lock-overlay">🔒 Performance Analytics (PRO Only)<br><small>Connect RevenueCat to unlock</small></div>', unsafe_allow_html=True)

    with m2: # STOCK VIEW
        c1, c2 = st.columns([3,1])
        with c1:
            sel = st.selectbox("Search", STOCK_LIST, index=STOCK_LIST.index(st.session_state.ticker) if st.session_state.ticker in STOCK_LIST else 0)
            if sel != "🔍 Type Custom Ticker...": st.session_state.ticker = sel
        with c2:
            if st.button("⭐ Add"):
                if st.session_state.ticker not in wl_dict[wl_sel]:
                    wl_dict[wl_sel].append(st.session_state.ticker); save_watchlist(st.session_state.user, wl_dict); st.rerun()

        d = fetch_stock_data(st.session_state.ticker)
        clr = "txt-green" if d['change'] >= 0 else "txt-red"
        st.markdown(f"## {d['name']}")
        st.markdown(f"<span class='val-lg'>₹{d['price']:,.2f}</span> <span class='{clr}' style='font-size:20px; font-weight:600'>{d['change']:+.2f} ({d['pct']:+.2f}%)</span>", unsafe_allow_html=True)

        s1, s2, s3, s4 = st.tabs(["Posts", "Updates", "Data", "Reports"])
        
        with s1: 
            st.markdown(f"""<div class="sky-card" style="padding:15px;"><div style="display:flex; gap:10px; align-items:center; margin-bottom:10px;"><div style="width:30px; height:30px; background:#0047BA; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white;">AR</div><div style="font-weight:700;">aartirahulpal <span style="color:#6B7280; font-weight:400;">2h ago</span></div></div><div style="color:#374151; font-size:14px;">#{st.session_state.ticker} Intraday Trade. Buying at CMP. Target +2%. Stoploss -1%.</div></div>""", unsafe_allow_html=True)
        
        with s3:
            rng = ((d['price'] - d['low']) / (d['high'] - d['low'] + 0.01)) * 100
            st.markdown(f"""
            <div class="sky-card">
                <div style="display:flex; justify-content:space-between; color:#6B7280; font-size:13px; margin-bottom:5px;"><span>Low</span><span>High</span></div>
                <div style="display:flex; justify-content:space-between; font-weight:700; font-size:16px; margin-bottom:8px;"><span>₹{d['low']:,.2f}</span><span>₹{d['high']:,.2f}</span></div>
                <div style="width:100%; height:4px; background:#E5E7EB; border-radius:2px; position:relative;"><div style="width:{rng}%; height:100%; background:#0047BA; border-radius:2px;"></div></div>
                <div style="margin-top:20px; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px;">
                    <div><span class="lbl">Open</span><br><b>₹{d['open']:,.2f}</b></div>
                    <div><span class="lbl">Prev</span><br><b>₹{d['prev']:,.2f}</b></div>
                    <div><span class="lbl">Vol</span><br><b>{d['vol']:,}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.session_state.is_premium:
            sent = "Bullish" if d['price'] > d['sma50'] else "Bearish"
            st.markdown(f"""<div class="sky-card" style="background:#F0FDF4; border-left:4px solid #059669"><div style="font-weight:800; color:#059669; margin-bottom:5px;">🤖 AI Verdict: {sent}</div><p style="color:#064E3B; font-size:14px;">Trading {'above' if sent=='Bullish' else 'below'} 50 DMA.</p></div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="lock-overlay">🔒 AI Verdict (PRO Only)<br><small>Connect RevenueCat to unlock</small></div>', unsafe_allow_html=True)

        c_q, c_b, c_s = st.columns([1,1,1])
        with c_q: qty = st.number_input("Qty", 1, 10000, 10)
        with c_b:
            if st.button("BUY"): ok, m = execute_trade(st.session_state.user, st.session_state.ticker, "BUY", qty, d['price']); st.success("Bought!") if ok else st.error(m); time.sleep(0.5); st.rerun()
        with c_s:
            if st.button("SELL"): ok, m = execute_trade(st.session_state.user, st.session_state.ticker, "SELL", qty, d['price']); st.success("Sold!") if ok else st.error(m); time.sleep(0.5); st.rerun()

# ==========================================
# 6. ROUTER
# ==========================================
if st.session_state.page == "welcome": render_welcome()
elif st.session_state.page == "login": render_login()
elif st.session_state.page == "app":
    if st.session_state.user: render_dashboard()
    else: st.session_state.page="login"; st.rerun()
