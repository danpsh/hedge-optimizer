import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- LIGHT TECH THEME ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; font-family: 'Courier New', monospace; font-weight: 800;
    }
    .stButton>button {
        background-color: #1e1e1e; color: #00ff88; border: none; border-radius: 8px; font-weight: bold;
    }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# --- SHARED DATA ---
book_map = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet",
    "BetMGM": "betmgm"
}

sports_map = {
    "NBA": "basketball_nba", 
    "NCAAB": "basketball_ncaab", 
    "NHL": "icehockey_nhl", 
    "Boxing": "boxing_boxing", 
    "MMA": "mma_mixed_martial_arts" 
}
sport_labels = list(sports_map.keys())

# --- HEADER AREA ---
st.title("Promo Converter")

# --- API TRACKER ---
quota_col1, quota_col2 = st.columns([1, 4])
quota_placeholder = quota_col1.empty()
if 'api_quota' not in st.session_state:
    st.session_state.api_quota = "Not Scanned"
quota_placeholder.metric("API Quota Left", st.session_state.api_quota)

# --- GAMEPLAN ARCHITECT ---
st.subheader("Gameplan architect")
with st.expander("Step 1: Input your available promos", expanded=True):
    if 'promos' not in st.session_state: st.session_state.promos = []

    with st.form("gp_form"):
        ga, gb, gc = st.columns([2,2,1])
        with ga:
            gp_b = st.selectbox("Book", list(book_map.keys()), key="gpb")
            gp_s = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="gps")
        with gb:
            gp_w = st.number_input("Wager amount ($)", min_value=1.0, value=25.0, key="gpw")
            gp_v = st.number_input("Boost % (if applicable)", min_value=0, value=50, key="gpv")
        with gc:
            gp_sp = st.multiselect("Sports to search", sport_labels, default=["NCAAB"], key="gpsp")
        
        if st.form_submit_button("Add promo to list"):
            st.session_state.promos.append({"book": gp_b, "strat": gp_s, "wager": gp_w, "val": gp_v, "sports": gp_sp})

    if st.session_state.promos:
        st.write("### Your promo list")
        user_books = list(set([book_map[p['book']] for p in st.session_state.promos]))
        
        for i, p in enumerate(st.session_state.promos):
            promo_title = f"{p['val']}% Profit Boost" if p['strat'] == "Profit Boost (%)" else p['strat']
            st.info(f"**{i+1}. {p['book']} {promo_title}** (${p['wager']}) | Searching: {', '.join(p['sports'])}")
        
        if st.button("Clear list"): 
            st.session_state.promos = []
            st.rerun()

        st.divider()
        api_key = st.secrets.get("ODDS_API_KEY", "")
        
        if st.button("Generate live gameplan", use_container_width=True):
            if not api_key:
                st.error("Missing API Key! Set ODDS_API_KEY in Streamlit Secrets.")
            else:
                now_utc = datetime.now(timezone.utc)
                
                for p in st.session_state.promos:
                    p_header = f"{p['val']}% Profit Boost" if p['strat'] == "Profit Boost (%)" else p['strat']
                    st.write(f"## Best opportunities for: {p['book']} {p_header}")
                    
                    found_plays = []
                    with st.spinner(f"Scanning {', '.join(p['sports'])}..."):
                        for sport_label in p['sports']:
                            sport_key = sports_map[sport_label]
                            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                            book_csv = ",".join(user_books)
                            params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': book_csv, 'oddsFormat': 'american'}
                            
                            res = requests.get(url, params=params)
                            
                            # Update API Quota from headers
                            if 'x-requests-remaining' in res.headers:
                                st.session_state.api_quota = res.headers['x-requests-remaining']
                                quota_placeholder.metric("API Quota Left", st.session_state.api_quota)

                            if res.status_code == 200:
                                games = res.json()
                                for game in games:
                                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                                    if commence_time <= now_utc: continue 
                                    
                                    source_odds, hedge_odds = [], []
                                    for bm in game['bookmakers']:
                                        for m in bm['markets']:
                                            for o in m['outcomes']:
                                                if bm['key'] == book_map[p['book']]:
                                                    source_odds.append(o)
                                                hedge_odds.append({'price': o['price'], 'team': o['name'], 'book': bm['title']})
                                    
                                    for so in source_odds:
                                        opp_team = next((t for t in [game['home_team'], game['away_team']] if t != so['name']), None)
                                        eligible_h = [ho for ho in hedge_odds if ho['team'] == opp_team]
                                        
                                        if eligible_h:
                                            best_h = max(eligible_h, key=lambda x: x['price'])
                                            sm, hm = get_multiplier(so['price']), get_multiplier(best_h['price'])
                                            
                                            if p['strat'] == "Profit Boost (%)":
                                                boosted_sm = sm * (1 + (p['val']/100))
                                                hamt = (p['wager'] * (1 + boosted_sm)) / (1 + hm)
                                                profit = (p['wager'] * boosted_sm) - hamt
                                            elif p['strat'] == "Bonus Bet":
                                                hamt = (p['wager'] * sm) / (1 + hm)
                                                profit = (p['wager'] * sm) - hamt
                                            else: # No-Sweat
                                                hamt = (p['wager'] * (sm + 0.30)) / (hm + 1)
                                                profit = (p['wager'] * sm) - hamt

                                            found_plays.append({
                                                "game": f"{game['away_team']} vs {game['home_team']}",
                                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                                "profit": profit, "hamt": hamt, "s_team": so['name'],
                                                "s_price": so['price'], "h_team": best_h['team'],
                                                "h_book": best_h['book'], "h_price": best_h['price'],
                                                "sport": sport_label
                                            })

                    top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
                    
                    if top_plays:
                        for i, play in enumerate(top_plays):
                            title = f"RANK {i+1} | {play['sport']} | {play['time']} | +${play['profit']:.2f}"
                            with st.expander(title):
                                st.write(f"**{play['game']}**")
                                rc1, rc2, rc3 = st.columns(3)
                                with rc1:
                                    st.caption(f"SOURCE: {p['book'].upper()}")
                                    st.info(f"Bet **${p['wager']:.0f}** on {play['s_team']} @ **{play['s_price']:+}**")
                                with rc2:
                                    st.caption(f"HEDGE: {play['h_book'].upper()}")
                                    st.success(f"Bet **${play['hamt']:.0f}** on {play['h_team']} @ **{play['h_price']:+}**")
                                with rc3:
                                    st.metric("Net Profit", f"${play['profit']:.2f}")
                    else:
                        st.warning("No matches found for this promo.")

