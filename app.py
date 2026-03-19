import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# --- PROFESSIONAL THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto+Mono&display=swap');
    
    .stApp { background-color: #f8fafc; color: #1e293b; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #0f172a !important; font-weight: 700 !important; }

    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    .stButton>button {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }

    .remove-btn button {
        background-color: #fef2f2 !important;
        color: #ef4444 !important;
        border: 1px solid #fee2e2 !important;
        border-radius: 4px !important;
        font-size: 0.8rem !important;
        padding: 2px 8px !important;
    }

    [data-testid="stMetricValue"] {
        font-family: 'Roboto Mono', monospace;
        font-size: 1.4rem !important;
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

# --- SCAN ENGINE ---
def run_promo_scan(p):
    allowed_book_keys = list(book_map.values())
    now_utc = datetime.now(timezone.utc)
    all_opps = []
    
    with st.status(f"Scanning {p['book']}...", expanded=False) as status:
        for sport_label in p['sports']:
            sport_key = sports_map[sport_label]
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            params = {'apiKey': API_KEY, 'regions': 'us,us2', 'markets': 'h2h', 'oddsFormat': 'american'}
            
            try:
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    st.session_state.api_quota = res.headers.get('x-requests-remaining', "0")
                    games = res.json()
                    for game in games:
                        commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if commence_time <= now_utc: continue

                        source_odds, hedge_odds = [], []
                        for bm in game['bookmakers']:
                            if bm['key'] in allowed_book_keys:
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
                                    raw_h = (p['wager'] * (1 + bsm)) / (1 + hm)
                                elif p['strat'] == "Bonus Bet":
                                    raw_h = (p['wager'] * sm) / (1 + hm)
                                else: # No-Sweat Bet
                                    mc = 0.65
                                    raw_h = (p['wager'] * (sm + (1 - mc))) / (hm + 1)

                                h_25 = round(raw_h * 4) / 4
                                h_100 = float(round(raw_h))

                                if p['strat'] == "Profit Boost (%)":
                                    bsm = sm * (1 + (p['val']/100))
                                    p_25 = min(((p['wager'] * bsm) - h_25), ((h_25 * hm) - p['wager']))
                                    p_100 = min(((p['wager'] * bsm) - h_100), ((h_100 * hm) - p['wager']))
                                elif p['strat'] == "Bonus Bet":
                                    p_25 = min(((p['wager'] * sm) - h_25), (h_25 * hm))
                                    p_100 = min(((p['wager'] * sm) - h_100), (h_100 * hm))
                                else: # No-Sweat
                                    p_25 = min(((p['wager'] * sm) - h_25), ((h_25 * hm) + (p['wager'] * 0.65) - p['wager']))
                                    p_100 = min(((p['wager'] * sm) - h_100), ((h_100 * hm) + (p['wager'] * 0.65) - p['wager']))

                                if p_25 > -5.0:
                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "sport": sport_label,
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "p_25": p_25, "p_100": p_100,
                                        "h_25": h_25, "h_100": h_100,
                                        "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                        "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price'],
                                        "wager": p['wager']
                                    })
            except Exception as e: st.error(f"API Error: {e}")
        status.update(label="Scanning Complete", state="complete")
    return all_opps

def display_results(all_opps, p):
    st.write(f"### Results for {p['book']}")
    sorted_opps = sorted(all_opps, key=lambda x: x['p_25'], reverse=True)
    
    if not sorted_opps:
        st.warning(f"No matches found.")
    else:
        for i, op in enumerate(sorted_opps[:10]):
            # Updated Rank Title to include Sport, Game, and Date/Time
            title = f"RANK {i+1} | {op['sport']} | {op['game']} | {op['time']} | Profit: ${op['p_25']:.2f}"
            
            with st.expander(title):
                st.write(f"**Full Details:** {op['sport']} - {op['game']} ({op['time']})")
                c_main, c_h25, c_h100 = st.columns([1.2, 1, 1])
                
                with c_main:
                    st.caption(f"SOURCE: {op['s_book'].upper()}")
                    st.info(f"Bet **${op['wager']:.2f}** on **{op['s_team']}** @ **{op['s_price']:+}**")
                
                with c_h25:
                    st.caption(f"HEDGE (0.25)")
                    st.success(f"Bet **${op['h_25']:.2f}** on **{op['h_team']}** @ **{op['h_price']:+}**")
                    st.metric("Profit", f"${op['p_25']:.2f}")

                with c_h100:
                    st.caption(f"HEDGE (1.00)")
                    st.success(f"Bet **${op['h_100']:.0f}.00** on **{op['h_team']}** @ **{op['h_price']:+}**")
                    st.metric("Profit", f"${op['p_100']:.2f}")
    st.divider()

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

with st.expander("Promo Configuration", expanded=True):
    with st.form("promo_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0, step=0.25)
            v = st.number_input("Boost % / Bonus Val", min_value=1, value=50)
        with col3:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=["NBA"])
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            add_to_q = st.form_submit_button("Add to Queue", use_container_width=True)
        with btn_col2:
            quick_scan = st.form_submit_button("Quick Scan", use_container_width=True)

# --- ACTIONS ---
if quick_scan:
    if not sp: st.error("Select a sport.")
    else:
        temp_p = {"book": b, "strat": s, "wager": w, "val": v, "sports": sp}
        results = run_promo_scan(temp_p)
        display_results(results, temp_p)

if add_to_q:
    if not sp: st.error("Select a sport.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        q_col1, q_col2 = st.columns([9.2, 0.8])
        with q_col1:
            st.info(f"**{p['book'].upper()}** | {p['strat']} | ${p['wager']} | {p['val']}% | {', '.join(p['sports'])}")
        with q_col2:
            if st.button("✕", key=f"rm_{i}"):
                st.session_state.promos.pop(i)
                st.rerun()
    
    run_col, clear_col = st.columns([4, 1])
    with run_col:
        if st.button("Run Queue", use_container_width=True):
            for p in st.session_state.promos:
                results = run_promo_scan(p)
                display_results(results, p)
    with clear_col:
        if st.button("Clear All", use_container_width=True):
            st.session_state.promos = []
            st.rerun()
