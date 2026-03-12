import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# --- BLOOMBERG LIGHT THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto+Mono&display=swap');
    
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3 {
        color: #0f172a !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
    }

    /* Professional Cards */
    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #059669 !important;
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 1.6rem !important;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #1e293b;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #334155;
        color: #ffffff;
    }

    /* Odds Display */
    code {
        color: #475569 !important;
        background-color: #f1f5f9 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'Roboto Mono', monospace !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")

def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

book_map = {
    "DraftKings": "draftkings", "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet", "BetMGM": "betmgm", "Caesars": "caesars"
}

# Updated to include NHL
sports_map = {
    "NBA": "basketball_nba",
    "NCAA Men's": "basketball_ncaab",
    "NCAA Women's": "basketball_ncaaw",
    "NHL": "icehockey_nhl"
}

# --- HEADER AREA ---
c_title, c_quota = st.columns([3, 1])
with c_title:
    st.title("Promo Converter")
with c_quota:
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("API Quota", st.session_state.api_quota)

st.divider()

# --- INPUT AREA (ALWAYS OPEN) ---
if 'promos' not in st.session_state: st.session_state.promos = []

with st.expander("Step 1: Define Available Promos", expanded=True):
    with st.form("promo_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=1.0, value=25.0)
            v = st.number_input("Promo Value (Boost/Refund %)", min_value=1, value=50)
        with col3:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=["NBA", "NHL"])
        
        if st.form_submit_button("Add to Scan Queue"):
            st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

# --- QUEUE & EXECUTION ---
if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        st.info(f"**{p['book']}** | {p['strat']} (${p['wager']:.2f})")
    
    run_col, clear_col = st.columns([4, 1])
    with run_col:
        execute = st.button("Run Market Analysis", use_container_width=True)
    with clear_col:
        if st.button("Clear All", use_container_width=True):
            st.session_state.promos = []
            st.rerun()

    if execute:
        for p in st.session_state.promos:
            st.write(f"### Best Markets: {p['book']}")
            found_plays = []
            
            with st.status(f"Scanning {p['book']} opportunities...", expanded=False) as status:
                for sport_label in p['sports']:
                    sport_key = sports_map[sport_label]
                    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                    params = {'apiKey': API_KEY, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                    
                    try:
                        res = requests.get(url, params=params)
                        if res.status_code == 200:
                            st.session_state.api_quota = res.headers.get('x-requests-remaining', "0")
                            games = res.json()
                            
                            for game in games:
                                source_outcomes, other_book_outcomes = [], []
                                for bm in game['bookmakers']:
                                    if bm['key'] == book_map[p['book']]:
                                        source_outcomes = bm['markets'][0]['outcomes']
                                    else:
                                        for o in bm['markets'][0]['outcomes']:
                                            other_book_outcomes.append({
                                                'price': o['price'], 'team': o['name'], 'book': bm['title']
                                            })
                                
                                if not source_outcomes or not other_book_outcomes: continue

                                for so in source_outcomes:
                                    opp_team = next(t for t in [game['home_team'], game['away_team']] if t != so['name'])
                                    eligible_hedges = [ho for ho in other_book_outcomes if ho['team'] == opp_team]
                                    
                                    if eligible_hedges:
                                        best_h = max(eligible_hedges, key=lambda x: x['price'])
                                        sm, hm = get_multiplier(so['price']), get_multiplier(best_h['price'])
                                        
                                        if p['strat'] == "Profit Boost (%)":
                                            bsm = sm * (1 + (p['val']/100))
                                            h_amt = (p['wager'] * (1 + bsm)) / (1 + hm)
                                            profit = (p['wager'] * bsm) - h_amt
                                        elif p['strat'] == "Bonus Bet":
                                            h_amt = (p['wager'] * sm) / (1 + hm)
                                            profit = (p['wager'] * sm) - h_amt
                                        else: # No Sweat
                                            h_amt = (p['wager'] * (sm + (p['val']/100 * 0.7))) / (hm + 1)
                                            profit = (p['wager'] * sm) - h_amt

                                        found_plays.append({
                                            "game": f"{game['away_team']} @ {game['home_team']}",
                                            "profit": profit, "hamt": h_amt, "s_team": so['name'],
                                            "s_price": so['price'], "h_team": best_h['team'],
                                            "h_book": best_h['book'], "h_price": best_h['price']
                                        })
                    except Exception as e:
                        st.error(f"Error connecting to API: {e}")
                status.update(label="Scanning Complete", state="complete")

            top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
            if top_plays:
                for play in top_plays:
                    with st.container():
                        c1, c2, c3 = st.columns([3, 3, 2])
                        with c1:
                            st.caption(f"SOURCE: {p['book'].upper()}")
                            st.markdown(f"**{play['s_team']}**")
                            st.code(f"{play['s_price']:+} | Bet ${p['wager']:.2f}")
                        with c2:
                            st.caption(f"HEDGE: {play['h_book'].upper()}")
                            st.markdown(f"**{play['h_team']}**")
                            st.code(f"{play['h_price']:+} | Bet ${play['hamt']:.0f}")
                        with c3:
                            st.metric("Net Profit", f"${play['profit']:.2f}")
                        st.divider()
            else:
                st.warning("No matches found.")

# --- MANUAL CALCULATOR ---
st.write("---")
st.write("### Manual Calculation")
with st.expander("Open Calculator"):
    m_strat = st.radio("Conversion Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        ms_p = st.number_input("Source Odds", value=200, key="ms")
        mw_a = st.number_input("Wager $", value=50.0, key="mw")
    with col_m2:
        mh_p = st.number_input("Hedge Odds", value=-150, key="mh")
        mv_v = st.number_input("Boost/Refund %", value=50, key="mv")
    with col_m3:
        sm_calc, hm_calc = get_multiplier(ms_p), get_multiplier(mh_p)
        if m_strat == "Profit Boost (%)":
            bsm_c = sm_calc * (1 + (mv_v/100))
            ha = (mw_a * (1 + bsm_c)) / (1 + hm_calc)
            pr = (mw_a * bsm_c) - ha
        elif m_strat == "Bonus Bet":
            ha = (mw_a * sm_calc) / (1 + hm_calc)
            pr = (mw_a * sm_calc) - ha
        else:
            ha = (mw_a * (sm_calc + (mv_v/100 * 0.7))) / (hm_calc + 1)
            pr = (mw_a * sm_calc) - ha
            
        st.metric("Hedge Amount", f"${ha:.2f}")
        st.metric("Expected Profit", f"${pr:.2f}")
