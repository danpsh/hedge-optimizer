import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- MATH HELPERS ---
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# CLEAN UI: High-contrast cards, no dark backgrounds on results
st.markdown("""
    <style>
    div[data-testid="stExpander"] { 
        background-color: #ffffff !important; 
        color: #000000 !important;
        border: 1px solid #d1d5db !important; 
        border-radius: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stMetric { 
        background-color: #f3f4f6; 
        border: 1px solid #d1d5db; 
        padding: 15px; 
        border-radius: 10px; 
    }
    p, span, label { font-family: 'Inter', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Arbitrage Edge")
    st.markdown("---")
    quota_placeholder = st.empty()
    st.success("Big 5 Strategy Active")

# --- USER INPUT ---
with st.form("input_panel"):
    col1, col2 = st.columns(2)
    with col1:
        promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"])
        source_book_display = st.selectbox("Source Book", ["DraftKings", "FanDuel", "Caesars", "Fanatics", "theScore Bet"])
        
        # Comprehensive key mapping for Caesars
        book_map = {
            "DraftKings": ["draftkings"],
            "FanDuel": ["fanduel"],
            "Caesars": ["williamhill_us", "caesars", "caesars_legal"], 
            "Fanatics": ["fanatics"],
            "theScore Bet": ["thescore"]
        }
        source_keys = book_map[source_book_display]

    with col2:
        sport_cat = st.selectbox("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB"])
        time_horizon = st.radio("Time Horizon", ["Today & Tomorrow", "Full Slate"], horizontal=True)
            
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        max_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
    with c2:
        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost (%)", min_value=1, value=50)
        else:
            boost_val = 0
            st.caption("Auto-optimizing for max conversion.")

    run_scan = st.form_submit_button("🔥 RUN DEEP SCAN")

# --- DATA PROCESSING ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key in Secrets!")
    else:
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"]
        }
        
        all_opps = []
        now = datetime.now(timezone.utc)
        tomorrow_midnight = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)

        with st.spinner(f"Scanning for {source_book_display} matches..."):
            for sport_key in sport_map[sport_cat]:
                # Pull odds for all US books to ensure we find a hedge
                url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    remaining = res.headers.get('x-requests-remaining', 'N/A')
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{remaining}]")

                    if res.status_code == 200:
                        data = res.json()
                        for game in data:
                            start_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if start_time <= now: continue
                            if time_horizon == "Today & Tomorrow" and start_time > tomorrow_midnight: continue
                            
                            source_outcomes = []
                            other_outcomes = []
                            
                            # Sort books into Source and Potential Hedges
                            for book in game['bookmakers']:
                                if book['key'] in source_keys:
                                    for market in book['markets']:
                                        if market['key'] == 'h2h':
                                            source_outcomes = market['outcomes']
                                else:
                                    # Collect hedge from ANY other book for better results
                                    for market in book['markets']:
                                        if market['key'] == 'h2h':
                                            for o in market['outcomes']:
                                                other_outcomes.append({'book': book['title'], 'name': o['name'], 'price': o['price']})

                            # If we found your source book for this game, run the math
                            if source_outcomes:
                                for s_opt in source_outcomes:
                                    opp_team = [t for t in [game['home_team'], game['away_team']] if t != s_opt['name']][0]
                                    possible_hedges = [h for h in other_outcomes if h['name'] == opp_team]
                                    
                                    if possible_hedges:
                                        best_hedge = max(possible_hedges, key=lambda x: x['price'])
                                        ds, dh = american_to_decimal(s_opt['price']), american_to_decimal(best_hedge['price'])

                                        if promo_type == "Profit Boost (%)":
                                            total_ret = (max_wager * (ds - 1) * (1 + (boost_val / 100))) + max_wager
                                            hedge_needed = total_ret / dh
                                            profit = total_ret - (max_wager + hedge_needed)
                                        elif promo_type == "Bonus Bet (SNR)":
                                            total_ret = max_wager * (ds - 1)
                                            hedge_needed = total_ret / dh
                                            profit = total_ret - hedge_needed
                                        else: # No-Sweat
                                            refund_val = max_wager * 0.70
                                            total_ret = max_wager * ds
                                            hedge_needed = (total_ret - refund_val) / dh
                                            profit = total_ret - (max_wager + hedge_needed)

                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start": start_time.strftime("%m/%d | %I:%M %p"),
                                            "profit": profit, "hedge": hedge_needed,
                                            "s_book": source_book_display, "s_team": s_opt['name'], "s_price": s_opt['price'],
                                            "h_book": best_hedge['book'], "h_team": best_hedge['name'], "h_price": best_hedge['price']
                                        })
                except: continue

        if all_opps:
            st.markdown("### 🏆 Top 5 Opportunities")
            # Filter out duplicates and sort
            sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)
            for i, op in enumerate(sorted_opps[:5]):
                with st.expander(f"RANK {i+1} | {op['start']} | ${op['profit']:.2f} | {op['game']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**PROMO: {op['s_book']}**")
                        st.markdown(f"✅ Bet **${max_wager:.2f}** on **{op['s_team']}**")
                        st.code(f"Odds: {op['s_price']}")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        st.markdown(f"🛡️ Bet **${op['hedge']:.2f}** on **{op['h_team']}**")
                        st.code(f"Odds: {op['h_price']}")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
        else:
            st.warning(f"No results found for {source_book_display}. This usually means Caesars hasn't posted Moneyline odds for these games yet.")
