import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal | 2026 Winter Olympics", layout="wide")

# --- CUSTOM TECH THEME ---
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

# --- API HELPERS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")

@st.cache_data(ttl=3600)
def fetch_active_sports():
    """Fetch real-time in-season sports from The Odds API."""
    if not API_KEY: return {}
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            # Return dict of {Sport Title: Sport Key}
            return {s['title']: s['key'] for s in data}
    except:
        return {}
    return {}

# --- HEADER & QUOTA ---
st.title("🥇 Promo Converter: Milano Cortina 2026")
quota_placeholder = st.empty()

# --- INPUT PANEL ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col3 = st.columns(3)
        book_map = {"DraftKings": "draftkings", "FanDuel": "fanduel", "BetMGM": "betmgm", "ESPN Bet": "espnbet", "All Books": "allbooks"}

        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book = book_map[st.radio("Source (Promo Book)", list(book_map.keys())[:-1], horizontal=True)]
        with col3:
            hedge_filter = book_map[st.radio("Hedge (Filter)", list(book_map.keys()), horizontal=True)]

        st.divider()
        
        # --- DYNAMIC SPORT SELECTION ---
        st.write("**Active In-Season Sports (Syncing from API...)**")
        all_sports = fetch_active_sports()
        selected_keys = []
        
        if all_sports:
            # Group into columns for scannability
            sport_cols = st.columns(6)
            for i, (name, key) in enumerate(all_sports.items()):
                with sport_cols[i % 6]:
                    # Auto-check Olympic sports
                    is_oly = "olympic" in key.lower() or "winter" in key.lower()
                    if st.checkbox(name, key=f"cb_{key}", value=is_oly):
                        selected_keys.append(key)
        else:
            st.warning("No sports found. Check your API Key.")

        st.divider()
        cw, cb = st.columns(2)
        with cw:
            max_wager = float(st.text_input("Wager Amount ($)", value="50.0"))
        with cb:
            boost_val = float(st.text_input("Boost %", value="50") if promo_type == "Profit Boost (%)" else "0")
            
        run_scan = st.form_submit_button("Run Optimizer", use_container_width=True)

# --- SCAN LOGIC ---
if run_scan:
    if not API_KEY or not selected_keys:
        st.error("Missing API Key or no sports selected.")
    else:
        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,caesars,fanatics,espnbet"
        all_opps = []
        now = datetime.now(timezone.utc)

        with st.spinner("Scanning markets..."):
            for sport in selected_keys:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': API_KEY, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    quota_placeholder.markdown(f"**Quota Remaining:** {res.headers.get('x-requests-remaining', 'N/A')}")
                    for game in res.json():
                        commence = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if commence <= now: continue 
                        
                        source_odds, hedge_odds = [], []
                        for book in game['bookmakers']:
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book': book['title'], 'team': o['name'], 'price': o['price']}
                                    if book['key'] == source_book: source_odds.append(entry)
                                    if hedge_filter == "allbooks" or book['key'] == hedge_filter: hedge_odds.append(entry)

                        for s in source_odds:
                            opp_team = next((t for t in [game['home_team'], game['away_team']] if t != s['team']), None)
                            eligible = [h for h in hedge_odds if h['team'] == opp_team]
                            if not eligible: continue
                            
                            best_h = max(eligible, key=lambda x: x['price'])
                            s_m = (s['price']/100) if s['price'] > 0 else (100/abs(s['price']))
                            h_m = (best_h['price']/100) if best_h['price'] > 0 else (100/abs(best_h['price']))

                            # Math Engine
                            if promo_type == "Profit Boost (%)":
                                boosted_m = s_m * (1 + (boost_val/100))
                                h_need = round((max_wager * (1 + boosted_m)) / (1 + h_m))
                                profit = min(((max_wager * boosted_m) - h_need), ((h_need * h_m) - max_wager))
                            elif promo_type == "Bonus Bet":
                                h_need = round((max_wager * s_m) / (1 + h_m))
                                profit = min(((max_wager * s_m) - h_need), (h_need * h_m))
                            else: # No-Sweat (Assumes 70% conversion of refund)
                                h_need = round((max_wager * (s_m + 0.30)) / (h_m + 1))
                                profit = min(((max_wager * s_m) - h_need), ((h_need * h_m) + (max_wager * 0.70) - max_wager))

                            if profit > -2.0:
                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "sport": "OLY" if "olympic" in sport else sport.split('_')[-1].upper(),
                                    "profit": profit, "hedge": h_need,
                                    "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                    "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                })

        if all_opps:
            top_6 = sorted(all_opps, key=lambda x: x['profit'], reverse=True)[:6]
            for i, op in enumerate(top_6):
                with st.expander(f"Rank {i+1} | {op['sport']} | Profit: ${op['profit']:.2f}"):
                    c1, c2, c3 = st.columns(3)
                    c1.info(f"Source: {op['s_book']}\n\n${max_wager} on {op['s_team']} @ {op['s_price']}")
                    c2.success(f"Hedge: {op['h_book']}\n\n${op['hedge']} on {op['h_team']} @ {op['h_price']}")
                    c3.metric("Net Profit", f"${op['profit']:.2f}")
        else:
            st.info("No profitable opportunities found in the current scan.")

# --- MANUAL CALCULATOR SECTION ---
st.divider()
st.subheader("🧮 Manual Arbitrage Calculator")
with st.expander("Calculate custom odds manually", expanded=False):
    with st.form("manual_calc"):
        mc1, mc2 = st.columns(2)
        with mc1:
            m_strat = st.radio("Strategy", ["Standard Arb", "Bonus Bet", "Profit Boost"], horizontal=True)
            m_wager = st.number_input("Wager Amount ($)", value=100.0)
            m_s_odds = st.number_input("Source Odds (American)", value=250)
        with mc2:
            m_h_odds = st.number_input("Hedge Odds (American)", value=-220)
            m_extra = st.number_input("Extra % (Boost or Refund)", value=50)
            
        if st.form_submit_button("Calculate Manual Hedge"):
            # Internal Math Logic
            sm = (m_s_odds/100) if m_s_odds > 0 else (100/abs(m_s_odds))
            hm = (m_h_odds/100) if m_h_odds > 0 else (100/abs(m_h_odds))
            
            if m_strat == "Profit Boost":
                bsm = sm * (1 + (m_extra/100))
                h = round((m_wager * (1 + bsm)) / (1 + hm))
                p = min(((m_wager * bsm) - h), ((h * hm) - m_wager))
            elif m_strat == "Bonus Bet":
                h = round((m_wager * sm) / (1 + hm))
                p = min(((m_wager * sm) - h), (h * hm))
            else: # Standard Arb
                h = round((m_wager * (1 + sm)) / (1 + hm))
                p = min(((m_wager * sm) - h), ((h * hm) - m_wager))
                
            rc1, rc2 = st.columns(2)
            rc1.metric("Required Hedge", f"${h:.2f}")
            rc2.metric("Guaranteed Profit", f"${p:.2f}")
