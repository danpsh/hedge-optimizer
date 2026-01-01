import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# --- LIGHT TECH THEME (White Background) ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    
    /* Clean White Cards */
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"]:hover {
        border: 1px solid #00ff88;
        box-shadow: 0 4px 12px rgba(0, 255, 136, 0.15);
    }

    /* Metric Styling */
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; 
        font-family: 'Courier New', monospace; 
        font-weight: 800;
    }
    
    /* Input Containers */
    div.row-widget.stRadio > div {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
    }

    /* Stealth EXECUTE Button */
    .stButton>button {
        background-color: #1e1e1e;
        color: #00ff88;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #00ff88;
        color: #1e1e1e;
    }

    /* Clean Text Inputs (Hiding Chrome/Safari arrows if number type used) */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("📟 ARB TERMINAL")
    st.info("Source Logic: FanDuel & DraftKings Only")
    quota_placeholder = st.empty()

# --- INPUT AREA (Main Scan) ---
with st.container():
    with st.form("input_panel"):
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"], horizontal=True)
        with col2:
            # Added Caesars to the radio options
            source_book_display = st.radio("Source Book", ["DraftKings", "FanDuel", "Caesars"], horizontal=True)
            
            # Map display name to API keys
            source_map = {
                "DraftKings": "draftkings",
                "FanDuel": "fanduel",
                "Caesars": "williamhill_us"
            }
            source_book = source_map[source_book_display]

        st.divider()
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB", "NCAAF"], horizontal=True)
        with col4:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")

        if promo_type == "Profit Boost (%)":
            boost_val_raw = st.text_input("Boost (%)", value="50")
        else:
            boost_val_raw = "0"

        run_scan = st.form_submit_button("EXECUTE LIVE SCAN")
        
