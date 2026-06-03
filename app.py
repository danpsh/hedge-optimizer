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
    [data-testid="stMetricValue"] {
        font-family: 'Roboto Mono', monospace;
        font-size: 1.4rem !important;
    }
    .promo-header {
        background-color: #e2e8f0;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 5px solid #1e293b;
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

# --- ACTIVE SPORTS ---
sports_map = {
    "NBA": "basketball_nba",
    "WNBA": "basketball_wnba",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb",
    "French Open": "tennis_fr_open"  # Added French Open
}

# --- CACHED API FETCHING ---
@st.cache_data(ttl=300)
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        'apiKey': API_KEY, 
        'regions': 'us,us2', 
        'markets': 'h2h', 
        'oddsFormat': 'american'
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        return res.json(), res.headers.get('x-requests-remaining', "0")
    else:
        return None, "Error"

# --- SCAN ENGINE ---
def run_promo_scan(p):
    if not p['hedge_books']:
        allowed_hedge_keys = [v for k, v in book_map.items() if k != p['book']]
    else:
        allowed_hedge_keys = [book_map[b] for b in p['hedge_books']]

    source_book_key = book_map[p['book']]
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=8)
    all_opps = []
    
    with st.status(f"Scanning {p['book']}...", expanded=False) as status:
        for sport_label in p['sports']:
            sport_key = sports_map[sport_label]
            games, remaining = fetch_odds(sport_key)
            
            if games:
                st.session_state.api_quota = remaining
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    if commence_time <= now_utc or commence_time > lookahead_limit:
                        continue

                    source_odds, hedge_odds = [], []
                    for bm in game['bookmakers']:
                        if bm['key'] == source_book_key or bm['key'] in allowed_hedge_keys:
                            outcomes = bm['markets'][0]['outcomes']
                            for o in outcomes:
                                entry = {'book': bm['title'], 'team': o['name'], 'price': o['price']}
                                if bm['key'] == source_book_key: 
                                    source_odds.append(entry)
                                elif bm['key'] in allowed_hedge_keys: 
                                    hedge_odds.append(entry)
                    
                    if not source_odds or not hedge_odds: continue

                    for s in source_odds:
                        opp_team = next((t for t in [game['home_team'], game['away_team']] if t != s['team']), None)
                        if not opp_team: continue
                        
                        eligible = [h for h in hedge_odds if h['team'] == opp_team]
                        if eligible:
                            best_h = max(eligible, key=lambda x: x['price'])
                            sm, hm = get_multiplier(s['price']), get_multiplier(best_h['price'])
                            
                            if p['strat'] == "Profit Boost (%)":
                                bsm = sm * (1 + (p['val']/100))
                                raw_h = (p['wager'] * (1 + bsm)) / (1 + hm)
                            elif p['strat'] == "Bonus Bet":
                                raw_h = (p['wager'] * sm) / (1 + hm)
                            else: # No-Sweat
                                mc = 0.65
                                raw_h = (p['wager'] * (sm + (1 - mc))) / (hm + 1)

                            # Exact calculations
                            if p['strat'] == "Profit Boost (%)":
                                bsm = sm * (1 + (p['val']/100))
                                exact_profit = min(((p['wager'] * bsm) - raw_h), ((raw_h * hm) - p['wager']))
                            elif p['strat'] == "Bonus Bet":
                                exact_profit = min(((p['wager'] * sm) - raw_h), (raw_h * hm))
                            else:
                                exact_profit = min(((p['wager'] * sm) - raw_h), ((raw_h * hm) + (p['wager'] * 0.65) - p['wager']))

                            if exact_profit > -10.0:
                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "sport": sport_label,
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                    "exact_profit": exact_profit,
                                    "exact_hedge": raw_h,
                                    "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                    "h_book": best_h['book'], "h_team": best_h['team'], "h_price": best_h['price'],
                                    "wager": p['wager'],
                                    "promo_val": p['val']
                                })
            else:
                st.error(f"Could not fetch data for {sport_label}")

        status.update(label=f"Scan for {p['book']} Complete", state="complete")
    return all_opps

def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} - {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)
    
    if not sorted_opps:
        st.warning(f"No profitable matches found for {p['book']}.")
    else:
        for i, op in enumerate(sorted_opps[:10]):
            if p['strat'] == "Bonus Bet":
                conv_rate = (op['exact_profit'] / op['wager']) * 100
                conv_str = f" | {conv_rate:.1f}% Conversion"
            else:
                conv_str = ""

            header_title = f"RANK {i+1} | {op['time']} | {op['game']}{conv_str} | Profit: ${op['exact_profit']:.2f}"
            
            with st.expander(header_title):
                st.write(f"**Full Match Details:** {op['sport']} | {op['game']} | Start Time: {op['time']}")
                c_main, c_hedge = st.columns([1.5, 2])
                with c_main:
                    st.caption(f"SOURCE BOOK: **{op['s_book'].upper()}**")
                    st.info(f"Bet **${op['wager']:.2f}** on **{op['s_team']}** @ **{op['s_price']:+}**")
                with c_hedge:
                    st.caption(f"HEDGE BOOK: **{op['h_book'].upper()}** (Exact)")
                    st.success(f"Bet **${op['exact_hedge']:.2f}** on **{op['h_team']}** @ **{op['h_price']:+}**")
                    st.metric("Optimal Profit", f"${op['exact_profit']:.2f}")

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
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=1.0)
            v = st.number_input("Boost % / Bonus Val", min_value=0, value=0)
        with col3:
            hb = st.multiselect("Hedge Book(s)", [k for k in book_map.keys() if k != b], placeholder="All Books")
        with col4:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), placeholder="Select sports...")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            add_to_q = st.form_submit_button("Add to Queue", use_container_width=True)
        with btn_col2:
            quick_scan = st.form_submit_button("Quick Scan", use_container_width=True)

# --- ACTIONS ---
if quick_scan:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        temp_p = {"book": b, "strat": s, "wager": w, "val": v, "sports": sp, "hedge_books": hb}
        results = run_promo_scan(temp_p)
        display_results(results, temp_p)

if add_to_q:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp, "hedge_books": hb})

if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        q_col1, q_col2 = st.columns([9.2, 0.8])
        with q_col1:
            hedge_label = ", ".join(p['hedge_books']) if p['hedge_books'] else "ALL"
            st.info(f"**{p['book'].upper()}** vs **{hedge_label}** | {p['strat']} | ${p['wager']} | {p['val']}% | {', '.join(p['sports'])}")
        with q_col2:
            if st.button("✕", key=f"rm_{i}"):
                st.session_state.promos.pop(i)
                st.rerun()
    
    run_col, clear_col, cache_col = st.columns([3, 1, 1])
    with run_col:
        if st.button("Run All in Queue", use_container_width=True):
            for promo_item in st.session_state.promos:
                scan_results = run_promo_scan(promo_item)
                display_results(scan_results, promo_item)
                st.divider() 
    with clear_col:
        if st.button("Clear Queue", use_container_width=True):
            st.session_state.promos = []
            st.rerun()
    with cache_col:
        if st.button("Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.toast("Cache cleared!")
