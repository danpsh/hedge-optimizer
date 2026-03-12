import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- TECH THEME CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
    }
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; font-family: 'Courier New', monospace; font-weight: 800;
    }
    .stButton>button {
        background-color: #1e1e1e; color: #00ff88; border: none; border-radius: 8px; font-weight: bold;
    }
    .stCheckbox { margin-bottom: -10px; white-space: nowrap; }
    </style>
    """, unsafe_allow_html=True)

# Helper for American Odds Conversion
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# --- HEADER AREA ---
st.title("📟 Arb Terminal")
quota_placeholder = st.empty()
quota_placeholder.markdown("**Quota:** Not scanned yet")

# --- MAIN SCANNER INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        
        book_map = {
            "DraftKings": "draftkings",
            "FanDuel": "fanduel",
            "BetMGM": "betmgm",
            "theScore / ESPN": "espnbet",
            "All Books": "allbooks"
        }

        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book_display = st.radio("Source Book (Promo)", ["DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            source_book = book_map[source_book_display]
        with col_hedge:
            hedge_book_display = st.radio("Hedge Book (Filter)", ["All Books", "DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            hedge_filter = book_map[hedge_book_display]

        st.divider()
        st.write("**Select Sports to Scan:**")
        sports_map = {
            "NBA": "basketball_nba", "NCAAB": "basketball_ncaab", 
            "NHL": "icehockey_nhl", "Boxing": "boxing_boxing", "MMA": "mma_mixed_martial_arts" 
        }
        sport_labels = list(sports_map.keys())
        selected_sports = []
        
        sport_cols = st.columns(len(sport_labels))
        for i, label in enumerate(sport_labels):
            with sport_cols[i]:
                if st.checkbox(label, key=f"cb_{label}"):
                    selected_sports.append(sports_map[label])

        st.divider()
        col_w, col_b = st.columns([1, 1])
        with col_w:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")
        with col_b:
            boost_val_raw = st.text_input("Boost (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
            
        run_scan = st.form_submit_button("Run Real-Time Optimizer", use_container_width=True)

# --- SCAN LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key! Please add ODDS_API_KEY to your Streamlit secrets.")
    elif not selected_sports:
        st.warning("Please select at least one sport.")
    else:
        try:
            max_wager = float(max_wager_raw)
            boost_val = float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,williamhill_us,caesars,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner("Scanning live markets..."):
            for sport in selected_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                res = requests.get(url, params=params)
                
                if res.status_code == 200:
                    quota_placeholder.markdown(f"**Quota Remaining:** {res.headers.get('x-requests-remaining', 'N/A')}")
                    games = res.json()
                    for game in games:
                        commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if commence_time <= now_utc: continue 
                        
                        source_odds, hedge_odds = [], []
                        for book in game['bookmakers']:
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book_name': book['title'], 'team': o['name'], 'price': o['price']}
                                    if book['key'] == source_book: source_odds.append(entry)
                                    if hedge_filter == "allbooks" or book['key'] == hedge_filter: hedge_odds.append(entry)

                        for s in source_odds:
                            opp_team = next((t for t in [game['home_team'], game['away_team']] if t != s['team']), None)
                            eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                            if not eligible_hedges: continue
                            
                            best_h = max(eligible_hedges, key=lambda x: x['price'])
                            s_m, h_m = get_multiplier(s['price']), get_multiplier(best_h['price'])

                            if promo_type == "Profit Boost (%)":
                                b_s_m = s_m * (1 + (boost_val / 100))
                                h_needed = round((max_wager * (1 + b_s_m)) / (1 + h_m))
                                profit = min(((max_wager * b_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                rating = profit
                            elif promo_type == "Bonus Bet":
                                h_needed = round((max_wager * s_m) / (1 + h_m))
                                profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                rating = (profit / max_wager) * 100
                            else: # No-Sweat
                                mc = 0.70 
                                h_needed = round((max_wager * (s_m + (1 - mc))) / (h_m + 1))
                                profit = min(((max_wager * s_m) - h_needed), ((h_needed * h_m) + (max_wager * mc) - max_wager))
                                rating = (profit / max_wager) * 100

                            if profit > -5.0:
                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "sport": sport.split('_')[-1].upper(),
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                    "profit": profit, "hedge": h_needed, "rating": rating,
                                    "s_team": s['team'], "s_book": s['book_name'], "s_price": s['price'],
                                    "h_team": best_h['team'], "h_book": best_h['book_name'], "h_price": best_h['price']
                                })

        st.write("### Top Opportunities")
        top_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)[:10]
        for i, op in enumerate(top_opps):
            with st.expander(f"Rank {i+1} | {op['sport']} | Profit: ${op['profit']:.2f} | Hedge: ${op['hedge']:.0f}"):
                c1, c2, c3 = st.columns(3)
                c1.info(f"**{op['s_book']}**\n\nBet ${max_wager} on {op['s_team']} @ {op['s_price']:+}")
                c2.success(f"**{op['h_book']}**\n\nBet ${op['hedge']} on {op['h_team']} @ {op['h_price']:+}")
                c3.metric("Net Profit", f"${op['profit']:.2f}")

# --- NEW: CROSS-BOOK PROMO OPTIMIZER ---
st.write("---")
st.subheader("🔄 Multi-Promo Optimizer")
with st.expander("Use Different Promos on Two Different Books", expanded=True):
    with st.form("cross_book_form"):
        L, R = st.columns(2)
        with L:
            st.markdown("### Side A")
            strat_a = st.selectbox("Type A", ["Cash / Boost", "Bonus Bet", "No-Sweat"], key="sa")
            odds_a = st.number_input("Odds A", value=150, key="oa")
            wager_a = st.number_input("Wager A ($)", value=50.0, key="wa")
            boost_a = st.number_input("Boost A %", value=0, key="ba")
            refund_a = st.slider("Refund A % (No-Sweat)", 0, 100, 70)

        with R:
            st.markdown("### Side B")
            strat_b = st.selectbox("Type B", ["Cash / Boost", "Bonus Bet", "No-Sweat"], key="sb")
            odds_b = st.number_input("Odds B", value=-180, key="ob")
            boost_b = st.number_input("Boost B %", value=0, key="bb")
            refund_b = st.slider("Refund B % (No-Sweat)", 0, 100, 70)
        
        round_bet = st.checkbox("Round Hedge to Nearest $5 (Better for Account Health)", value=True)

        if st.form_submit_button("Optimize Both Sides", use_container_width=True):
            m_a, m_b = get_multiplier(odds_a), get_multiplier(odds_b)
            
            # Logic: Calculate Net Winning/Loss for Side A
            if strat_a == "Cash / Boost":
                win_a = wager_a * m_a * (1 + boost_a/100)
                loss_a = -wager_a
            elif strat_a == "Bonus Bet":
                win_a = wager_a * m_a
                loss_a = 0
            else: # No-Sweat
                win_a = wager_a * m_a
                loss_a = -wager_a * (1 - (refund_a/100))

            # Solve for Wager B to equalize outcomes
            if strat_b == "Cash / Boost":
                wager_b = (win_a - loss_a) / (m_b * (1 + boost_b/100) + 1)
            elif strat_b == "Bonus Bet":
                wager_b = (win_a - loss_a) / m_b
            else: # No-Sweat
                wager_b = (win_a - loss_a) / (m_b + (1 - refund_b/100))

            if round_bet: wager_b = 5 * round(wager_b / 5)

            # Scenario Calculation
            profit_a_wins = win_a - (wager_b if strat_b != "Bonus Bet" else 0)
            if strat_b == "No-Sweat": profit_a_wins = win_a - (wager_b * (1 - refund_b/100))
            
            profit_b_wins = (wager_b * m_b * (1 + boost_b/100 if strat_b=="Cash / Boost" else 1)) + loss_a

            st.divider()
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Bet on Side B", f"${wager_b:.2f}")
            rc2.metric("Avg Profit", f"${(profit_a_wins + profit_b_wins)/2:.2f}")
            rc3.metric("ROI", f"{(((profit_a_wins + profit_b_wins)/2)/wager_a*100):.1f}%")
            st.caption(f"If A wins: ${profit_a_wins:.2f} | If B wins: ${profit_b_wins:.2f}")