# --- SCAN LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key!")
    else:
        try:
            max_wager = float(max_wager_raw)
            boost_val = float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab", "americanfootball_ncaaf"],
            "NBA": ["basketball_nba"], 
            "NFL": ["americanfootball_nfl"], 
            "NHL": ["icehockey_nhl"], 
            "NCAAB": ["basketball_ncaab"],
            "NCAAF": ["americanfootball_ncaaf"]
        }
        
        # Ensure williamhill_us is in the master list
        BOOK_LIST = "draftkings,fanduel,williamhill_us,fanatics,espnbet,betmgm"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner(f"Scanning {sport_cat} using {source_book_display} as Source..."):
            sports_to_scan = sport_map.get(sport_cat, [])
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    quota_placeholder.markdown(f"**Quota:** :green[{res.headers.get('x-requests-remaining', 'N/A')}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            # ... (Rest of the logic remains the same)
        }
        
        # Define allowed hedge books
        BOOK_LIST = "draftkings,fanduel,williamhill_us,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner(f"Intercepting {sport_cat} data..."):
            sports_to_scan = sport_map.get(sport_cat, [])
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{res.headers.get('x-requests-remaining', 'N/A')}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            commence_time_utc = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if commence_time_utc <= now_utc: continue 
                            cst_time = commence_time_utc - timedelta(hours=6)

                            source_odds, hedge_odds = [], []
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        if book['key'] == source_book: source_odds.append(entry)
                                        else: hedge_odds.append(entry)

                            for s in source_odds:
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                                best_h = max([h for h in hedge_odds if h['team'] == opp_team], key=lambda x: x['price'], default=None)
                                
                                if best_h:
                                    s_price, h_price = s['price'], best_h['price']
                                    s_m = (s_price / 100) if s_price > 0 else (100 / abs(s_price))
                                    h_m = (h_price / 100) if h_price > 0 else (100 / abs(h_price))

                                    if promo_type == "Profit Boost (%)":
                                        b_factor = 1 + (boost_val / 100)
                                        boosted_s_m = s_m * b_factor
                                        raw_h = (max_wager * (1 + boosted_s_m)) / (1 + h_m)
                                        h_needed = float(round(raw_h))
                                        profit = min(((max_wager * boosted_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                        rating = profit

                                    elif promo_type == "Bonus Bet (SNR)":
                                        raw_h = (max_wager * s_m) / (1 + h_m)
                                        h_needed = float(round(raw_h))
                                        profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                        rating = (profit / max_wager) * 100

                                    else: # No-Sweat
                                        ref_c = 0.70
                                        raw_h = (max_wager * (s_m + 1 - ref_c)) / (h_m + 1 + ref_c)
                                        h_needed = float(round(raw_h))
                                        p_s = (max_wager * s_m) - h_needed
                                        p_h = (h_needed * h_m) + (max_wager * ref_c) - max_wager
                                        profit = min(p_s, p_h)
                                        rating = (profit / max_wager) * 100

                                    if profit > 0:
                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start_cst": cst_time.strftime("%m/%d %I:%M %p"),
                                            "profit": profit, "hedge": h_needed, "rating": rating,
                                            "s_team": s['team'], "s_book": s['book'], "s_price": s_price,
                                            "h_team": best_h['team'], "h_book": best_h['book'], "h_price": h_price
                                        })
                except: continue

        st.markdown("### 🏆 Top Scanned Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)

        if not sorted_opps:
            st.warning("No high-value matches found currently.")
        else:
            for i, op in enumerate(sorted_opps[:10]):
                with st.expander(f"RANK {i+1} | {op['start_cst']} | +${op['profit']:.2f}"):
                    st.write(f"**{op['game']}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.caption("SOURCE BOOK")
                        st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                        st.caption(f"Book: {op['s_book']}")
                    with c2:
                        st.caption("STEALTH HEDGE (Rounded)")
                        st.success(f"Bet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                        st.caption(f"Book: {op['h_book']}")
                    with c3:
                        st.metric("Guaranteed Profit", f"${op['profit']:.2f}")
                        st.caption(f"Rating: {op['rating']:.1f}%")

# --- STANDALONE MANUAL CALCULATOR ---
st.write("---")
st.subheader("🧮 Manual Multi-Strategy Calculator")

with st.expander("Open Manual Calculator", expanded=True):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"], horizontal=True)
        m_col1, m_col2 = st.columns(2)
        
        with m_col1:
            m_s_price_raw = st.text_input("Source Odds (Underdog) e.g. 250", value="250")
            m_wager_raw = st.text_input("Wager Amount ($)", value="50.0")
            if m_promo == "Profit Boost (%)":
                m_boost_raw = st.text_input("Boost %", value="50")
        
        with m_col2:
            h_input_raw = st.text_input("Hedge Odds (Favorite) e.g. 300", value="300")
            if m_promo == "No-Sweat Bet":
                m_conv_raw = st.text_input("Refund Conversion %", value="70")

        submit_calc = st.form_submit_button("📊 CALCULATE HEDGE", type="primary", use_container_width=True)

    if submit_calc:
        try:
            m_s_p = float(m_s_price_raw)
            m_w = float(m_wager_raw)
            h_i = float(h_input_raw)
            m_h_p = -abs(h_i) # Auto-negative Favorite
            
            ms_m = (m_s_p / 100) if m_s_p > 0 else (100 / abs(m_s_p))
            mh_m = (m_h_p / 100) if m_h_p > 0 else (100 / abs(m_h_p))

            if m_promo == "Profit Boost (%)":
                m_b = float(m_boost_raw)
                boost_f = 1 + (m_b / 100)
                boosted_ms_m = ms_m * boost_f
                m_hedge = (m_w * (1 + boosted_ms_m)) / (1 + mh_m)
                m_profit = (m_w * boosted_ms_m) - m_hedge
            elif m_promo == "Bonus Bet (SNR)":
                m_hedge = (m_w * ms_m) / (1 + mh_m)
                m_profit = (m_w * ms_m) - m_hedge
            else: # No-Sweat
                m_c = float(m_conv_raw) / 100
                m_hedge = (m_w * (ms_m + 1 - m_c)) / (mh_m + 1 + m_c)
                m_profit = (m_w * ms_m) - (m_hedge + (m_w * (1 - m_c)))

            st.divider()
            st.info(f"Odds Used: **{m_s_p:+.0f}** vs **{m_h_p:+.0f}**")
            res_c1, res_c2, res_c3 = st.columns(3)
            res_c1.metric("Hedge Amount", f"${m_hedge:.2f}")
            res_c2.metric("Net Profit", f"${m_profit:.2f}")
            res_c3.metric("ROI", f"{((m_profit/m_w)*100):.1f}%")
            
        except:
            st.error("⚠️ Syntax Error: Please enter valid numbers.")

