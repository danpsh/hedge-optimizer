import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- MATH HELPERS ---
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# CLEAN UI STYLING: High-contrast white cards, no dark backgrounds
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stExpander"] { 
        background-color: #ffffff !important; 
        border: 1px solid #dee2e6 !important; 
        border-radius: 12px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TOP ROW: API COUNTER (GAS GAUGE) ---
if 'remaining_requests' not in st.session_state:
    st.session_state.remaining_requests = "---"

col_left, col_mid, col_right = st.columns([1, 2, 1])
with col_mid:
    st.metric(label="📊 API CREDITS REMAINING", value=st.session_state.remaining_requests)

st.divider()

# --- USER INPUT AREA ---
with st.form("input_panel"):
    col1, col2 = st.columns(2)
    with col1:
        promo_type = st.selectbox("Strategy", ["No-Sweat Bet", "Profit Boost (%)", "Bonus Bet (SNR)"])
        source_book_display = st.selectbox("Source Book", ["FanDuel", "DraftKings"])
        
        # Book Key Mapping
        book_map = {
            "DraftKings": "draftkings",
            "FanDuel": "fanduel",
            "Caesars": ["williamhill_us", "caesars"],
            "Fanatics": "fanatics",
            "theScore Bet": "thescore"
        }
        source_key = book_map[source_book_display]

    with col2:
        sport_cat = st.selectbox("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB"])
        time_horizon = st.radio("Time Horizon", ["Today & Tomorrow", "Full Slate"], horizontal=True)
            
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        max_wager = st.number_input("Max Wager ($)", min_value=1.0, value=50.0)
    with c2:
        # DYNAMIC UI: Only shows if Profit Boost is selected
        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost (%)", min_value=1, value=50)
        else:
            boost_val = 0
            st.info("💡 Strategy: Max Conversion Mode")

    run_scan = st.form_submit_button("Find Max Value")

# --- DATA PROCESSING ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("API Key not found in Streamlit Secrets.")
    else:
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"]
        }
        
        # Strictly limited to your requested 5 books for both sides
        ALLOWED_HEDGE_KEYS = ["draftkings", "fanduel", "williamhill_us", "caesars", "fanatics", "thescore"]
        
        all_opps = []
        now_utc = datetime.now(timezone.utc)
        cst_offset = timedelta(hours=-6) # CST Adjustment
        tomorrow_midnight_utc = (now_utc + timedelta(days=1)).replace(hour=23, minute=59, second=59)

        with st.spinner("Analyzing Markets..."):
            for sport_key in sport_map[sport_cat]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    st.session_state.remaining_requests = res.headers.get('x-requests-remaining', '---')

                    if res.status_code == 200:
                        data = res.json()
                        for game in data:
                            # 1. TIMEZONE & FILTERING BLOCK
                            start_time_utc = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if start_time_utc <= now_utc: continue
                            if time_horizon == "Today & Tomorrow" and start_time_utc > tomorrow_midnight_utc: continue
                            
                            start_time_cst = start_time_utc + cst_offset
                            
                            source_outcomes = []
                            hedge_outcomes = []
                            
                            for book in game['bookmakers']:
                                # Identify Source Book Odds
                                if book['key'] == source_key:
                                    for market in book['markets']:
                                        if market['key'] == 'h2h': source_outcomes = market['outcomes']
                                
                                # Identify Hedge Odds (MUST be in Big 5)
                                elif book['key'] in ALLOWED_HEDGE_KEYS:
                                    for market in book['markets']:
                                        if market['key'] == 'h2h':
                                            for o in market['outcomes']:
                                                hedge_outcomes.append({'book': book['title'], 'name': o['name'], 'price': o['price']})

                            if source_outcomes and hedge_outcomes:
                                for s_opt in source_outcomes:
                                    opp_team = [t for t in [game['home_team'], game['away_team']] if t != s_opt['name']][0]
                                    possible_hedges = [h in hedge_outcomes if h['name'] == opp_team]
                                    
                                    # Filter for best price among our allowed hedge books
                                    valid_hedges = [h for h in hedge_outcomes if h['name'] == opp_team]
                                    if valid_hedges:
                                        best_hedge = max(valid_hedges, key=lambda x: x['price'])
                                        ds, dh = american_to_decimal(s_opt['price']), american_to_decimal(best_hedge['price'])

                                        # Calculation Logic
                                        if promo_type == "Profit Boost (%)":
                                            total_ret = (max_wager * (ds - 1) * (1 + (boost_val / 100))) + max_wager
                                            hedge_needed = total_ret / dh
                                            profit = total_ret - (max_wager + hedge_needed)
                                        elif promo_type == "Bonus Bet (SNR)":
                                            total_ret = max_wager * (ds - 1)
                                            hedge_needed = total_ret / dh
                                            profit = total_ret - hedge_needed
                                        else: # No-Sweat
                                            refund_val = max_wager * 0.70 # Assumes 70% conversion of bonus
                                            total_ret = max_wager * ds
                                            hedge_needed = (total_ret - refund_val) / dh
                                            profit = total_ret - (max_wager + hedge_needed)

                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start": start_time_cst.strftime("%m/%d | %I:%M %p CST"),
                                            "profit": profit, "hedge": hedge_needed,
                                            "s_book": source_book_display, "s_team": s_opt['name'], "s_price": s_opt['price'],
                                            "h_book": best_hedge['book'], "h_team": best_hedge['name'], "h_price": best_hedge['price']
                                        })
                except: continue

        # --- DISPLAY RESULTS ---
        if all_opps:
            st.markdown("### 🏆 Top 5 Big 5 Matches")
            sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)
            for i, op in enumerate(sorted_opps[:5]):
                with st.expander(f"RANK {i+1} | {op['start']} | ${op['profit']:.2f} | {op['game']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**PROMO: {op['s_book']}**")
                        st.info(f"Bet ${max_wager:.2f} on {op['s_team']} @ {op['s_price']}")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        st.success(f"Bet ${op['hedge']:.2f} on {op['h_team']} @ {op['h_price']}")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
        else:
            st.warning("No Big 5 matches found. Try 'Full Slate' or switch Source Book.")