# --- MANUAL CALCULATOR ---
st.write("---")
st.subheader("Manual Calculator")
with st.expander("Open Manual Calculator", expanded=True):
    with st.form("manual_calc_form"):
        m_strat = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        mc1, mc2 = st.columns(2)
        with mc1:
            m_s_p = st.number_input("Source Odds", value=250)
            m_w = st.number_input("Wager ($)", value=50.0)
            m_b = st.number_input("Boost %", value=50) if m_strat == "Profit Boost (%)" else 0
        with mc2:
            m_h_p = st.number_input("Hedge Odds", value=-280)
            m_c = st.number_input("Refund %", value=70) if m_strat == "No-Sweat Bet" else 0
        
        if st.form_submit_button("Calculate Hedge", use_container_width=True):
            sm = get_multiplier(m_s_p)
            hm = get_multiplier(m_h_p)
            if m_strat == "Profit Boost (%)":
                bsm = sm * (1 + (m_b/100))
                h_amt = (m_w * (1 + bsm)) / (1 + hm)
                profit = (m_w * bsm) - h_amt
            elif m_strat == "Bonus Bet":
                h_amt = (m_w * sm) / (1 + hm)
                profit = (m_w * sm) - h_amt
            else:
                conv = m_c / 100
                h_amt = (m_w * (sm + (1 - conv))) / (hm + 1)
                profit = (m_w * sm) - h_amt
            
            st.divider()
            res1, res2 = st.columns(2)
            res1.metric("Hedge Amount", f"${h_amt:.0f}")
            res2.metric("Net Profit", f"${profit:.2f}")
