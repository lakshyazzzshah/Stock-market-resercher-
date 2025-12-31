import streamlit as st
import yfinance as yf
import pandas as pd
import json
import hashlib
import os
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro Stock AI", layout="centered", initial_sidebar_state="collapsed")

# --- 🎨 CUSTOM MODERN CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .css-card { background-color: #1E2130; border-radius: 20px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px; border: 1px solid #2E3345; }
    .score-badge { font-size: 60px; font-weight: 800; text-align: center; margin: 0; padding: 0; }
    .score-title { text-transform: uppercase; letter-spacing: 2px; font-size: 14px; color: #A0A5B5; text-align: center; }
    .hero-title { font-size: 50px; font-weight: 800; background: -webkit-linear-gradient(45deg, #00FF7F, #00BFFF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 10px;}
    .hero-sub { font-size: 18px; color: #A0A5B5; text-align: center; margin-bottom: 40px; }
    .feature-box { background: #151821; padding: 15px; border-radius: 12px; border: 1px solid #2E3345; text-align: center; }
    .price-card { background: #151821; border: 1px solid #2E3345; border-radius: 15px; padding: 20px; text-align: center; transition: 0.3s; }
    .price-card:hover { border-color: #00FF7F; transform: scale(1.02); }
    .price-amount { font-size: 32px; font-weight: bold; color: #FAFAFA; }
    .stTextInput input { background-color: #151821 !important; color: white !important; border-radius: 12px; border: 1px solid #2E3345; }
    div[data-testid="stMetricValue"] { font-size: 28px; color: #ffffff; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 1. LOCAL DATABASE SYSTEM (NO GOOGLE CLOUD NEEDED) ---
USERS_FILE = "users_db.csv"
DATA_FILE = "app_data.csv"

def init_local_db():
    # Create Users File if not exists
    if not os.path.exists(USERS_FILE):
        df = pd.DataFrame(columns=["Username", "PasswordHash", "Status"])
        # Add Admin
        admin_row = pd.DataFrame([{"Username": "arun", "PasswordHash": hashlib.sha256(str.encode("9700")).hexdigest(), "Status": "Active"}])
        df = pd.concat([df, admin_row], ignore_index=True)
        df.to_csv(USERS_FILE, index=False)
    
    # Create Data File if not exists
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=["Username", "Balance", "Watchlist", "Portfolio"])
        # Add Admin Data
        admin_data = pd.DataFrame([{
            "Username": "arun", 
            "Balance": 1000000.0, 
            "Watchlist": json.dumps(["RELIANCE.NS", "TCS.NS"]), 
            "Portfolio": json.dumps({})
        }])
        df = pd.concat([df, admin_data], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(username, password):
    try:
        df = pd.read_csv(USERS_FILE)
        hashed_pw = make_hash(password)
        user = df[(df['Username'] == username) & (df['PasswordHash'] == hashed_pw)]
        if not user.empty:
            return True, user.iloc[0]['Status']
        return False, "Invalid"
    except: return False, "Error"

def sign_up_user(username, password):
    try:
        df = pd.read_csv(USERS_FILE)
        if username in df['Username'].values:
            return False
        
        new_user = pd.DataFrame([{
            "Username": username, 
            "PasswordHash": make_hash(password), 
            "Status": "Inactive"
        }])
        df = pd.concat([df, new_user], ignore_index=True)
        df.to_csv(USERS_FILE, index=False)
        return True
    except: return False

def request_activation(username):
    try:
        df = pd.read_csv(USERS_FILE)
        idx = df.index[df['Username'] == username].tolist()
        if idx:
            df.at[idx[0], 'Status'] = 'Pending'
            df.to_csv(USERS_FILE, index=False)
            return True
        return False
    except: return False

def activate_user(username):
    try:
        df = pd.read_csv(USERS_FILE)
        idx = df.index[df['Username'] == username].tolist()
        if idx:
            df.at[idx[0], 'Status'] = 'Active'
            df.to_csv(USERS_FILE, index=False)
            return True
        return False
    except: return False

def load_user_data(username):
    try:
        df = pd.read_csv(DATA_FILE)
        user_row = df[df['Username'] == username]
        
        if user_row.empty:
            # Create default data
            new_data = pd.DataFrame([{
                "Username": username, 
                "Balance": 1000000.0, 
                "Watchlist": json.dumps(["RELIANCE.NS", "TCS.NS"]), 
                "Portfolio": json.dumps({})
            }])
            # Append and Save
            new_data.to_csv(DATA_FILE, mode='a', header=False, index=False)
            return {"Balance": 1000000.0, "Watchlist": ["RELIANCE.NS", "TCS.NS"], "Portfolio": {}}
        
        row = user_row.iloc[0]
        return {
            "Balance": float(row["Balance"]),
            "Watchlist": json.loads(row["Watchlist"]),
            "Portfolio": json.loads(row["Portfolio"])
        }
    except: return None

def save_user_data(username, balance, watchlist, portfolio):
    try:
        df = pd.read_csv(DATA_FILE)
        idx = df.index[df['Username'] == username].tolist()
        
        if idx:
            df.at[idx[0], 'Balance'] = balance
            df.at[idx[0], 'Watchlist'] = json.dumps(watchlist)
            df.at[idx[0], 'Portfolio'] = json.dumps(portfolio)
        else:
            new_row = pd.DataFrame([{
                "Username": username,
                "Balance": balance,
                "Watchlist": json.dumps(watchlist),
                "Portfolio": json.dumps(portfolio)
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            
        df.to_csv(DATA_FILE, index=False)
    except: pass

# Initialize Files
init_local_db()

# --- 2. SESSION STATE ---
if "page" not in st.session_state: st.session_state["page"] = "welcome"
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "username" not in st.session_state: st.session_state["username"] = ""
if "subscription_status" not in st.session_state: st.session_state["subscription_status"] = "Inactive"

def logout():
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["subscription_status"] = "Inactive"
    st.session_state["page"] = "welcome"
    st.rerun()

def go_to_login():
    st.session_state["page"] = "login"
    st.rerun()

# --- 3. UI PAGES ---

def welcome_page():
    st.markdown('<div style="padding-top: 50px;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Investing Wisdom,<br>Simplified.</h1>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Analyze stocks using legendary strategies.<br>Premium Access Only.</p>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown('<div class="feature-box">📚<br><b>Book Wisdom</b><br><span style="font-size:12px; color:#A0A5B5">Strategies from top best-sellers.</span></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="feature-box">🤖<br><b>AI Score</b><br><span style="font-size:12px; color:#A0A5B5">Simple 0-100 verdict on any stock.</span></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="feature-box">🛡️<br><b>Trust Check</b><br><span style="font-size:12px; color:#A0A5B5">Avoid scams with Reliability checks.</span></div>', unsafe_allow_html=True)
    
    st.markdown('<br><br>', unsafe_allow_html=True)
    col_center = st.columns([1, 2, 1])
    with col_center[1]:
        if st.button("🚀 Member Login", type="primary", use_container_width=True):
            go_to_login()
    st.markdown('<p style="text-align:center; margin-top:50px; font-size:12px; color:#555;">© 2024 Pro Stock AI. All Rights Reserved.</p>', unsafe_allow_html=True)

def login_page():
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.title("🔐 Login")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        user = st.text_input("Username", key="l_user")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("Log In", type="primary", use_container_width=True):
            success, status = check_login(user, pw)
            if success:
                st.session_state["logged_in"] = True
                st.session_state["username"] = user
                st.session_state["subscription_status"] = status
                if status == "Active": st.session_state["page"] = "app"
                else: st.session_state["page"] = "payment"
                st.rerun()
            else: st.error("Incorrect details.")
                
    with tab2:
        st.info("ℹ️ New accounts require activation.")
        new_user = st.text_input("New Username", key="s_user")
        new_pw = st.text_input("New Password", type="password", key="s_pw")
        if st.button("Create Account", use_container_width=True):
            if sign_up_user(new_user, new_pw): st.success("Created! Please Log In.")
            else: st.error("Username taken.")
            
    if st.button("← Back"):
        st.session_state["page"] = "welcome"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def payment_page():
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.title("🔒 Choose Your Plan")
    st.caption(f"Hello {st.session_state['username']}, please select a subscription.")

    status = st.session_state.get("subscription_status", "Inactive")
    if status == "Pending":
        st.info("⏳ Payment Under Review. Please wait for Admin approval.")
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown('<div class="price-card"><h3>Starter</h3><div class="price-amount">₹100</div><div class="price-period">1 Month</div><br><small>✅ Full Access</small></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="price-card" style="border-color: #FFD700;"><h3 style="color:#FFD700">Value</h3><div class="price-amount">₹279</div><div class="price-period">3 Months</div><br><small>✅ Best Seller</small></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="price-card"><h3>Pro</h3><div class="price-amount">₹1000</div><div class="price-period">1 Year</div><br><small>✅ Save Big</small></div>', unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("### 📲 Scan to Pay")
    col_qr, col_info = st.columns([1, 2])
    
    with col_qr:
        if os.path.exists("qrcode.jpg"): st.image("qrcode.jpg", width=200)
        else: st.warning("⚠️ Admin: Upload 'qrcode.jpg' to GitHub")
            
    with col_info:
        st.markdown("1. Pay via UPI.\n2. **Click button below** to notify Admin.")
        
        if st.button("✅ I Have Made Payment", type="primary"):
            if request_activation(st.session_state["username"]):
                st.session_state["subscription_status"] = "Pending"
                st.success("Admin Notified!")
                time.sleep(1)
                st.rerun()
            else: st.error("Error connecting.")
        
    if st.button("Log Out"): logout()
    st.markdown('</div>', unsafe_allow_html=True)

def main_app():
    if "data_loaded" not in st.session_state:
        data = load_user_data(st.session_state["username"])
        if data:
            st.session_state["balance"] = data["Balance"]
            st.session_state["watchlist"] = data["Watchlist"]
            st.session_state["portfolio"] = data["Portfolio"]
        st.session_state["data_loaded"] = True
        
    if "selected_ticker" not in st.session_state: st.session_state["selected_ticker"] = "RELIANCE.NS"

    def save_state():
        save_user_data(st.session_state["username"], st.session_state["balance"], st.session_state["watchlist"], st.session_state["portfolio"])

    # HEADER
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    c1.title(f"👋 Hi, {st.session_state['username']}")
    c1.caption("Pro Stock AI • Premium Member")
    c2.metric("Wallet", f"₹{st.session_state['balance']:,.0f}")
    if c2.button("Log Out"): logout()
    st.markdown('</div>', unsafe_allow_html=True)

    # SEARCH
    c_search, c_btn = st.columns([4, 1])
    query = c_search.text_input("Search Ticker", st.session_state["selected_ticker"], label_visibility="collapsed")
    if c_btn.button("🔍", type="primary"):
        st.session_state["selected_ticker"] = query.upper().strip()
        st.rerun()

    current_stock = st.session_state["selected_ticker"]
    
    # ANALYSIS
    try:
        stock = yf.Ticker(current_stock)
        info = stock.info
        price = info.get("currentPrice", 0)
        score = 0
        reasons = []
        if info.get("returnOnEquity", 0) > 0.15: score += 20; reasons.append("✅ High Efficiency (ROE)")
        if info.get("grossMargins", 0) > 0.40: score += 20; reasons.append("✅ Strong Brand (High Margins)")
        if info.get("dividendYield", 0) > 0.015: score += 15; reasons.append("✅ Pays Dividends")
        if info.get("heldPercentInstitutions", 0) > 0.40: score += 15; reasons.append("✅ Institutional Trust")
        if info.get("beta", 1.5) < 1.2: score += 10; reasons.append("✅ Low Volatility")
        if info.get("trailingPE", 0) < 25: score += 20; reasons.append("✅ Good Valuation")
        name = info.get("longName", current_stock)
    except: score, price, name, reasons = 0, 0, "Not Found", ["Invalid Ticker"]

    # SCORE CARD
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    col_a, col_b = st.columns([2, 3])
    color = "#00FF7F" if score >= 80 else "#FFD700" if score >= 50 else "#FF4B4B"
    with col_a:
        st.markdown(f'<p class="score-title">AI VERDICT</p><p class="score-badge" style="color: {color};">{score}</p><p style="text-align:center; color:{color}; font-weight:bold;">/ 100</p>', unsafe_allow_html=True)
    with col_b:
        st.subheader(name)
        st.metric("Price", f"₹{price:,.2f}")
        if score >= 80: st.success("Strong Buy")
        elif score >= 50: st.warning("Hold")
        else: st.error("Avoid")
    st.markdown('</div>', unsafe_allow_html=True)
    
    with st.expander("See Analysis Details"):
        for r in reasons: st.write(r)
    
    # TRADING
    st.markdown("### ⚡ Trade Actions")
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    c_qty, c_buy, c_sell = st.columns([1, 2, 2])
    qty = c_qty.number_input("Qty", 1, value=10, label_visibility="collapsed")
    if c_buy.button("🟢 BUY", use_container_width=True):
        cost = qty * price
        if st.session_state['balance'] >= cost:
            st.session_state['balance'] -= cost
            port = st.session_state['portfolio']
            if current_stock in port:
                old = port[current_stock]
                new_avg = ((old['qty'] * old['avg_price']) + cost) / (old['qty'] + qty)
                port[current_stock] = {'qty': old['qty'] + qty, 'avg_price': new_avg}
            else: port[current_stock] = {'qty': qty, 'avg_price': price}
            save_state()
            st.success("Bought!")
            st.rerun()
        else: st.error("No Funds")
    if c_sell.button("🔴 SELL", use_container_width=True):
        port = st.session_state['portfolio']
        if current_stock in port and port[current_stock]['qty'] >= qty:
            st.session_state['balance'] += (qty * price)
            port[current_stock]['qty'] -= qty
            if port[current_stock]['qty'] == 0: del port[current_stock]
            save_state()
            st.success("Sold!")
            st.rerun()
        else: st.error("No Shares")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # PORTFOLIO
    if st.session_state["portfolio"]:
        st.markdown("### 🎒 Your Holdings")
        for t, d in st.session_state["portfolio"].items():
            live_p = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]
            pl = (live_p - d['avg_price']) * d['qty']
            pl_color = "#00FF7F" if pl >= 0 else "#FF4B4B"
            st.markdown(f'<div style="background:#1E2130; padding:15px; border-radius:12px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;"><div><span style="font-weight:bold; font-size:18px;">{t}</span><br><span style="color:#A0A5B5; font-size:12px;">{d["qty"]} Shares</span></div><div style="text-align:right;"><span style="font-weight:bold; font-size:18px; color:{pl_color}">₹{pl:,.0f}</span></div></div>', unsafe_allow_html=True)

    # ADMIN PANEL (Only for 'arun')
    if st.session_state["username"] == "arun":
        st.divider()
        st.markdown("### 👑 Admin Panel")
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        
        try:
            df = pd.read_csv(USERS_FILE)
            pending_users = df[df['Status'] == 'Pending']
            
            if not pending_users.empty:
                st.error(f"🔔 {len(pending_users)} Pending Request(s)")
                u_to_approve = st.selectbox("Select User", pending_users['Username'].unique())
                if st.button(f"✅ Approve {u_to_approve}"):
                    activate_user(u_to_approve)
                    st.success("Approved!")
                    st.rerun()
            else:
                st.success("No Pending Requests")
                
            with st.expander("View All Users"):
                st.dataframe(df[["Username", "Status"]], use_container_width=True)
        except: st.error("Could not load admin data")
        st.markdown('</div>', unsafe_allow_html=True)

# --- 4. NAVIGATION ---
if st.session_state["page"] == "welcome":
    welcome_page()
elif st.session_state["page"] == "login":
    login_page()
elif st.session_state["page"] == "payment":
    payment_page()
elif st.session_state["page"] == "app" and st.session_state["logged_in"]:
    if st.session_state["subscription_status"] == "Active": main_app()
    else: payment_page()
else:
    welcome_page()
