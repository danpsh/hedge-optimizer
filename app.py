import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="ARB_TERMINAL", layout="wide")

# --- TERMINAL CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }
    .stApp { background-color: #ffffff; color: #1e1e1e; }
    
    /* Minimalist Metrics */
    [data-testid="stMetricValue"] { 
        font-size: 1.5rem !important; 
        color: #000000 !important;
    }
    
    /* Ultra-Thin Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 2px;
        border: 1px solid #e0e0e0;
        background-color: #ffffff;
        color: #1e1e1e;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1px;
    }
    .stButton>button:hover {
        border-color: #000000;
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    
    /* Cleaner Dividers */
    hr { margin: 1rem 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIG & SECRETS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")

# --- UTILS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

book_map = {
    "DraftKings": "draftkings", "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet", "BetMGM": "betmgm", "Caesars": "caesars"
}

sports_map = {
    "NBA": "basketball_nba", "NCAAB": "basketball_ncaab", 
    "NHL": "icehockey_nhl", "MLB": "baseball_mlb", "MMA": "mma_mixed_martial_arts"
}

# --- SIDEBAR ---
with st.sidebar:
    st.caption("SYSTEM_STATUS")
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("API_REMAINING", st.session_state.api_quota)
    
    if not API_KEY:
        st.error("MISSING_API_KEY")

# --- MAIN INTERFACE ---
st.title("PROMO_CONVERTER_V1")
st.text(f"UTC_TIME: {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

# --- PROMO QUEUE ---
if 'promos' not in st.session_state: st.session_state.promos = []

with st.expander("NEW_ENTRY", expanded=not st.session_state.promos):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        b = st.selectbox("BOOK", list(book_map.keys()))
        s = st.selectbox("TYPE", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
    with c2:
        w = st.number_input("WAGER_USD", value=25.0, step=5.0)
        v = st.number_input("BOOST/REFUND_%", value=50)
    with c3:
        sp = st.multiselect("SPORTS", list(sports_map.keys()), default=["NBA"])
    
    if st.button("APPEND_TO_QUEUE"):
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

# --- QUEUE MANAGEMENT ---
if st.session_state.promos:
    st.divider()
    for i, p in enumerate(st.session_state.promos):
        st.text(f"[{i}] {p['book'].upper()} | {p['strat'].upper()} | ${p['wager']}")
    
    col_run, col_clear = st.columns(2)
    with col_clear:
        if st.button("CLEAR_QUEUE"):
            st.session_state.promos = []
            st.rerun()
    with col_run:
        run_scan = st.button("EXECUTE_SCAN", type="primary")

    if run_scan:
        if not API_KEY:
            st.error("FATAL: API KEY NOT FOUND")
        else:
            for p in st.session_state.promos:
                st.subheader(f"RESULTS: {p['book']}")
                found_plays = []
                
                with st.status(f"Scanning {p['book']}...", expanded=False) as status:
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
                                    source_outcomes = []
                                    other_book_outcomes = []
                                    
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
                                            else: # No Sweat (Standard 70% conversion assumption)
                                                h_amt = (p['wager'] * (sm + (p['val']/100 * 0.7))) / (hm + 1)
                                                profit = (p['wager'] * sm) - h_amt

                                            found_plays.append({
                                                "game": f"{game['away_team']} @ {game['home_team']}",
                                                "profit": profit, "hamt": h_amt, "s_team": so['name'],
                                                "s_price": so['price'], "h_team": best_h['team'],
                                                "h_book": best_h['book'], "h_price": best_h['price']
                                            })
                        except Exception as e:
                            st.error(f"API_ERROR: {str(e)}")
                    status.update(label="SCAN_COMPLETE", state="complete")

                top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
                if top_plays:
                    for play in top_plays:
                        col_main, col_val = st.columns([4, 1])
                        with col_main:
                            st.text(f"{play['game']}")
                            st.caption(f"BET: {play['s_team']} {play['s_price']:+} on {p['book'].upper()}")
                            st.caption(f"HEDGE: {play['h_team']} {play['h_price']:+} on {play['h_book'].upper()} (${play['hamt']:.0f})")
                        with col_val:
                            st.metric("NET", f"+${play['profit']:.2f}")
                        st.divider()
                else:
                    st.warning("NO_MATCHES_FOUND")

# --- MANUAL CALCULATOR ---
st.write("---")
st.caption("MANUAL_OVERRIDE")
with st.expander("OPEN_CALCULATOR"):
    with st.form("manual_form"):
        m_strat = st.radio("STRATEGY", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        mc1, mc2 = st.columns(2)
        with mc1:
            m_s_p = st.number_input("SOURCE_ODDS", value=250)
            m_w = st.number_input("WAGER_AMOUNT", value=50.0)
            m_b = st.number_input("BOOST/REFUND_%", value=50)
        with mc2:
            m_h_p = st.number_input("HEDGE_ODDS", value=-280)
        
        if st.form_submit_button("CALCULATE_HEDGE"):
            sm, hm = get_multiplier(m_s_p), get_multiplier(m_h_p)
            if m_strat == "Profit Boost (%)":
                bsm = sm * (1 + (m_b/100))
                h_amt = (m_w * (1 + bsm)) / (1 + hm)
                profit = (m_w * bsm) - h_amt
            elif m_strat == "Bonus Bet":
                h_amt = (m_w * sm) / (1 + hm)
                profit = (m_w * sm) - h_amt
            else:
                h_amt = (m_w * (sm + (m_b/100 * 0.7))) / (hm + 1)
                profit = (m_w * sm) - h_amt
            
            st.divider()
            r1, r2 = st.columns(2)
            r1.metric("HEDGE_AMOUNT", f"${h_amt:.0f}")
            r2.metric("EXPECTED_PROFIT", f"${profit:.2f}")
