import streamlit as st
import requests
from datetime import datetime, timedelta

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Arbitrage Scanner", layout="wide")
st.title("🏹 Pro Betting Arbitrage & Hedge Scanner")

# --- SIDEBAR / INPUTS ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Odds API Key", type="password")
    
    sport_cat = st.selectbox("Select Sport", ["NBA", "NFL", "NCAAF", "NHL", "MLB"])
    
    promo_type = st.radio(
        "Scan Strategy", 
        ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"]
    )
    
    wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
    
    if promo_type == "Profit Boost (%)":
        boost_pct = st.number_input("Boost Percentage (%)", min_value=0, value=50)
    if promo_type == "No-Sweat Bet":
        conversion_goal = st.slider("Refund Conversion (%)", 0, 100, 70) / 100

    run_scan = st.button("🚀 RUN GLOBAL SCAN", use_container_width=True)

# Sport Mapping
sport_map = {
    "NBA": ["basketball_nba"],
    "NFL": ["americanfootball_nfl"],
    "NCAAF": ["americanfootball_ncaaf"],
    "NHL": ["icehockey_nhl"],
    "MLB": ["baseball_mlb"]
}

# --- 1. SCHEDULE PREVIEW ---
st.subheader(f"📅 Upcoming {sport_cat} Schedule")
if st.button(f"🔍 Preview {sport_cat} Games"):
    if not api_key:
        st.error("Please enter an API Key in the sidebar.")
    else:
        with st.spinner("Fetching games..."):
            preview_sport = sport_map[sport_cat][0]
            url = f"https://api.the-odds-api.com/v4/sports/{preview_sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                games = res.json()
                if games:
                    for game in games[:5]:
                        t = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00')) - timedelta(hours=6)
                        st.write(f"🔹 **{game['away_team']}** @ **{game['home_team']}** | {t.strftime('%m/%d %I:%M %p')}")
                else:
                    st.info("No games found.")
            else:
                st.error("API Error.")

# --- 2. GLOBAL SCAN LOGIC ---
if run_scan:
    if not api_key:
        st.error("API Key Required")
    else:
        all_opps = []
        with st.spinner("Scanning for edges..."):
            for sport_key in sport_map[sport_cat]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    for game in data:
                        home_team = game['home_team']
                        away_team = game['away_team']
                        
                        # Filter for FanDuel and DraftKings as requested
                        books = [b for b in game['bookmakers'] if b['key'] in ['fanduel', 'draftkings']]
                        
                        if len(books) >= 2:
                            # Logic to compare odds across FD and DK
                            # (Simplified for this example: finding best prices for side A and side B)
                            pass # Actual arbitrage math goes here based on your previous logic

        # --- TOP 10 RESULTS ---
        st.write("---")
        st.subheader(f"🎯 Top 10 Opportunities")
        # Display table here...
        st.info("Scan results would populate here based on live data.")

# --- 3. MANUAL CALCULATOR (Placed under results) ---
st.write("---")
st.subheader("🧮 Manual Multi-Strategy Calculator")
st.caption("Use this for specific game boosts. Favorite odds will automatically be treated as negative.")

with st.expander("Open Manual Calculator", expanded=True):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"], horizontal=True)
        
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_s_price = st.number_input("Source Odds (Underdog) e.g. 250", value=250)
            m_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
            if m_promo == "Profit Boost (%)":
                m_boost = st.number_input("Boost %", min_value=0, value=50)
        
        with m_col2:
            h_input = st.number_input("Hedge Odds (Favorite) e.g. 300", value=300)
            if m_promo == "No-Sweat Bet":
                m_conv_input = st.number_input("Refund Conversion %", value=70)
                m_conv = m_conv_input / 100

        submit_calc = st.form_submit_button("📊 CALCULATE HEDGE", type="primary", use_container_width=True)

    if submit_calc:
        # AUTOMATIC CONVERSION TO NEGATIVE
        m_h_price = -abs(h_input)
        
        # American to Multiplier Logic
        ms_m = (m_s_price / 100) if m_s_price > 0 else (100 / abs(m_s_price))
        mh_m = (m_h_price / 100) if m_h_price > 0 else (100 / abs(m_h_price))

        if m_promo == "Profit Boost (%)":
            boost_f = 1 + (m_boost / 100)
            boosted_ms_m = ms_m * boost_f
            m_hedge = (m_wager * (1 + boosted_ms_m)) / (1 + mh_m)
            m_profit = (m_wager * boosted_ms_m) - m_hedge
        elif m_promo == "Bonus Bet (SNR)":
            m_hedge = (m_wager * ms_m) / (1 + mh_m)
            m_profit = (m_wager * ms_m) - m_hedge
        else: # No-Sweat
            m_hedge = (m_wager * (ms_m + 1 - m_conv)) / (mh_m + 1 + m_conv)
            m_profit = (m_wager * ms_m) - (m_hedge + (m_wager * (1 - m_conv)))

        st.divider()
        st.info(f"Odds Used: **{m_s_price}** (Underdog) vs **{m_h_price}** (Favorite)")
        
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric("Hedge Amount", f"${m_hedge:.2f}")
        res_c2.metric("Net Profit", f"${m_profit:.2f}")
        res_c3.metric("ROI", f"{((m_profit/m_wager)*100):.1f}%")

        if m_profit > 0:
            st.success(f"✅ Place **${m_hedge:.2f}** on the Favorite side.")
