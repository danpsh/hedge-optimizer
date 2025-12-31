import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- MATH HELPERS ---
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# Simplified CSS: Removed the dark backgrounds for expanders and metrics
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    /* Removed custom background-color for data-testid="stExpander" */
    .stMetric { padding: 10px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Arbitrage Edge")
    st.markdown("---")
    st.subheader("System Monitor")
    quota_placeholder = st.empty()
    st.info("Status: Source Books Filtered")
    st.caption("Monitoring: FanDuel & DraftKings")

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"])
            # Filtered source books per your instructions
            source_book_display = st.selectbox("Source Book", ["DraftKings", "FanDuel"])
            
            book_map = {"DraftKings": "draftkings", "FanDuel": "fanduel"}
            source_book = book_map[source_book_display]

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
                st.write("Optimizing for maximum conversion.")

        run_scan = st.form_submit_button("🔥 RUN GLOBAL SCAN")

# --- DATA & LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key!")
    else:
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"]
        }
        
        # Kept the API call broad to find the best hedge across all books, 
        # while the source book is restricted to DK/FD
        BOOK_LIST = "draftkings,fanduel,caesars,fanatics,thescore"
        all_opps = []
        now = datetime.now(timezone.utc)
        tomorrow_midnight = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)

        with st.spinner(f"Analyzing {sport_cat}..."):
            for sport in sport_map[sport_cat]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST}
                
                try:
                    res = requests.get(url, params=params)
                    remaining = res.headers.get('x-requests-remaining', 'N/A')
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{remaining}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            start_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if start_time <= now: continue
                            if time_horizon == "Today & Tomorrow" and start_time > tomorrow_midnight: continue
                            
                            source_odds, hedge_odds = [], []
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        if book['key'] == source_book:
                                            source_odds.append(entry)
                                        else:
                                            hedge_odds.append(entry)

                            for s in source_odds:
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                                possible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                                
                                for h in possible_hedges:
                                    ds, dh = american_to_decimal(s['price']), american_to_decimal(h['price'])
                                    
                                    if promo_type == "Profit Boost (%)":
                                        # New Payout = Stake + (Profit * Boost)
                                        boost_decimal = 1 + (boost_val / 100)
                                        total_ret = max_wager * (1 + (ds - 1) * boost_decimal)
                                        hedge_needed = total_ret / dh
                                        profit = total_ret - (max_wager + hedge_needed)

                                    elif promo_type == "Bonus Bet (SNR)":
                                        # Stake is not returned
                                        total_ret = max_wager * (ds - 1)
                                        hedge_needed = total_ret / dh
                                        profit = total_ret - hedge_needed

                                    else: # No-Sweat Bet
                                        # Logic: Equalize profit for (Win) vs (Loss + Bonus Bet Refund)
                                        # Assume 70% conversion on the refund
                                        refund_rate = 0.70
                                        # Formula: Hedge = (Stake * (DecimalSource + RefundRate - 1)) / (DecimalHedge + RefundRate)
                                        hedge_needed = (max_wager * (ds + refund_rate - 1)) / (dh + refund_rate)
                                        profit = (max_wager * ds) - (max_wager + hedge_needed)

                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "start": start_time.strftime("%m/%d | %I:%M %p"),
                                        "profit": profit, "hedge": hedge_needed,
                                        "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                        "h_team": h['team'], "h_book": h['book'], "h_price": h['price']
                                    })
                except: continue

        st.markdown("### 🏆 Top 5 Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)

        if not sorted_opps:
            st.warning("No matches found.")
        else:
            for i, op in enumerate(sorted_opps[:5]):
                header = f"RANK {i+1} | {op['start']} | ${op['profit']:.2f} | {op['game']}"
                with st.expander(header):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**PROMO: {op['s_book']}**")
                        st.info(f"Bet ${max_wager:.2f} on {op['s_team']} @ {op['s_price']}")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        st.success(f"Bet ${op['hedge']:.2f} on {op['h_team']} @ {op['h_price']}")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
