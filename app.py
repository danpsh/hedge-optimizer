import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# --- TECH LIGHT THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto+Mono&display=swap');
    
    .stApp { background-color: #f8fafc; color: #1e293b; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #0f172a !important; font-weight: 700 !important; }

    /* Expanders & Cards */
    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* Green Metrics */
    [data-testid="stMetricValue"] {
        color: #008f51 !important;
        font-family: 'Roboto Mono', monospace;
        font-weight: 800;
        font-size: 1.6rem !important;
    }
    
    /* Dark Buttons with Green Text */
    .stButton>button {
        background-color: #1e1e1e;
        color: #00ff88;
        border: none;
        border-radius: 8px;
        font-weight: bold;
    }
    .stButton>button:hover { color: #00ff88; border: 1px solid #00ff88; }

    .remove-btn>button {
        background-color: transparent !important;
        color: #ef4444 !important;
        border: 1px solid #fee2e2 !important;
        font-size: 0.8rem !important;
    }

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
    "DraftKings": "draftkings", 
    "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet", 
    "BetMGM": "betmgm"
}

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
    if 'api_quota' not in st.session_state: st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)

st.divider()

# --- INPUT AREA ---
if 'promos' not in st.session_state: st.session_state.promos = []

with st.expander("Step 1: Define Available Promos", expanded=True):
    with st.form("promo_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
            v = st.number_input("Boost/Refund %", min_value=1, value=50)
        with col3:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=["NBA", "NHL"])
        
        if st.form_submit_button("Add to Scan Queue"):
            st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

# --- QUEUE & EXECUTION ---
if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        q_col1, q_col2 = st.columns([9, 1])
        with q_col1:
            st.info(f"**{p['book'].upper()}** | {p['strat']} | Wager: **${p['wager']:.2f}** | Boost: **{p['val']}%**")
        with q_col2:
            st.markdown('<div class="remove-btn">', unsafe_allow_html=True)
            if st.button("✕", key=f"rm_{i}"):
                st.session_state.promos.pop(i)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    run_col, clear_col = st.columns([4, 1])
    with run_col:
        execute = st.button("Identify Opportunities", use_container_width=True)
    with clear_col:
        if st.button("Clear All", use_container_width=True):
            st.session_state.promos = []
            st.rerun()

    if execute:
        allowed_hedge_keys = list(book_map.values())
        now_utc = datetime.now(timezone.utc)
        
        for p in st.session_state.promos:
            all_opps = []
            with st.status(f"Scanning markets for {p['book']}...", expanded=False) as status:
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
                                # Start time check
                                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                                if commence_time <= now_utc: continue

                                source_odds, hedge_odds = [], []
                                for bm in game['bookmakers']:
                                    if bm['key'] in allowed_hedge_keys:
                                        outcomes = bm['markets'][0]['outcomes']
                                        for o in outcomes:
                                            entry = {'book': bm['title'], 'team': o['name'], 'price': o['price']}
                                            if bm['key'] == book_map[p['book']]: source_odds.append(entry)
                                            else: hedge_odds.append(entry)
                                
                                if not source_odds or not hedge_odds: continue

                                for s in source_odds:
                                    opp_team = next(t for t in [game['home_team'], game['away_team']] if t != s['team'])
                                    eligible = [h for h in hedge_odds if h['team'] == opp_team]
                                    if eligible:
                                        best_h = max(eligible, key=lambda x: x['price'])
                                        sm, hm = get_multiplier(s['price']), get_multiplier(best_h['price'])
                                        
                                        if p['strat'] == "Profit Boost (%)":
                                            bsm = sm * (1 + (p['val']/100))
                                            h_amt = round((p['wager'] * (1 + bsm)) / (1 + hm))
                                            profit = min(((p['wager'] * bsm) - h_amt), ((h_amt * hm) - p['wager']))
                                            rating = (profit / p['wager']) * 100
                                        elif p['strat'] == "Bonus Bet":
                                            h_amt = round((p['wager'] * sm) / (1 + hm))
                                            profit = min(((p['wager'] * sm) - h_amt), (h_amt * hm))
                                            rating = (profit / p['wager']) * 100
                                        else: # No Sweat (assumes 70% conversion on refund)
                                            mc = 0.70
                                            h_amt = round((p['wager'] * (sm + (1 - mc))) / (hm + 1))
                                            profit = min(((p['wager'] * sm) - h_amt), ((h_amt * hm) + (p['wager'] * mc) - p['wager']))
                                            rating = (profit / p['wager']) * 100

                                        if profit > -2.0:
                                            all_opps.append({
                                                "game": f"{game['away_team']} vs {game['home_team']}",
                                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                                "profit": profit, "hedge": h_amt, "rating": rating,
                                                "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                                "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                            })
                    except Exception as e: st.error(f"API Error: {e}")
                status.update(label="Scanning Complete", state="complete")

            # --- NEW DISPLAY LOGIC ---
            st.write(f"### Results for {p['book']}")
            sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)
            if not sorted_opps:
                st.warning("No high-value matches found.")
            else:
                for i, op in enumerate(sorted_opps[:5]):
                    title = f"RANK {i+1} | {op['time']} | +${op['profit']:.2f} ({op['rating']:.1f}%)"
                    with st.expander(title):
                        st.write(f"**{op['game']}**")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.caption(f"SOURCE: {op['s_book'].upper()}")
                            st.info(f"Bet **${p['wager']:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                        with c2:
                            st.caption(f"HEDGE: {op['h_book'].upper()}")
                            st.success(f"Bet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                        with c3:
                            st.metric("Net Profit", f"${op['profit']:.2f}")
                            st.caption(f"Strategy: {p['strat']}")
                st.divider()

# --- MANUAL CALCULATOR ---
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
