import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- CLEAN THEME ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
    }
    [data-testid="stMetricValue"] { color: #008f51 !important; font-weight: 800; }
    .stButton>button { background-color: #1e1e1e; color: #00ff88; border-radius: 8px; }
    .stCheckbox { margin-bottom: -10px; white-space: nowrap; }
    </style>
    """, unsafe_allow_html=True)

if 'select_all' not in st.session_state: st.session_state.select_all = False

st.title("Promo Converter")
quota_placeholder = st.empty()

# --- INPUT AREA ---
with st.form("input_panel"):
    col1, col2, col3 = st.columns(3)
    books = {"DraftKings": "draftkings", "FanDuel": "fanduel", "BetMGM": "betmgm", "theScore / ESPN": "espnbet"}
    
    with col1: promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
    with col2: source_book = books[st.radio("Source Book", list(books.keys()), horizontal=True)]
    with col3: hedge_filter = st.radio("Hedge Filter", ["allbooks"] + list(books.values()), horizontal=True)

    st.write("**Select Sports:**")
    sports_map = {"NBA": "basketball_nba", "NCAAB": "basketball_ncaab", "NHL": "icehockey_nhl", "MMA": "mma_mixed_martial_arts"}
    all_clicked = st.checkbox("Select All", value=st.session_state.select_all)
    selected_sports = [v for k, v in sports_map.items() if st.checkbox(k, value=all_clicked)]

    cw, cb = st.columns(2)
    max_wager = float(cw.text_input("Wager ($)", "50.0"))
    boost_val = float(cb.text_input("Boost (%)", "50")) if promo_type == "Profit Boost (%)" else 0.0
    run_scan = st.form_submit_button("Run Optimizer", use_container_width=True)

if run_scan and selected_sports:
    api_key = st.secrets.get("ODDS_API_KEY")
    all_opps = []

    for sport in selected_sports:
        res = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds/", 
                           params={'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'oddsFormat': 'american'})
        if res.status_code == 200:
            quota_placeholder.write(f"Quota: {res.headers.get('x-requests-remaining')}")
            for game in res.json():
                s_odds = [o for b in game['bookmakers'] if b['key'] == source_book for m in b['markets'] for o in m['outcomes']]
                h_odds = [o for b in game['bookmakers'] if (hedge_filter == "allbooks" or b['key'] == hedge_filter) for m in b['markets'] for o in m['outcomes']]
                
                for s in s_odds:
                    opp_team = next(t for t in [game['home_team'], game['away_team']] if t != s['team'])
                    best_h = max([h for h in h_odds if h['team'] == opp_team], key=lambda x: x['price'], default=None)
                    if not best_h: continue

                    sm, hm = (s['price']/100 if s['price']>0 else 100/abs(s['price'])), (best_h['price']/100 if best_h['price']>0 else 100/abs(best_h['price']))
                    
                    if promo_type == "Profit Boost (%)":
                        bsm = sm * (1 + boost_val/100)
                        h_need = round((max_wager * (1 + bsm)) / (1 + hm))
                        profit = min(((max_wager * bsm) - h_need), ((h_need * hm) - max_wager))
                    elif promo_type == "Bonus Bet":
                        h_need = round((max_wager * sm) / (1 + hm))
                        profit = min(((max_wager * sm) - h_need), (h_need * hm))
                    else:
                        h_need = round((max_wager * (sm + 0.3)) / (hm + 1))
                        profit = min(((max_wager * sm) - h_need), ((h_need * hm) + (max_wager * 0.7) - max_wager))

                    if profit > -2:
                        all_opps.append({"game": f"{game['away_team']} @ {game['home_team']}", "profit": profit, "hedge": h_need, "s": s, "h": best_h, "rating": profit if promo_type == "Profit Boost (%)" else (profit/max_wager)})

    for i, op in enumerate(sorted(all_opps, key=lambda x: x['rating'], reverse=True)[:10]):
        # Simplified string to prevent auto-shading
        title = f"Rank {i+1} | Profit ${op['profit']:.2f} | Hedge ${op['hedge']} | {op['game']}"
        with st.expander(title):
            c1, c2, c3 = st.columns(3)
            c1.info(f"Bet ${max_wager} on {op['s']['team']} @ {op['s']['price']}")
            c2.success(f"Hedge ${op['hedge']} on {op['h']['team']} @ {op['h']['price']}")
            c3.metric("Profit", f"${op['profit']:.2f}")

st.write("---")
st.subheader("Manual Calculator")
with st.expander("Open Calc"):
    with st.form("manual"):
        m_s, m_w, m_h = float(st.text_input("Source Odds", "250")), float(st.text_input("Wager", "50")), float(st.text_input("Hedge Odds", "-280"))
        if st.form_submit_button("Calc"):
            msm, mhm = (m_s/100 if m_s>0 else 100/abs(m_s)), (m_h/100 if m_h>0 else 100/abs(m_h))
            mh = round((m_w * msm) / (1 + mhm))
            st.metric("Hedge Needed", f"${mh}")
