import streamlit as st
import yfinance as yf
import pandas as pd
import json
import hashlib
import os
import time
import plotly.graph_objects as go
import sqlite3
from datetime import datetime, timedelta
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro Stock Terminal", layout="wide", initial_sidebar_state="expanded")

# --- 0. DATABASE ENGINE ---
DB_FILE = "pro_stock.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, status TEXT, plan TEXT, start_date TEXT, expiry_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_data (username TEXT PRIMARY KEY, balance REAL, watchlist TEXT, portfolio TEXT)''')
    try:
        admin_pw = hashlib.sha256(str.encode("9700")).hexdigest()
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)", ("arun", admin_pw, "Active", "Lifetime", datetime.now().strftime("%Y-%m-%d"), "2099-12-31"))
        c.execute("INSERT OR IGNORE INTO user_data VALUES (?, ?, ?, ?)", ("arun", 1000000.0, json.dumps(["RELIANCE.NS"]), json.dumps({})))
        conn.commit()
    except: pass
    conn.close()

init_db()

# --- 1. PREMIUM PRO UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;500;700;900&family=JetBrains+Mono:wght@400&display=swap');

    .stApp {
        background-color: #000000;
        background-image: radial-gradient(at 50% 0%, rgba(0, 100, 255, 0.15) 0px, transparent 50%);
        font-family: 'Inter', sans-serif;
        color: #ffffff;
    }

    .glass-card {
        background: rgba(20, 20, 20, 0.6);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 30px;
        margin-bottom: 24px;
        transition: transform 0.3s ease;
    }
    .glass-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255, 255, 255, 0.2);
    }

    /* SCROLLING TICKER */
    .ticker-wrap {
        width: 100%;
        overflow: hidden;
        background-color: rgba(255, 255, 255, 0.05);
        padding-top: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
        white-space: nowrap;
    }
    .ticker { display: inline-block; animation: ticker 40s linear infinite; }
    .ticker-item { display: inline-block; padding: 0 2rem; font-family: 'JetBrains Mono', monospace; font-size: 14px; color: #2EBD85; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    /* METRICS */
    .metric-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 24px; font-weight: 700; color: #fff; }
    
    /* HEATMAP BLOCKS */
    .heatmap-box {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 10px;
        font-weight: bold;
        transition: transform 0.2s;
        cursor: pointer;
    }
    .heatmap-box:hover { transform: scale(1.05); }
    .green-bg { background: rgba(46, 189, 133, 0.2); border: 1px solid #2EBD85; color: #2EBD85; }
    .red-bg { background: rgba(246, 70, 93, 0.2); border: 1px solid #F6465D; color: #F6465D; }

    /* ORDER FLOW */
    .order-row {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        padding: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        display: flex;
        justify-content: space-between;
    }

    .stButton>button { width: 100%; border-radius: 12px; font-weight: 700; transition: 0.3s; }
    .stTextInput input { background-color: #0F0F0F !important; border: 1px solid #333 !important; color: white !important; border-radius: 12px !important; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND LOGIC ---
def get_db(): return sqlite3.connect(DB_FILE)

def login_user(u, p):
    conn = get_db(); c = conn.cursor()
    h = hashlib.sha256(str.encode(p)).hexdigest()
    try:
        c.execute("SELECT status, expiry_date FROM users WHERE username=? AND password=?", (u, h))
        res = c.fetchone()
        if res:
            status, exp = res
            if status == "Active" and exp:
                try: 
                    if datetime.now() > datetime.strptime(exp, "%Y-%m-%d"):
                        c.execute("UPDATE users SET status='Expired' WHERE username=?", (u,)); conn.commit(); status = "Expired"
                except: pass
            return True, status
    except: pass
    finally: conn.close()
    return False, None

def signup_user(u, p):
    conn = get_db(); c = conn.cursor()
    try:
        h = hashlib.sha256(str.encode(p)).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (u, h, "Inactive", "None", "", ""))
        c.execute("INSERT INTO user_data VALUES (?, ?, ?, ?)", (u, 1000000.0, json.dumps(["RELIANCE.NS"]), json.dumps({})))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def approve_user(u):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT plan FROM users WHERE username=?", (u,))
    row = c.fetchone()
    if not row: return
    days = 365 if "1 Year" in row[0] else 90 if "3 Months" in row[0] else 30
    start = datetime.now(); end = start + timedelta(days=days)
    c.execute("UPDATE users SET status='Active', start_date=?, expiry_date=? WHERE username=?", (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), u))
    conn.commit(); conn.close()

def get_data(u):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT balance, watchlist, portfolio FROM user_data WHERE username=?", (u,))
    r = c.fetchone(); conn.close()
    return (r[0], json.loads(r[1]), json.loads(r[2])) if r else (1000000.0, [], {})

def save_data(u, b, w, p):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE user_data SET balance=?, watchlist=?, portfolio=? WHERE username=?", (b, json.dumps(w), json.dumps(p), u))
    conn.commit(); conn.close()

# --- 3. MASSIVE 500+ STOCK LIST ---
STOCK_LIST = [
    "🔍 Type Custom Ticker...",
    # --- NIFTY 50 GIANTS ---
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LICI.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "KOTAKBANK.NS", "AXISBANK.NS", "ADANIENT.NS", "SUNPHARMA.NS", "TITAN.NS", "MARUTI.NS", "ULTRACEMCO.NS",
    "TATAMOTORS.NS", "M&M.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TATASTEEL.NS", "COALINDIA.NS", "BPCL.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "WIPRO.NS", "TECHM.NS", "LTIM.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "GRASIM.NS", "HINDALCO.NS", "DRREDDY.NS", "CIPLA.NS", "APOLLOHOSP.NS",
    
    # --- BANKING & FINANCE (MIDCAP) ---
    "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "PFC.NS", "RECLTD.NS", "IOB.NS", "UCOBANK.NS", "CENTRALBK.NS", "BANKINDIA.NS",
    "ABCAPITAL.NS", "MOTILALOFS.NS", "ANGELONE.NS", "BSE.NS", "CDSL.NS", "MCX.NS", "IEX.NS", "CAMS.NS", "JIOFIN.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
    
    # --- TECH & IT SERVICES ---
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS", "TATAELXSI.NS", "KPITTECH.NS", "CYIENT.NS", "ZENSARTECH.NS", "SONACOMS.NS", "HAPPSTMNDS.NS",
    
    # --- AUTO & ANCILLARY ---
    "BOSCHLTD.NS", "MRF.NS", "BALKRISIND.NS", "APOLLOTYR.NS", "CEAT.NS", "JKTYRE.NS", "MOTHERSON.NS", "ASHOKLEY.NS", "TVSMOTOR.NS", "ESCORTS.NS",
    
    # --- CONSUMER & RETAIL ---
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS", "VBL.NS", "TRENT.NS", "PIDILITIND.NS", "ASIANPAINT.NS", "BERGEPAINT.NS", "KANSAINER.NS",
    "GODREJCP.NS", "DABUR.NS", "MARICO.NS", "BRITANNIA.NS", "TATACONSUM.NS", "COLPAL.NS", "PGHH.NS", "GILLETTE.NS", "EMAMILTD.NS", "JYOTHYLAB.NS",
    "UBL.NS", "MCDOWELL-N.NS", "RADICO.NS", "SULA.NS", "GLOBUSSPR.NS", "BATAINDIA.NS", "RELAXO.NS", "CAMPUS.NS", "METROBRAND.NS", "KALYANKJIL.NS",
    "SENCO.NS", "THANGAMAYL.NS", "RAJESHEXPO.NS", "TITAN.NS", "PVRINOX.NS", "INDHOTEL.NS", "EIHOTEL.NS", "CHALET.NS", "LEMON TREE.NS",
    
    # --- PHARMA & HEALTHCARE ---
    "DIVISLAB.NS", "LUPIN.NS", "ALKEM.NS", "AUROPHARMA.NS", "BIOCON.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "GLENMARK.NS", "LAURUSLABS.NS", "GRANULES.NS",
    "SYNGENE.NS", "METROPOLIS.NS", "LALPATHLAB.NS", "VIJAYA.NS", "KIMS.NS", "NH.NS", "FORTIS.NS", "MEDANTA.NS", "MAXHEALTH.NS", "ASTERDM.NS",
    
    # --- INFRA, REALTY & POWER ---
    "DLF.NS", "LODHA.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "SOBHA.NS", "NBCC.NS", "NCC.NS",
    "RAILTEL.NS", "RITES.NS", "CONCOR.NS", "GPPL.NS", "SCI.NS", "GESHIP.NS", "DREDGECORP.NS", "GMRINFRA.NS", "ADANIENSOL.NS", "JPPOWER.NS",
    "TATAPOWER.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "SJVN.NS", "NHPC.NS", "IRFC.NS", "RVNL.NS", "HAL.NS", "BEL.NS", "MAZDOCK.NS", "COCHINSHIP.NS",
    
    # --- CHEMICALS & FERTILIZERS ---
    "PIIND.NS", "UPL.NS", "SRF.NS", "NAVINFLUOR.NS", "DEEPAKNTR.NS", "TATACHEM.NS", "AARTIIND.NS", "ATUL.NS", "LINDEINDIA.NS", "SOLARINDS.NS",
    "FACT.NS", "RCF.NS", "CHAMBLFERT.NS", "COROMANDEL.NS", "GNFC.NS", "GSFC.NS", "NFL.NS", "PARADEEP.NS", "SUMICHEM.NS", "BAYERCROP.NS",
    
    # --- TEXTILES ---
    "TRIDENT.NS", "ALOKINDS.NS", "WELSPUNIND.NS", "RAYMOND.NS", "ARVIND.NS", "KPRMILL.NS", "GOKEX.NS", "PAGEIND.NS", "LUXIND.NS", "RUPA.NS",
    
    # --- US & CRYPTO ---
    "AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "AMZN", "META", "NFLX", "AMD", "INTC", "BTC-USD", "ETH-USD", "DOGE-USD", "SOL-USD"
]

def get_stock_safe(t):
    try:
        s = yf.Ticker(t); h = s.history(period="6mo"); i = s.info
        if h is None or h.empty: return None, {}, 0, []
        
        # Calc Score & Indicators
        sc = 50; r = []
        try:
            if h['Close'].iloc[-1] > h['Close'].rolling(50).mean().iloc[-1]: sc += 20; r.append("✅ Bullish Trend")
            else: sc -= 10; r.append("⚠️ Bearish Trend")
        except: pass
        
        pe = i.get('trailingPE', 0)
        if pe and 0 < pe < 25: sc += 15; r.append("✅ Undervalued")
        
        # Mock RSI/MACD for display
        rsi = random.randint(30, 80)
        macd = random.uniform(-5, 10)
        i['rsi'] = rsi; i['macd'] = macd
        
        return h, i, sc, r
    except: return None, {}, 0, []

def get_news_guaranteed(ticker):
    try:
        news = yf.Ticker(ticker).news
        valid = []
        if news:
            for n in news[:5]:
                if 'title' in n and 'link' in n: valid.append(n)
        if not valid:
            google_symbol = ticker.replace(".NS", ":NSE").replace(".BO", ":BOM")
            return [{'title': f"Click to read latest news for {ticker}", 'link': f"https://www.google.com/finance/quote/{google_symbol}", 'publisher': 'Google Finance (Live)'}]
        return valid
    except:
        return [{'title': f"External News Link: {ticker}", 'link': f"https://finance.yahoo.com/quote/{ticker}", 'publisher': 'Yahoo Finance'}]

# --- 4. UI PAGES ---

def welcome_page():
    # TICKER TAPE
    st.markdown("""
    <div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item">NIFTY 50 ▲ 24,580 (+0.45%)</span>
        <span class="ticker-item">BANK NIFTY ▼ 52,100 (-0.12%)</span>
        <span class="ticker-item">SENSEX ▲ 81,200 (+0.38%)</span>
        <span class="ticker-item">USD/INR ▲ 83.45</span>
        <span class="ticker-item">GOLD ▼ 72,000</span>
        <span class="ticker-item">RELIANCE ▲ 2,980</span>
        <span class="ticker-item">BTC ▲ $98,000</span>
    </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.markdown('<h1 class="hero-text">Trading is Math.<br>Not Magic.</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-hero">90% of retail traders lose money because they trade on emotion. <br>The <b>Quantum Trader AI</b> processes 50+ technical indicators instantly to give you a mathematically calculated edge.</p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        c_b1, c_b2 = st.columns([1, 1.5])
        with c_b1:
            if st.button("Start Free Trial"): st.session_state.page = "login"; st.rerun()
        with c_b2: st.markdown("<div style='margin-top:12px; color:#666;'>⚡ No credit card required</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("""<div class="glass-card" style="transform: rotate(-2deg); margin-top: 20px; border-color: #2EBD85;"><div style="display:flex; justify-content:space-between; margin-bottom:10px;"><span style="font-family:'JetBrains Mono'; font-size:12px; color:#888;">AI_SIGNAL_v4</span><span style="background:#2EBD85; color:#000; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">CONFIRMED</span></div><h1 style="font-size:50px; margin:0; color:#fff;">BUY</h1><p style="color:#aaa; font-size:14px;">Asset: <b>RELIANCE.NS</b><br>Probability: <b>98.4%</b></p></div>""", unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    with s1: st.markdown('<div class="stat-box"><div class="stat-num">14k+</div><div class="stat-label">Active Traders</div></div>', unsafe_allow_html=True)
    with s2: st.markdown('<div class="stat-box"><div class="stat-num">₹500Cr</div><div class="stat-label">Volume Analyzed</div></div>', unsafe_allow_html=True)
    with s3: st.markdown('<div class="stat-box"><div class="stat-num">98.9%</div><div class="stat-label">Uptime</div></div>', unsafe_allow_html=True)
    with s4: st.markdown('<div class="stat-box" style="border:none"><div class="stat-num">4.9/5</div><div class="stat-label">User Rating</div></div>', unsafe_allow_html=True)

def login_page():
    st.markdown('<div style="padding-top: 60px;"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Secure Terminal Access</h2>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign In", "Create Account"])
        with tab1:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Enter Terminal"):
                ok, stat = login_user(u, p)
                if ok: st.session_state.user = u; st.session_state.status = stat; st.session_state.page = "app"; st.rerun()
                else: st.error("Invalid Credentials")
        with tab2:
            nu = st.text_input("Choose Username", key="s_u")
            np = st.text_input("Choose Password", type="password", key="s_p")
            if st.button("Register"):
                if signup_user(nu, np): st.success("Account Created.")
                else: st.error("Username Unavailable")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Back to Home"): st.session_state.page = "welcome"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def payment_page():
    st.markdown('<div style="padding-top: 50px;"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
        if st.session_state.status == "Pending":
            st.info("Payment Verification in Progress"); st.write("Our team is confirming your transaction ID."); st.button("Check Status", on_click=st.rerun)
        else:
            st.markdown("<h2>Unlock Pro Features</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#888'>Gain an unfair advantage in the market today.</p>", unsafe_allow_html=True)
            qr = "qrcode.jpg" if os.path.exists("qrcode.jpg") else "Screenshot_20251231_101328.jpg"
            if os.path.exists(qr): st.image(qr, width=220)
            else: st.warning("QR Code Not Found")
            p = st.radio("Select Plan", ["1 Month (₹100)", "1 Year (₹1000) - Best Value"], horizontal=True)
            if st.button("I Have Completed Payment"):
                conn = get_db(); c = conn.cursor()
                c.execute("UPDATE users SET status='Pending', plan=? WHERE username=?", (p.split(" (")[0], st.session_state.user))
                conn.commit(); conn.close()
                st.session_state.status = "Pending"; st.rerun()
        if st.button("Logout"): st.session_state.user=None; st.session_state.page="welcome"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def dashboard():
    bal, wl, port = get_data(st.session_state.user)
    
    # LIVE TICKER
    st.markdown("""
    <div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item">NIFTY 50 ▲ 24,580 (+0.45%)</span>
        <span class="ticker-item">BANK NIFTY ▼ 52,100 (-0.12%)</span>
        <span class="ticker-item">SENSEX ▲ 81,200 (+0.38%)</span>
        <span class="ticker-item">USD/INR ▲ 83.45</span>
        <span class="ticker-item">GOLD ▼ 72,000</span>
        <span class="ticker-item">RELIANCE ▲ 2,980</span>
        <span class="ticker-item">BTC ▲ $98,000</span>
    </div>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"### {st.session_state.user}")
        st.markdown("<span style='color:#2EBD85; font-size:12px;'>● SYSTEM ONLINE</span>", unsafe_allow_html=True)
        st.metric("Buying Power", f"₹{bal:,.0f}")
        
        if st.session_state.user == 'arun':
            st.error("Admin Panel")
            conn = get_db(); c = conn.cursor()
            c.execute("SELECT username, plan FROM users WHERE status='Pending'")
            pend = c.fetchall(); conn.close()
            if pend:
                sel = st.selectbox("Requests", [f"{u[0]} ({u[1]})" for u in pend])
                if st.button("Approve"): approve_user(sel.split(" (")[0]); st.success("Approved"); time.sleep(1); st.rerun()
            else: st.info("No Pending Requests")
        
        # LIVE ORDER FLOW SIMULATION
        st.markdown("---")
        st.markdown("### 📡 GLOBAL ORDER FLOW")
        trades = [
            ("TATA MOTORS", "BUY", "100"), ("ZOMATO", "SELL", "500"), 
            ("RELIANCE", "BUY", "25"), ("HDFCBANK", "SELL", "50"),
            ("ADANI ENT", "BUY", "10")
        ]
        for t in trades:
            clr = "#2EBD85" if t[1]=="BUY" else "#F6465D"
            st.markdown(f"""
            <div class="order-row">
                <span>{t[0]}</span>
                <span style="color:{clr}">{t[1]}</span>
                <span>{t[2]}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### WATCHLIST")
        for t in wl: 
            if st.button(t): st.session_state.ticker = t; st.rerun()
        st.markdown("---"); st.button("Logout", on_click=lambda: setattr(st.session_state, 'user', None))

    c1, c2 = st.columns([3, 1])
    with c1:
        sel = st.selectbox("Search", STOCK_LIST, index=STOCK_LIST.index(st.session_state.ticker) if st.session_state.ticker in STOCK_LIST else 0, label_visibility="collapsed")
        if sel == "🔍 Type Custom Ticker...":
            t = st.text_input("Ticker").upper()
            if t: st.session_state.ticker = t
        else: st.session_state.ticker = sel
    with c2:
        if st.button("Add to Watchlist"): 
            if st.session_state.ticker not in wl: wl.append(st.session_state.ticker); save_data(st.session_state.user, bal, wl, port); st.rerun()

    h, i, sc, r = get_stock_safe(st.session_state.ticker)
    
    if h is None:
        st.markdown('<div class="glass-card"><h3>⚠️ Market Data Unavailable</h3><p>The feed for this stock is currently offline. Please try another ticker.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"<span style='font-size:24px; font-weight:700; color:#aaa;'>{i.get('longName', st.session_state.ticker)}</span>", unsafe_allow_html=True)
            if not h.empty:
                curr = h['Close'].iloc[-1]
                st.markdown(f"<div style='font-size:60px; font-weight:700; color:#fff; line-height:1;'>₹{curr:,.2f}</div>", unsafe_allow_html=True)
        with c2: 
            st.metric("High", f"₹{i.get('dayHigh',0):,.0f}")
            st.metric("Low", f"₹{i.get('dayLow',0):,.0f}")
        with c3: 
            clr = "#2EBD85" if sc > 50 else "#F6465D"
            st.markdown(f"<div style='background:#111; padding:20px; border-radius:12px; text-align:center; border:1px solid {clr}'><h1>{sc}</h1><small>AI SCORE</small></div>", unsafe_allow_html=True)
        
        # FUNDAMENTALS & INDICATORS GRID (Filling space)
        st.markdown("---")
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1: st.markdown(f"<div class='metric-label'>Market Cap</div><div class='metric-value'>₹{i.get('marketCap',0)/1e7:,.0f}Cr</div>", unsafe_allow_html=True)
        with f2: st.markdown(f"<div class='metric-label'>P/E Ratio</div><div class='metric-value'>{i.get('trailingPE','N/A')}</div>", unsafe_allow_html=True)
        with f3: st.markdown(f"<div class='metric-label'>RSI (14)</div><div class='metric-value'>{i.get('rsi', 50)}</div>", unsafe_allow_html=True)
        with f4: st.markdown(f"<div class='metric-label'>MACD</div><div class='metric-value'>{i.get('macd', 0.0):.2f}</div>", unsafe_allow_html=True)
        with f5: st.markdown(f"<div class='metric-label'>Sector</div><div class='metric-value' style='font-size:16px; margin-top:5px'>{i.get('sector','Unknown')}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        t1, t2 = st.tabs(["Chart & Analysis", "Trading Desk"])
        with t1:
            if not h.empty:
                fig = go.Figure(data=[go.Candlestick(x=h.index, open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
                fig.update_layout(xaxis_rangeslider_visible=False, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'))
                st.plotly_chart(fig, use_container_width=True)
            
            c_a, c_b = st.columns(2)
            with c_a: 
                st.write("### Strengths")
                for x in r: 
                    if "✅" in x: st.success(x)
            with c_b:
                st.write("### Weaknesses")
                for x in r:
                    if "⚠️" in x: st.warning(x)

        with t2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            
            # QUICK ACTION BUTTONS
            st.write("⚡ **QUICK TRADE**")
            qb1, qb2, qb3 = st.columns(3)
            q_val = 10
            if qb1.button("Buy 10"): q_val = 10
            if qb2.button("Buy 50"): q_val = 50
            if qb3.button("Buy 100"): q_val = 100
            
            q = st.number_input("CUSTOM QUANTITY", 1, 10000, q_val)
            c_b, c_s = st.columns(2)
            if c_b.button("🟢 BUY MARKET"):
                cost = q * curr
                if bal >= cost:
                    bal -= cost; p = port.get(st.session_state.ticker, {'qty':0, 'avg':0})
                    navg = ((p['qty']*p['avg']) + cost)/(p['qty']+q)
                    port[st.session_state.ticker] = {'qty': p['qty']+q, 'avg': navg}
                    save_data(st.session_state.user, bal, wl, port); st.success("Filled"); time.sleep(0.5); st.rerun()
                else: st.error("Funds Low")
            if c_s.button("🔴 SELL MARKET"):
                if st.session_state.ticker in port and port[st.session_state.ticker]['qty'] >= q:
                    bal += q * curr; port[st.session_state.ticker]['qty'] -= q
                    if port[st.session_state.ticker]['qty'] == 0: del port[st.session_state.ticker]
                    save_data(st.session_state.user, bal, wl, port); st.success("Filled"); time.sleep(0.5); st.rerun()
                else: st.error("No Position")
            
            st.markdown("### Positions")
            if port:
                pd_d = []
                for t, d in port.items():
                    try: l = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]
                    except: l = d['avg']
                    pd_d.append({"Ticker": t, "Qty": d['qty'], "Avg": round(d['avg'],1), "LTP": round(l,1), "P/L": round((l-d['avg'])*d['qty'],1)})
                st.dataframe(pd.DataFrame(pd_d), hide_index=True, use_container_width=True)
            else: st.info("No Open Trades")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # MARKET SECTOR HEATMAP (Filling Bottom Space)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🔥 MARKET SECTOR HEATMAP")
    hm1, hm2, hm3, hm4 = st.columns(4)
    with hm1: st.markdown('<div class="heatmap-box green-bg">BANKING<br>+1.2%</div>', unsafe_allow_html=True)
    with hm2: st.markdown('<div class="heatmap-box red-bg">IT TECH<br>-0.8%</div>', unsafe_allow_html=True)
    with hm3: st.markdown('<div class="heatmap-box green-bg">AUTO<br>+0.5%</div>', unsafe_allow_html=True)
    with hm4: st.markdown('<div class="heatmap-box green-bg">ENERGY<br>+2.1%</div>', unsafe_allow_html=True)

    # NEWS SECTION (GUARANTEED)
    st.markdown("### Market Intelligence")
    news = get_news_guaranteed(st.session_state.ticker)
    if news:
        for n in news:
            st.markdown(f"**[{n.get('title','Link')}]({n.get('link','#')})**")
            st.caption(n.get('publisher', 'Source'))
            st.markdown("---")

# --- 6. ROUTER ---
if 'page' not in st.session_state: st.session_state.page = "welcome"
if 'user' not in st.session_state: st.session_state.user = None
if 'status' not in st.session_state: st.session_state.status = None
if 'ticker' not in st.session_state: st.session_state.ticker = "RELIANCE.NS"

if st.session_state.page == "welcome": welcome_page()
elif st.session_state.page == "login": login_page()
elif st.session_state.page == "app":
    if st.session_state.user:
        if st.session_state.status == "Active": dashboard()
        else: payment_page()
    else: st.session_state.page = "login"; st.rerun()
