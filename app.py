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
st.set_page_config(page_title="FrontPage Pro", layout="wide", initial_sidebar_state="expanded")

# --- 0. DATABASE ENGINE ---
DB_FILE = "pro_stock.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, status TEXT, plan TEXT, start_date TEXT, expiry_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_data (username TEXT PRIMARY KEY, balance REAL, watchlist TEXT, portfolio TEXT)''')
    try:
        admin_pw = hashlib.sha256(str.encode("9700")).hexdigest()
        default_wl = json.dumps(["RELIANCE.NS", "TCS.NS", "ZOMATO.NS", "TATAMOTORS.NS", "HDFCBANK.NS"])
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)", ("arun", admin_pw, "Active", "Lifetime", datetime.now().strftime("%Y-%m-%d"), "2099-12-31"))
        c.execute("INSERT OR IGNORE INTO user_data VALUES (?, ?, ?, ?)", ("arun", 1000000.0, default_wl, json.dumps({})))
        conn.commit()
    except: pass
    conn.close()

init_db()

# --- 1. FRONTPAGE UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap');

    .stApp {
        background-color: #0b0f19; /* FrontPage Dark Blue */
        color: #e1e4e8;
        font-family: 'Inter', sans-serif;
    }

    /* --- WELCOME PAGE STYLES --- */
    .hero-text {
        font-size: 70px;
        font-weight: 900;
        letter-spacing: -2px;
        background: linear-gradient(180deg, #fff, #888);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
        margin-bottom: 20px;
    }
    .ticker-wrap {
        width: 100%;
        background: rgba(255,255,255,0.05);
        color: #2EBD85;
        font-family: monospace;
        padding: 10px 0;
        text-align: center;
        margin-bottom: 30px;
    }
    .welcome-card {
        background: rgba(20, 20, 20, 0.7);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }

    /* --- TRADE LAB (PORTFOLIO) STYLES --- */
    .tradelab-card {
        background: #151a25;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #2a2e39;
        margin-bottom: 20px;
    }
    .portfolio-val { font-size: 32px; font-weight: 700; color: #fff; margin: 0; }
    .pl-val { font-size: 24px; font-weight: 600; color: #2EBD85; text-align: right; }
    .sub-label { color: #8b949e; font-size: 14px; margin-top: 5px; }
    .margin-row { display: flex; justify-content: space-between; margin-top: 20px; padding-top: 20px; border-top: 1px solid #2a2e39; }
    .margin-item { font-size: 14px; color: #fff; font-weight: 600; }
    .margin-lbl { color: #8b949e; font-weight: 400; }

    /* --- STOCK DETAILS TABS --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
        border-bottom: 1px solid #2a2e39;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border: none;
        color: #8b949e;
        font-weight: 600;
        font-size: 15px;
    }
    .stTabs [aria-selected="true"] {
        color: #2962ff !important;
        border-bottom: 2px solid #2962ff !important;
    }

    /* --- DATA TAB (SLIDERS) --- */
    .price-range-card {
        background: #1e222d;
        border: 1px solid #2a2e39;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .range-header { display: flex; justify-content: space-between; font-size: 13px; color: #8b949e; margin-bottom: 8px; }
    .range-values { display: flex; justify-content: space-between; font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 8px; }
    .range-track { width: 100%; height: 4px; background: #2a2e39; border-radius: 2px; position: relative; }
    .range-fill { height: 100%; background: #2962ff; border-radius: 2px; position: absolute; }
    .range-thumb { width: 12px; height: 12px; background: #2962ff; border-radius: 50%; position: absolute; top: -4px; border: 2px solid #0b0f19; }

    /* --- TECHNICAL GRID --- */
    .tech-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        background: #1e222d;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #2a2e39;
    }
    .tech-item-lbl { color: #8b949e; font-size: 12px; margin-bottom: 4px; }
    .tech-item-val { color: #fff; font-size: 16px; font-weight: 600; }

    /* --- POSTS --- */
    .post-card {
        padding: 15px 0;
        border-bottom: 1px solid #2a2e39;
    }
    .post-header { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
    .user-avatar { width: 30px; height: 30px; background: #2962ff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }
    .user-name { font-weight: 700; font-size: 14px; color: #fff; }
    .post-time { font-size: 12px; color: #8b949e; }
    .post-content { font-size: 14px; color: #e1e4e8; line-height: 1.5; }
    .post-tag { color: #2962ff; font-weight: 600; }

    /* --- REPORTS --- */
    .report-row {
        padding: 15px;
        border-bottom: 1px solid #2a2e39;
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
    }
    .report-row:hover { background: #1c212b; }
    .report-icon { font-size: 18px; margin-right: 10px; }

    /* --- BUTTONS --- */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; padding: 10px; transition: 0.2s; }
    .trade-btn-buy { background-color: #2EBD85; color: white; border: none; }
    .trade-btn-sell { background-color: #F6465D; color: white; border: none; }
    
    .stTextInput input { background-color: #151a25 !important; border: 1px solid #2a2e39 !important; color: white !important; border-radius: 8px; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND LOGIC ---
def get_db(): return sqlite3.connect(DB_FILE)

def login_user(u, p):
    conn = get_db(); c = conn.cursor()
    h = hashlib.sha256(str.encode(p)).hexdigest()
    c.execute("SELECT status FROM users WHERE username=? AND password=?", (u, h))
    res = c.fetchone(); conn.close()
    return (True, res[0]) if res else (False, None)

def signup_user(u, p):
    conn = get_db(); c = conn.cursor()
    try:
        h = hashlib.sha256(str.encode(p)).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (u, h, "Inactive", "None", "", ""))
        c.execute("INSERT INTO user_data VALUES (?, ?, ?, ?)", (u, 1000000.0, json.dumps(["RELIANCE.NS"]), json.dumps({})))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def get_data(u):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT balance, watchlist, portfolio FROM user_data WHERE username=?", (u,))
    r = c.fetchone(); conn.close()
    if r:
        wl = json.loads(r[1])
        if isinstance(wl, str): wl = [wl] # Fallback
        return r[0], wl, json.loads(r[2])
    return 1000000.0, [], {}

def save_data(u, b, w, p):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE user_data SET balance=?, watchlist=?, portfolio=? WHERE username=?", (b, json.dumps(w), json.dumps(p), u))
    conn.commit(); conn.close()

# --- 3. DATA ENGINE (500+ STOCKS) ---
STOCK_LIST = [
    "🔍 Search...",
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", 
    "TATAMOTORS.NS", "M&M.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TATASTEEL.NS", "COALINDIA.NS", "BPCL.NS", 
    "WIPRO.NS", "TECHM.NS", "LTIM.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "GRASIM.NS", "HINDALCO.NS", "DRREDDY.NS", 
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS", "VBL.NS", "TRENT.NS", "HAL.NS", "BEL.NS", "IRFC.NS", "RVNL.NS", 
    "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "PFC.NS", "RECLTD.NS", "TATAPOWER.NS", "ADANIGREEN.NS", 
    "DLF.NS", "LODHA.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "SOBHA.NS",
    "AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "BTC-USD", "ETH-USD"
]

def get_stock_data_pro(t):
    try:
        s = yf.Ticker(t); h = s.history(period="1y"); i = s.info
        if h.empty: return None
        
        # Calculations for Data Tab
        last = h.iloc[-1]
        prev = h.iloc[-2]
        
        # DMAs
        dma12 = h['Close'].rolling(12).mean().iloc[-1]
        dma50 = h['Close'].rolling(50).mean().iloc[-1]
        dma100 = h['Close'].rolling(100).mean().iloc[-1]
        dma200 = h['Close'].rolling(200).mean().iloc[-1]
        
        return {
            "name": i.get('longName', t),
            "price": last['Close'],
            "change": last['Close'] - prev['Close'],
            "pct": ((last['Close'] - prev['Close'])/prev['Close'])*100,
            "day_high": last['High'], "day_low": last['Low'],
            "year_high": h['High'].max(), "year_low": h['Low'].min(),
            "open": last['Open'], "prev": prev['Close'], "vol": last['Volume'],
            "dma": {"12": dma12, "50": dma50, "100": dma100, "200": dma200}
        }
    except: return None

# --- 4. UI PAGES ---

def welcome_page():
    # YOUR ORIGINAL WELCOME UI
    st.markdown("""<div class="ticker-wrap">LIVE MARKET: &nbsp;&nbsp; BTC $98,420 ▲ &nbsp;|&nbsp; NIFTY 24,500 ▲ &nbsp;|&nbsp; RELIANCE ₹1,571 ▲ &nbsp;|&nbsp; SYSTEM: ONLINE</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.markdown('<h1 class="hero-text">Trading is Math.<br>Not Magic.</h1>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:20px; color:#a1a1aa;">The <b>Quantum Trader AI</b> processes 50+ technical indicators instantly.</p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start Free Trial"): st.session_state.page = "login"; st.rerun()
    with c2:
        st.markdown("""<div class="welcome-card" style="transform: rotate(-2deg); margin-top: 20px; border-color: #2EBD85;"><h1 style="font-size:50px; margin:0; color:#fff;">BUY</h1><p style="color:#aaa;">Confidence: 98%</p></div>""", unsafe_allow_html=True)

def login_page():
    st.markdown('<div class="welcome-card" style="max-width:400px; margin:auto; margin-top:50px;"><h2>Login</h2>', unsafe_allow_html=True)
    u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Enter"):
        ok, stat = login_user(u, p)
        if ok: st.session_state.user = u; st.session_state.status = stat; st.session_state.page = "app"; st.rerun()
        else: st.error("Invalid")
    st.markdown('</div>', unsafe_allow_html=True)

def dashboard():
    bal, wl, port = get_data(st.session_state.user)
    
    # --- SIDEBAR (NAVIGATION) ---
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown("### 📂 Watchlist")
        sel = st.selectbox("Add Stock", STOCK_LIST)
        if sel != "🔍 Search..." and st.button("Add"): 
            if sel not in wl: wl.append(sel); save_data(st.session_state.user, bal, wl, port); st.rerun()
        
        for t in wl:
            if st.button(t, key=f"wl_{t}", use_container_width=True): st.session_state.ticker = t; st.rerun()
        
        st.markdown("---")
        if st.button("Log Out"): st.session_state.user=None; st.session_state.page="welcome"; st.rerun()

    # --- MAIN TABS (Trade Lab vs Stock View) ---
    main_tab1, main_tab2 = st.tabs(["🏛️ Trade Lab", "📈 Stock View"])

    # 1. TRADE LAB (PORTFOLIO)
    with main_tab1:
        # Portfolio Summary Card
        st.markdown(f"""
        <div class="tradelab-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><div class="portfolio-val">₹{bal:,.2f}</div><div class="sub-label">Total Portfolio ⓘ</div></div>
                <div><div class="pl-val">₹0.00</div><div class="sub-label" style="text-align:right">Unrealised P&L</div></div>
            </div>
            <div class="margin-row">
                <div><div class="margin-lbl">Available Margin</div><div class="margin-item">₹{bal:,.2f}</div></div>
                <div><div class="margin-lbl">Invested Margin</div><div class="margin-item">₹0.00</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Tabs for Trade Lab
        tl_t1, tl_t2, tl_t3 = st.tabs(["Discover", "Positions", "Performance"])
        with tl_t1: 
            st.info("Market Movers & Option Chain coming soon.")
        with tl_t2:
            if port:
                pd_d = []
                for t, d in port.items():
                    data = get_stock_data_pro(t)
                    curr = data['price'] if data else d['avg']
                    pl = (curr - d['avg']) * d['qty']
                    pd_d.append({"Ticker": t, "Qty": d['qty'], "Avg": round(d['avg'],1), "LTP": round(curr,1), "P/L": round(pl,1)})
                st.dataframe(pd.DataFrame(pd_d), hide_index=True, use_container_width=True)
            else:
                st.markdown("""<div style="text-align:center; padding:40px; color:#888;"><h3>No open positions.</h3><p>To submit a trade tap on Stock View.</p></div>""", unsafe_allow_html=True)

    # 2. STOCK VIEW (FRONTPAGE STYLE)
    with main_tab2:
        data = get_stock_data_pro(st.session_state.ticker)
        if not data: st.error("Loading data..."); return

        # Header
        clr = "#2EBD85" if data['change'] >= 0 else "#F6465D"
        st.markdown(f"## {data['name']}")
        st.markdown(f"<span style='font-size:32px; font-weight:bold'>₹{data['price']:,.2f}</span> <span style='color:{clr}; font-size:18px'>{data['change']:+.2f} ({data['pct']:+.2f}%)</span>", unsafe_allow_html=True)

        # Stock Tabs
        st_t1, st_t2, st_t3, st_t4 = st.tabs(["Posts", "Updates", "Data", "Reports"])

        with st_t1: # POSTS
            st.markdown(f"""
            <div class="post-card">
                <div class="post-header"><div class="user-avatar">AR</div><div class="user-name">aartirahulpal <span style="color:#888;font-weight:400">Dec 30</span></div></div>
                <div class="post-content"><span class="post-tag">#{st.session_state.ticker}</span> Option (Intraday Learning Trade). Buying 1550 CE at 32. Target 38. Stoploss 28.</div>
            </div>
            <div class="post-card">
                <div class="post-header"><div class="user-avatar">SB</div><div class="user-name">StockBets <span style="color:#888;font-weight:400">Dec 25</span></div></div>
                <div class="post-content">Bearish view on <span class="post-tag">#{st.session_state.ticker}</span>. Resistance at {data['day_high']:.0f}. Watch out for reversal.</div>
            </div>
            """, unsafe_allow_html=True)

        with st_t2: # UPDATES
            st.markdown(f"""
            <div class="post-card">
                <div class="post-header"><div class="user-avatar" style="background:#2962ff">CA</div><div class="user-name">corpannouncement</div></div>
                <div class="post-content"><b>{st.session_state.ticker} Tax Penalty:</b> Company fined Rs. 1.11 Crore due to alleged incorrect input tax credit claims. Plans to appeal.</div>
            </div>
            """, unsafe_allow_html=True)

        with st_t3: # DATA
            st.markdown("#### Price Summary")
            # Day Range
            rng_pct = ((data['price'] - data['day_low']) / (data['day_high'] - data['day_low'] + 0.01)) * 100
            st.markdown(f"""
            <div class="price-range-card">
                <div class="range-header"><span>Today's Low</span><span>Today's High</span></div>
                <div class="range-values"><span>₹{data['day_low']:,.2f}</span><span>₹{data['day_high']:,.2f}</span></div>
                <div class="range-track"><div class="range-fill" style="width:{rng_pct}%"></div><div class="range-thumb" style="left:{rng_pct}%"></div></div>
                
                <div style="margin-top:20px;"></div>
                <div class="range-header"><span>52 Week Low</span><span>52 Week High</span></div>
                <div class="range-values"><span>₹{data['year_low']:,.2f}</span><span>₹{data['year_high']:,.2f}</span></div>
                <div class="range-track"><div class="range-fill" style="width:50%"></div><div class="range-thumb" style="left:50%"></div></div>

                <div style="display:flex; justify-content:space-between; margin-top:20px; border-top:1px solid #2a2e39; padding-top:10px;">
                    <div><div class="range-header">Open</div><div class="range-values" style="font-size:14px">₹{data['open']:,.2f}</div></div>
                    <div><div class="range-header">Prev Close</div><div class="range-values" style="font-size:14px">₹{data['prev']:,.2f}</div></div>
                    <div><div class="range-header">Volume</div><div class="range-values" style="font-size:14px">{data['vol']:,}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("#### Technical Summary")
            st.markdown(f"""
            <div class="tech-grid">
                <div><div class="tech-item-lbl">DMA(12)</div><div class="tech-item-val">₹{data['dma']['12']:,.2f}</div></div>
                <div><div class="tech-item-lbl">DMA(50)</div><div class="tech-item-val">₹{data['dma']['50']:,.2f}</div></div>
                <div><div class="tech-item-lbl">DMA(100)</div><div class="tech-item-val">₹{data['dma']['100']:,.2f}</div></div>
                <div><div class="tech-item-lbl">DMA(200)</div><div class="tech-item-val">₹{data['dma']['200']:,.2f}</div></div>
            </div>
            """, unsafe_allow_html=True)

        with st_t4: # REPORTS
            reports = ["Concall Q2FY26 Summary", "Concall Q4FY25 Summary", "Concall Q3FY25 Summary", "Concall Q2FY25 Summary"]
            for r in reports:
                st.markdown(f"""
                <div class="report-row">
                    <div style="display:flex; align-items:center;"><span class="report-icon">📄</span> {r}</div>
                    <div style="color:#888">></div>
                </div>
                """, unsafe_allow_html=True)

        # --- TRADE ACTION PAD ---
        st.markdown("---")
        c_q, c_b, c_s = st.columns([1, 1, 1])
        with c_q:
            qty = st.number_input("Qty", 1, 10000, 10, label_visibility="collapsed")
        with c_b:
            if st.button("BUY", key="b_btn"):
                cost = qty * data['price']
                if bal >= cost:
                    bal -= cost
                    p = port.get(st.session_state.ticker, {'qty':0, 'avg':0})
                    n_avg = ((p['qty']*p['avg']) + cost)/(p['qty']+qty)
                    port[st.session_state.ticker] = {'qty': p['qty']+qty, 'avg': n_avg}
                    save_data(st.session_state.user, bal, wl, port)
                    st.success("Order Placed!"); time.sleep(0.5); st.rerun()
                else: st.error("No Funds")
        with c_s:
            if st.button("SELL", key="s_btn"):
                if st.session_state.ticker in port and port[st.session_state.ticker]['qty'] >= qty:
                    bal += qty * data['price']
                    port[st.session_state.ticker]['qty'] -= qty
                    if port[st.session_state.ticker]['qty'] == 0: del port[st.session_state.ticker]
                    save_data(st.session_state.user, bal, wl, port)
                    st.success("Order Placed!"); time.sleep(0.5); st.rerun()
                else: st.error("Invalid")

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
