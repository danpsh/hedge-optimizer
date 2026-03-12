import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal Pro", layout="wide")

# --- TECH FLAVOR CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;700&family=JetBrains+Mono&display=swap');
    
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        font-family: 'Outfit', sans-serif;
    }

    /* Glassmorphism Cards */
    div[data-testid="stExpander"], .stForm, .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 16px !important;
        backdrop-filter: blur(10px);
    }

    /* Metric Styling */
    [data-testid="stMetricValue"] {
        color: #10b981 !important;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }

    /* Results Row */
    .result-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border-left: 4px solid #3b82f6;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SECRETS ---
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

# --- HEADER ---
st.title("🚀 Arb Terminal Pro")
st.markdown("##### Smart Promo Conversion & Arbitrage Engine")

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=80)
    st.subheader("System Monitor")
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("API Requests Left", st.session_state.api_quota)
    st.divider()
    st.caption("Active in: US-East Regions")

# --- PROMO ARCHITECT ---
if 'promos' not in st.session_state: st.session_state.promos = []

with st.container():
    st.subheader("🛠 Promo Architect")
    with st.form("promo_entry"):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            b = st.selectbox("Bookmaker", list(book_map.keys()))
            s = st.selectbox("Promo Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", value=25.0, step=5.0)
            v = st.number_input("Value (Boost/Refund %)", value=50)
        with col3:
            sp = st.multiselect("Sports", list(sports_map.keys()), default=["NBA"])
        
        if st.form_submit_button("Add to Gameplan"):
            st.session_state.promos.append({"book": b, "strat": s, "wager": w, "val": v, "sports": sp})

# --- QUEUE DISPLAY ---
if st.session_state.promos:
    st.write("### 📝 Current Gameplan")
    for i, p in enumerate(st.session_state.promos):
        st.info(f"**{p['book']}** | {p['strat']} (${p['wager']})")
    
    col_run, col_clear = st.columns([1, 1])
    with col_clear:
        if st.button("🗑 Clear List"):
            st.session_state.promos = []
            st.rerun()
    with col_run:
        if st.button("🔥 Generate Live Plays", use_container_width=True):
            if not API_KEY:
                st.error("API Key missing in secrets!")
            else:
                for p in st.session_state.promos:
                    st.markdown(f"#### Best Plays for {p['book']}")
                    found_plays = []
                    
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
                                        source_outcomes = []
                                        other_book_outcomes = []
                                        
                                        for bm in game['bookmakers']:
                                            if bm['key'] == book_map[p['book']]:
                                                source_outcomes = bm['markets'][0]['outcomes']
                                            else:
                                                # Logic check: Never hedge on the same book
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
                                st.error(f"Error: {str(e)}")
                        status.update(label="Scanning Complete!", state="complete")

                    top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
                    if top_plays:
                        for play in top_plays:
                            with st.container():
                                st.markdown(f"""
                                <div class="result-card">
                                    <h4 style="margin:0;">{play['game']}</h4>
                                </div>
                                """, unsafe_allow_html=True)
                                c_a, c_b, c_c = st.columns(3)
                                with c_a:
                                    st.caption(f"MAIN: {p['book'].upper()}")
                                    st.write(f"**{play['s_team']}**")
                                    st.code(f"{play['s_price']:+} | Bet ${p['wager']:.0f}")
                                with c_b:
                                    st.caption(f"HEDGE: {play['h_book'].upper()}")
                                    st.write(f"**{play['h_team']}**")
                                    st.code(f"{play['h_price']:+} | Bet ${play['hamt']:.0f}")
                                with c_c:
                                    st.metric("Net Profit", f"${play['profit']:.2f}")
                                st.divider()
                    else:
                        st.warning("No matches found for this specific criteria.")

# --- MANUAL CALCULATOR ---
st.divider()
st.subheader("🧮 Fast-Action Calculator")
with st.expander("Toggle Manual Override"):
    # (Existing manual calculator logic remains here with the new styling)
    m_strat = st.radio("Mode", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
    m1, m2, m3 = st.columns(3)
    with m1:
        m_s_p = st.number_input("Source Odds", value=200, key="ms1")
        m_w = st.number_input("Wager $", value=50.0, key="mw1")
    with m2:
        m_h_p = st.number_input("Hedge Odds", value=-150, key="mh1")
        m_b = st.number_input("Boost %", value=50, key="mb1")
    with m3:
        # Calculate inline
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
            
        st.metric("Hedge This", f"${h_amt:.0f}")
        st.metric("Profit", f"${profit:.2f}")
