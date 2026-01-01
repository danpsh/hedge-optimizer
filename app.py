import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

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
    st.title("Arbitrage Edge")
    st.info("Source: FD & DK Only")
    quota_placeholder = st.empty()

# --- UPDATE THE SPORT MAP IN THE LOGIC SECTION ---
# Make sure to replace your existing sport_map with this one:
sport_map = {
    "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab", "americanfootball_ncaaf"],
    "NBA": ["basketball_nba"], 
    "NFL": ["americanfootball_nfl"], 
    "NHL": ["icehockey_nhl"], 
    "NCAAB": ["basketball_ncaab"],
    "NCAAF": ["americanfootball_ncaaf"]


# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        # First row for Strategy and Source Book
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.radio(
                "Strategy", 
                ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"],
                horizontal=True
            )
        with col2:
            source_book_display = st.radio(
                "Source Book", 
                ["DraftKings", "FanDuel"], 
                horizontal=True
            )
            source_book = source_book_display.lower()

        # Second row for Sport and Wager
        st.divider()
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio(
                "Sport", 
                ["All Sports", "NBA", "NFL", "NHL", "NCAAB", "NCAAF"],
                horizontal=True
            )
        with col4:
            max_wager = st.number_input("Wager ($)", min_value=1.0, value=50.0)

        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost (%)", min_value=1, value=50)
        else:
            boost_val = 0

        run_scan = st.form_submit_button("Calculate")



# --- DATA & LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key! Please add ODDS_API_KEY to your secrets.")
    else:
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"]
        }
        
        BOOK_LIST = "draftkings,fanduel,caesars,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner(f"Scanning {sport_cat}..."):
            for sport in sport_map[sport_cat]:
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
                                    s_price = s['price']
                                    h_price = best_h['price']

                                    # --- MATH USING AMERICAN ODDS DIRECTLY ---
                                    # Calculate Multipliers (Profit per $1 wagered)
                                    s_mult = (s_price / 100) if s_price > 0 else (100 / abs(s_price))
                                    h_mult = (h_price / 100) if h_price > 0 else (100 / abs(h_price))

                                    if promo_type == "Profit Boost (%)":
                                        boost_factor = 1 + (boost_val / 100)
                                        boosted_s_mult = s_mult * boost_factor
                                        # Hedge to equalize profit: W1 * (1 + S_boosted) / (1 + H)
                                        hedge_needed = (max_wager * (1 + boosted_s_mult)) / (1 + h_mult)
                                        profit = (max_wager * boosted_s_mult) - hedge_needed
                                        rating = profit

                                    elif promo_type == "Bonus Bet (SNR)":
                                        # Profit = Winnings only (Stake not returned)
                                        # Hedge = Winnings / (1 + H_mult)
                                        hedge_needed = (max_wager * s_mult) / (1 + h_mult)
                                        profit = (max_wager * s_mult) - hedge_needed
                                        rating = (profit / max_wager) * 100

                                    else: # No-Sweat Bet
                                        # Assumes 70% conversion of the returned bonus bet
                                        ref_conv = 0.70
                                        # Hedge = W1 * (S_mult + 1 - Ref) / (H_mult + 1 + Ref)
                                        hedge_needed = (max_wager * (s_mult + 1 - ref_conv)) / (h_mult + 1 + ref_conv)
                                        profit = (max_wager * s_mult) - (hedge_needed + (max_wager * (1 - ref_conv)))
                                        rating = (profit / max_wager) * 100

                                    if profit > 0:
                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start_cst": cst_time.strftime("%m/%d %I:%M %p"),
                                            "profit": profit, "hedge": hedge_needed, "rating": rating,
                                            "s_team": s['team'], "s_book": s['book'], "s_price": s_price,
                                            "h_team": best_h['team'], "h_book": best_h['book'], "h_price": h_price
                                        })
                except Exception as e:
                    continue

        st.markdown("### 🏆 Top Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)

        if not sorted_opps:
            st.warning("No profitable future matches found.")
        else:
            for i, op in enumerate(sorted_opps[:10]):
                with st.expander(f"RANK {i+1} | {op['start_cst']} | ${op['profit']:.2f} Profit"):
                    st.write(f"**{op['game']}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**PROMO: {op['s_book']}**")
                        s_sign = "+" if op['s_price'] > 0 else ""
                        st.info(f"Bet **${max_wager:.2f}** on {op['s_team']} @ **{s_sign}{op['s_price']}**")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        h_sign = "+" if op['h_price'] > 0 else ""
                        st.success(f"Bet **${op['hedge']:.2f}** on {op['h_team']} @ **{h_sign}{op['h_price']}**")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
                        st.caption(f"Rating/Conversion: {op['rating']:.1f}%")






