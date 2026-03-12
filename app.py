import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="ARB_TERMINAL", layout="wide")

# --- MINIMALIST CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=JetBrains+Mono&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #ffffff; color: #1e1e1e; }
    
    /* Clean metrics */
    [data-testid="stMetricValue"] { 
        font-family: 'JetBrains Mono', monospace; 
        color: #1e1e1e !important; font-size: 1.8rem !important; 
    }
    
    /* Minimal Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 4px;
        border: 1px solid #1e1e1e;
        background-color: transparent;
        color: #1e1e1e;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    
    /* Remove Borders from Expanders */
    div[data-testid="stExpander"] {
        border: none !important;
        border-bottom: 1px solid #eee !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

book_map = {
    "DraftKings": "draftkings", "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet", "BetMGM": "betmgm", "Caeasars": "caesars"
}

sports_map = {
    "NBA": "basketball_nba", "NCAAB": "basketball_ncaab", "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb", "MMA": "mma_mixed_martial_arts"
}

# --- SIDEBAR (Clean Quota) ---
with st.sidebar:
    st.title("SETTINGS")
    api_key = st.text_input("API Key", type="password")
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("Requests Left", st.session_state.api_quota)

# --- MAIN UI ---
st.title("Converter.")
st.caption("Live Promo Arbitrage Engine")

# --- PROMO INPUT ---
if 'promos' not in st.session_state: st.session_state.promos = []

with st.expander("ADD PROMO", expanded=not st.session_state.promos):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        b = st.selectbox("Bookmaker", list(book_map.keys()))
        s = st.selectbox("Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
    with c2:
        w = st.number_input("Wager ($)", value=25.0, step=5.0)
        v = st.number_input("Boost/Refund %", value=50)
    with c3:
        sp = st.multiselect("Sports", list(sports_map.keys()), default=["NBA"])
    
    if st.button("Add to Queue"):
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

# --- QUEUE DISPLAY ---
if st.session_state.promos:
    for i, p in enumerate(st.session_state.promos):
        st.text(f"{p['book']} | {p['strat']} | ${p['wager']}")
    if st.button("Clear All", type="secondary"):
        st.session_state.promos = []
        st.rerun()

    if st.button("GENERATE OPPORTUNITIES", type="primary"):
        now_utc = datetime.now(timezone.utc)
        
        for p in st.session_state.promos:
            st.markdown(f"### Opportunities for {p['book']}")
            found_plays = []
            
            with st.status(f"Scanning {p['book']}...", expanded=False) as status:
                for sport_label in p['sports']:
                    sport_key = sports_map[sport_label]
                    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                    # Fetching all books to find best hedge
                    params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                    
                    res = requests.get(url, params=params)
                    if res.status_code == 200:
                        st.session_state.api_quota = res.headers.get('x-requests-remaining', "0")
                        games = res.json()
                        
                        for game in games:
                            # 1. Identify Source Book Odds
                            source_outcomes = []
                            other_book_outcomes = []
                            
                            for bm in game['bookmakers']:
                                if bm['key'] == book_map[p['book']]:
                                    source_outcomes = bm['markets'][0]['outcomes']
                                else:
                                    # 2. Hard constraint: Collect odds ONLY from OTHER books
                                    for o in bm['markets'][0]['outcomes']:
                                        other_book_outcomes.append({
                                            'price': o['price'], 
                                            'team': o['name'], 
                                            'book': bm['title']
                                        })
                            
                            if not source_outcomes or not other_book_outcomes: continue

                            for so in source_outcomes:
                                opp_team = next(t for t in [game['home_team'], game['away_team']] if t != so['name'])
                                
                                # Find best hedge price among ALL OTHER books
                                eligible_hedges = [ho for ho in other_book_outcomes if ho['team'] == opp_team]
                                if not eligible_hedges: continue
                                
                                best_h = max(eligible_hedges, key=lambda x: x['price'])
                                
                                sm, hm = get_multiplier(so['price']), get_multiplier(best_h['price'])
                                
                                # Calculation Logic
                                if p['strat'] == "Profit Boost (%)":
                                    bsm = sm * (1 + (p['val']/100))
                                    h_amt = (p['wager'] * (1 + bsm)) / (1 + hm)
                                    profit = (p['wager'] * bsm) - h_amt
                                elif p['strat'] == "Bonus Bet":
                                    h_amt = (p['wager'] * sm) / (1 + hm)
                                    profit = (p['wager'] * sm) - h_amt
                                else: # No Sweat
                                    h_amt = (p['wager'] * (sm + 0.30)) / (hm + 1)
                                    profit = (p['wager'] * sm) - h_amt

                                found_plays.append({
                                    "game": f"{game['away_team']} @ {game['home_team']}",
                                    "profit": profit, "hamt": h_amt, "s_team": so['name'],
                                    "s_price": so['price'], "h_team": best_h['team'],
                                    "h_book": best_h['book'], "h_price": best_h['price']
                                })
                status.update(label="Scan Complete", state="complete")

            # Display top 3
            top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:3]
            for play in top_plays:
                with st.container():
                    col_a, col_b, col_c = st.columns([2, 2, 1])
                    col_a.markdown(f"**{play['s_team']}** ({p['book']})\n\n{play['s_price']:+}")
                    col_b.markdown(f"**{play['h_team']}** ({play['h_book']})\n\n{play['h_price']:+}")
                    col_c.metric("Profit", f"${play['profit']:.2f}")
                    st.divider()
