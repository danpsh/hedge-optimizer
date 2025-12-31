import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- MATH HELPERS ---
def american_to_decimal(odds):
    """Accurate conversion for American odds to Decimal."""
    if odds > 0: 
        return (odds / 100) + 1
    # Avoid division by zero if odds are somehow 0
    return (100 / max(abs(odds), 1)) + 1

def format_odds(decimal_odds):
    """
    Fixed conversion: Handles heavy favorites correctly to 
    prevent extreme numbers like -9000.
    """
    if decimal_odds >= 2.0:
        return f"+{int(round((decimal_odds - 1) * 100))}"
    else:
        # If decimal is 1.05, this becomes 100 / 0.05 = 2000 -> -2000
        # If it's a massive favorite, we cap/round appropriately
        val = int(round(100 / (decimal_odds - 1)))
        return f"-{val}"

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { padding: 10px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Arbitrage Edge")
    st.info("Source: FD & DK Only")
    quota_placeholder = st.empty()

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"])
            # Restricted to FD and DK per user instructions
            source_book_display = st.selectbox("Source Book", ["DraftKings", "FanDuel"])
            source_book = "draftkings" if source_book_display == "DraftKings" else "fanduel"

        with col2:
            sport_cat = st.selectbox("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB"])
            max_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
            
        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost (%)", min_value=1, value=50)
        else:
            boost_val = 0

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
        
        BOOK_LIST = "draftkings,fanduel,caesars,fanatics,thescore"
        all_opps = []
        now = datetime.now(timezone.utc)

        with st.spinner(f"Scanning for future {sport_cat} games..."):
            for sport in sport_map[sport_cat]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                # We pull American odds directly from the API to avoid conversion glitches
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{res.headers.get('x-requests-remaining', 'N/A')}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if commence_time <= now:
                                continue 

                            source_odds, hedge_odds = [], []
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        # API is now providing American odds directly
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        if book['key'] == source_book: source_odds.append(entry)
                                        else: hedge_odds.append(entry)

                            for s in source_odds:
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                                best_h = max([h for h in hedge_odds if h['team'] == opp_team], key=lambda x: x['price'], default=None)
                                
                                if best_h:
                                    # Convert to decimal ONLY for the internal math
                                    ds, dh = american_to_decimal(s['price']), american_to_decimal(best_h['price'])
                                    
                                    if promo_type == "Profit Boost (%)":
                                        boost_mult = 1 + (boost_val / 100)
                                        boosted_ds = 1 + ((ds - 1) * boost_mult)
                                        hedge_needed = (max_wager * boosted_ds) / dh
                                        profit = (max_wager * boosted_ds) - (max_wager + hedge_needed)
                                        rating = profit 

                                    elif promo_type == "Bonus Bet (SNR)":
                                        hedge_needed = (max_wager * (ds - 1)) / dh
                                        profit = (max_wager * (ds - 1)) - hedge_needed
                                        rating = (profit / max_wager) * 100 

                                    else: # No-Sweat Bet
                                        refund_val = 0.70 
                                        hedge_needed = (max_wager * (ds - refund_val)) / (dh + refund_val)
                                        profit = (max_wager * ds) - (max_wager + hedge_needed)
                                        rating = (profit / max_wager) * 100

                                    # Only show results with realistic profit/conversion
                                    if rating > 0: 
                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start": commence_time.strftime("%m/%d %I:%M %p"),
                                            "profit": profit, "hedge": hedge_needed, "rating": rating,
                                            "s_team": s['team'], "s_book": s['book'], "s_price": s['price'], # Keep raw American
                                            "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                        })
                except: continue

        st.markdown("### 🏆 Top Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)

        if not sorted_opps:
            st.warning("No profitable future matches found.")
        else:
            for i, op in enumerate(sorted_opps[:5]):
                with st.expander(f"RANK {i+1} | {op['start']} | ${op['profit']:.2f} Profit | {op['game']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**PROMO: {op['s_book']}**")
                        # Displaying as simple +200/-300 strings
                        s_prefix = "+" if op['s_price'] > 0 else ""
                        st.info(f"Bet **${max_wager:.2f}** on {op['s_team']} @ **{s_prefix}{op['s_price']}**")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        h_prefix = "+" if op['h_price'] > 0 else ""
                        st.success(f"Bet **${op['hedge']:.2f}** on {op['h_team']} @ **{h_prefix}{op['h_price']}**")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
                        if promo_type != "Profit Boost (%)":
                            st.caption(f"Conversion: {op['rating']:.1f}%")
