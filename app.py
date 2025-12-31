import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- MATH HELPERS ---
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# Custom CSS for the "Institutional" look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stExpander"] { background-color: #161b22 !important; border: 1px solid #30363d !important; border-radius: 8px !important; }
    .stMetric { background-color: #1c2128; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: SYSTEM MONITOR ---
with st.sidebar:
    st.title("🛡️ Arbitrage Edge")
    st.markdown("---")
    st.subheader("System Monitor")
    
    # Placeholder for Quota - This updates after the first scan
    quota_placeholder = st.empty()
    st.info("Status: API Connection Live")
    st.markdown("---")
    st.caption("v2.0.1 | Data: The Odds API")

# --- STEP 1: CONTROL CENTER ---
st.title("📈 Control Center")
with st.container():
    with st.form("control_panel"):
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.selectbox("Promo Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"])
            source_book = st.selectbox("Source Book (Where is the promo?)", ["draftkings", "fanduel", "caesars", "betmgm", "pointsbet", "williamhill_us"])
        
        with col2:
            sport_cat = st.selectbox("Sport Category", ["All Sports", "NBA", "NFL", "NHL", "NCAAB"])
            time_horizon = st.radio("Time Horizon", ["Next 48 Hours", "Full Slate"], horizontal=True)
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            max_wager = st.number_input("Promo Wager Amount ($)", min_value=1.0, value=50.0)
        with c2:
            if promo_type == "Profit Boost (%)":
                boost_val = st.number_input("Boost Percentage (%)", min_value=1, value=50)
            else:
                boost_val = 0
                st.write("Math optimized for max conversion.")

        run_scan = st.form_submit_button("🔥 RUN GLOBAL SCAN")

# --- STEP 2: SCANNING & LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key in Streamlit Secrets!")
    else:
        # Map friendly names to API keys
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"]
        }
        
        TARGET_BOOKS = "draftkings,fanduel,caesars,betmgm,pointsbet,williamhill_us"
        all_opps = []
        now = datetime.now(timezone.utc)

        with st.spinner(f"Scanning {sport_cat} for {promo_type} opportunities..."):
            for sport in sport_map[sport_cat]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
                
                res = requests.get(url, params=params)
                
                # Update Quota in Sidebar
                remaining = res.headers.get('x-requests-remaining', 'N/A')
                color = "red" if (remaining != 'N/A' and int(remaining) < 50) else "green"
                quota_placeholder.markdown(f"**Quota Remaining:** :{color}[{remaining}]")

                if res.status_code == 200:
                    games = res.json()
                    for game in games:
                        # Time Filtering
                        start_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if start_time <= now: continue
                        if time_horizon == "Next 48 Hours" and start_time > (now + timedelta(hours=48)): continue
                        
                        # Separate Source Book odds from Hedge Book odds
                        source_odds = []
                        hedge_odds = []
                        
                        for book in game['bookmakers']:
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book': book['title'], 'book_id': book['key'], 'team': o['name'], 'price': o['price']}
                                    if book['key'] == source_book:
                                        source_odds.append(entry)
                                    else:
                                        hedge_odds.append(entry)

                        # Match Source vs All Hedges
                        for s in source_odds:
                            # Find the opposing team in the hedge list
                            opposing_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                            possible_hedges = [h for h in hedge_odds if h['team'] == opposing_team]
                            
                            for h in possible_hedges:
                                ds, dh = american_to_decimal(s['price']), american_to_decimal(h['price'])
                                
                                if promo_type == "Profit Boost (%)":
                                    total_ret = (max_wager * (ds - 1) * (1 + (boost_val / 100))) + max_wager
                                    hedge_needed = total_ret / dh
                                    profit = total_ret - (max_wager + hedge_needed)
                                elif promo_type == "Bonus Bet (SNR)":
                                    total_ret = max_wager * (ds - 1)
                                    hedge_needed = total_ret / dh
                                    profit = total_ret - hedge_needed
                                else: # No Sweat
                                    refund_val = max_wager * 0.70
                                    total_ret = max_wager * ds
                                    hedge_needed = (total_ret - refund_val) / dh
                                    profit = total_ret - (max_wager + hedge_needed)

                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "start": start_time.strftime("%m/%d | %I:%M %p"),
                                    "profit": profit, "hedge": hedge_needed,
                                    "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                    "h_team": h['team'], "h_book": h['book'], "h_price": h['price']
                                })

        # Display Top 5
        st.markdown("### 🏆 Top 5 Market Edges")
        sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)

        if not sorted_opps:
            st.warning("No profitable matches found for this specific book/timeframe.")
        else:
            for i, op in enumerate(sorted_opps[:5]):
                header = f"RANK {i+1} | {op['start']} | ${op['profit']:.2f} PROFIT | {op['game']}"
                with st.expander(header):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**SOURCE: {op['s_book']}**")
                        st.info(f"Bet ${max_wager:.2f} on {op['s_team']} @ {op['s_price']}")
                    with c2:
                        st.write(f"**HEDGE: {op['h_book']}**")
                        st.success(f"Bet ${op['hedge']:.2f} on {op['h_team']} @ {op['h_price']}")
                    with c3:
                        st.metric("Net Gain", f"${op['profit']:.2f}")
