import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json
import hashlib
import os

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
    
    /* Pricing Cards */
    .price-card { background: #151821; border: 1px solid #2E3345; border-radius: 15px; padding: 20px; text-align: center; transition: 0.3s; }
    .price-card:hover { border-color: #00FF7F; transform: scale(1.02); }
    .price-amount { font-size: 32px; font-weight: bold; color: #FAFAFA; }
    .price-period { font-size: 14px; color: #A0A5B5; }
    
    .stTextInput input { background-color: #151821 !important; color: white !important; border-radius: 12px; border: 1px solid #2E3345; }
    div[data-testid="stMetricValue"] { font-size: 28px; color: #ffffff; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 1. BACKEND (Database & Auth) ---
def get_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except: return None

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(username, password):
    client = get_client()
    if not client: return False, "Error"
    try:
        try: sheet = client.open("Stock_App_DB").worksheet("Users")
        except: 
            sheet = client.open("Stock_App_DB").add_worksheet(title="Users", rows=100, cols=3)
            sheet.append_row(["Username", "PasswordHash", "Status"])
        users = sheet.get_all_records()
        hashed_pw = make_hash(password)
        for user in users:
            if user['Username'] == username and user['PasswordHash'] == hashed_pw:
                # Returns (True, Status)
                return True, user.get("Status", "Inactive")
        return False, "Invalid"
    except: return False, "Error"

def sign_up_user(username, password):
    client = get_client()
    if not client: return False
    try:
        try: sheet = client.open("Stock_App_DB").worksheet("Users")
        except: 
            sheet = client.open("Stock_App_DB").add_worksheet(title="Users", rows=100, cols=3)
            sheet.append_row(["Username", "PasswordHash", "Status"])
        if sheet.find(username): return False
        sheet.append_row([username, make_hash(password), "Inactive"])
        return True
    except: return False

def request_activation(username):
    """Updates status to Pending"""
    client = get_client()
    if not client: return False
    try:
        sheet = client.open("Stock_App_DB").worksheet("Users")
        cell = sheet.find(username)
        if cell:
            sheet.update_cell(cell.row, 3, "Pending")
            return True
    except: return False

def activate_user(username):
    """Admin function to activate user"""
    client = get_client()
    if not client: return False
    try:
        sheet = client.open("Stock_App_DB").worksheet("Users")
        cell = sheet.find(username)
        if cell:
            sheet.update_cell(cell.row, 3, "Active")
            return True
    except: return False

def load_user_data(username):
    client = get_client()
    if not client: return None
    try:
        try: sheet = client.open("Stock_App_DB").worksheet("AppData")
        except: 
            sheet = client.open("Stock_App_DB").add_worksheet(title="AppData", rows=100, cols=4)
            sheet.append_row(["Username", "Balance", "Watchlist", "Portfolio"])
        cell = sheet.find(username)
        if cell:
            row_values = sheet.row_values(cell.row)
            return {"Balance": float(row_values[1]), "Watchlist": json.loads(row_values[2]), "Portfolio": json.loads(row_values[3])}
        else:
            default_data = [username, 1000000.0, json.dumps(["RELIANCE.NS", "TCS.NS"]), json.dumps({})]
            sheet.append_row(default_data)
            return {"Balance": 1000000.0, "Watchlist": ["RELIANCE.NS", "TCS.NS"], "Portfolio": {}}
    except: return None

def save_user_data(username, balance, watchlist, portfolio):
    client = get_client()
    if not client: return
    try:
        sheet = client.open("Stock_App_DB").worksheet("AppData")
        cell = sheet.find(username)
        row_data = [username, balance, json.dumps(watchlist), json.dumps(portfolio)]
        if cell:
            for i, val in enumerate(row_data): sheet.update_cell(cell.row, i+1, val)
        else: sheet.append_row(row_data)
    except: pass

# --- 2. SESSION & STATE MANAGEMENT ---
if "page" not in st.session_state: st.session_state["page"] = "welcome"
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "username" not in st.session_state: st.session_state["username"] = ""
if "subscription_status" not in st.session_state: st.session_state["subscription_status"] = "Inactive"

# Auto-Create Admin 'arun'
if "admin_check" not in st.session_state:
    client = get_client()
    if client:
        try:
            sheet = client.open("Stock_App_DB").worksheet("Users")
            if not sheet.find("arun"): sheet.append_row(["arun", make_hash("9700"), "Active"])
        except: pass
    st.session_state["admin_check"] = True

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
    st.caption("Access your personal portfolio.")
    
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
        st.info("ℹ️ New accounts require manual activation after payment.")
        new_user = st.text_input("New Username", key="s_user")
        new_pw = st.text_input("New Password", type="password", key="s_pw")
        if st.button("Create Account", use_container_width=True):
            if sign_up_user(new_user, new_pw): st.success("Account Created! Please Log In.")
            else: st.error("Username taken.")
            
    if st.button("← Back to Home"):
        st.session_state["page"] = "welcome"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def payment_page():
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.title("🔒 Choose Your Plan")
    st.caption(f"Hello {st.session_state['username']}, please select a subscription.")

    # Status Message
    status = st.session_state.get("subscription_status", "Inactive")
    if status == "Pending":
        st.info("⏳ Your payment is under review! Please wait for Admin approval.")
    
    # PRICING CARDS
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="price-card"><h3>Starter</h3><div class="price-amount">₹100</div><div class="price-period">1 Month</div><br><small>✅ Full Access<br>✅ Portfolio<br>✅ AI Scores</small></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="price-card" style="border-color: #FFD700;"><h3 style="color:#FFD700">Value</h3><div class="price-amount">₹279</div><div class="price-period">3 Months</div><br><small>✅ Save 7%<br>✅ Priority Support<br>✅ All Features</small></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="price-card"><h3>Pro</h3><div class="price-amount">₹1000</div><div class="price-period">1 Year</div><br><small>✅ Save 17%<br>✅ Long Term<br>✅ All Features</small></div>', unsafe_allow_html=True)
    
    st.divider()
    
    # QR CODE SECTION
    st.markdown("### 📲 Scan to Pay")
    col_qr, col_info = st.columns([1, 2])
    
    with col_qr:
        if os.path.exists("qrcode.jpg"): st.image("qrcode.jpg", caption="Scan with Any UPI App", width=200)
        else: st.warning("⚠️ Admin: Upload 'qrcode.jpg' to GitHub")
            
    with col_info:
        st.markdown("""
        1. Select plan (₹100, ₹279, or ₹1000).
        2. Scan QR or pay to **lakshyazzzshah@gmail.com**
        3. **Click the button below** to notify Admin.
        """)
        
        # THE NOTIFICATION BUTTON
        if st.button("✅ I Have Made Payment", type="primary"):
            if request_activation(st.session_state["username"]):
                st.session_state["subscription_status"] = "Pending"
                st.success("Admin Notified! We will activate your account shortly.")
                st.rerun()
            else:
                st.error("Error connecting to server.")
        
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

    # --- ADMIN PANEL (Only for 'arun') ---
    if st.session_state["username"] == "arun":
        st.divider()
        st.markdown("### 👑 Admin: Manage Users")
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        
        client = get_client()
        sheet = client.open("Stock_App_DB").worksheet("Users")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Filter only Pending requests
        pending_users = df[df['Status'] == 'Pending']
        
        if not pending_users.empty:
            st.error(f"🔔 You have {len(pending_users)} Pending Payments!")
            st.dataframe(pending_users[["Username", "Status"]], use_container_width=True)
            
            # Simple approval form
            u_to_approve = st.selectbox("Select User to Approve", pending_users['Username'].unique())
            if st.button(f"✅ Approve Payment for {u_to_approve}"):
                if activate_user(u_to_approve):
                    st.success(f"{u_to_approve} is now Active!")
                    st.rerun()
                else: st.error("Failed to update.")
        else:
            st.success("No pending payments.")
            st.write("All Users:")
            st.dataframe(df[["Username", "Status"]], use_container_width=True)
            
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
