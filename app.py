import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="ARB TERMINAL", layout="wide")

# --- LIGHT TECH THEME (Minimal CSS) ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    
    /* Main Expander Container */
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
    div[data-testid="column"] { width: min-content !important; min-width: 85px !important; }
    </style>
    """, unsafe_allow_html=True)

# Helper Functions
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# Initialize Session State
if 'select_all' not in st.session_state:
    st.session_state.select_all = False

# --- HEADER AREA ---
st.title("PROMO CONVERTER")
quota_placeholder = st.empty()
quota_placeholder.markdown("**QUOTA:** Not scanned yet")

# --- INPUT AREA (SINGLE BOOK SCANNER) ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        
        book_map = {
            "DraftKings": "draftkings",
            "FanDuel": "fanduel",
            "BetMGM": "betmgm",
            "theScore / ESPN": "espnbet",
            "All Books": "allbooks"
        }

        with col1:
            promo_type = st.radio("STRATEGY", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book_display = st.radio("SOURCE BOOK (PROMO)", ["DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            source_book = book_map[source_book_display]
        with col_hedge:
            hedge_book_display = st.radio("HEDGE BOOK (FILTER)", ["All Books", "DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            hedge_filter = book_map[hedge_book_display]

        st.divider()
        st.write("**SELECT SPORTS TO SCAN:**")
        sports_map = {
            "NBA": "basketball_nba", "NCAAB": "basketball_ncaab", "NCAAW": "basketball_wncaab",
            "NHL": "icehockey_nhl", "Boxing": "boxing_boxing", "MMA": "mma_mixed_martial_arts" 
        }
        sport_labels = list(sports_map.keys())
        selected_sports = []

        all_clicked = st.checkbox("SELECT ALL", value=st.session_state.select_all)
        sport_cols = st.columns(len(sport_labels))
        for i, label in enumerate(sport_labels):
            with sport_cols[i]:
                if st.checkbox(label, value=all_clicked, key=f"cb_{label}"):
                    selected_sports.append(sports_map[label])

        st.divider()
        col_w, col_b = st.columns([1, 1])
        with col_w:
            max_wager_raw = st.text_input("WAGER ($)", value="50.0")
        with col_b:
            boost_val_raw = st.text_input("BOOST (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
            
        run_scan = st.form_submit_button("RUN OPTIMIZER", use_container_width=True)

# --- SCAN LOGIC (SINGLE BOOK) ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("MISSING API KEY!")
    elif not selected_sports:
        st.warning("PLEASE SELECT AT LEAST ONE SPORT.")
    else:
        try:
            max_wager, boost_val = float(max_wager_raw), float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner("SCANNING MARKETS..."):
            for sport in selected_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': "draftkings,fanduel,betmgm,bet365,williamhill_us,caesars,fanatics,espnbet", 'oddsFormat': 'american'}
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    quota_placeholder.markdown(f"**QUOTA REMAINING:** {res.headers.get('x-requests-remaining', 'N/A')}")
                    games = res.json()
                    for game in games:
                        commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if commence_time <= now_utc: continue 
                        source_odds, hedge_odds = [], []
                        for book in game['bookmakers']:
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book_name': book['title'], 'team': o['name'], 'price': o['price']}
                                    if book['key'] == source_book: source_odds.append(entry)
                                    if hedge_filter == "allbooks" or book['key'] == hedge_filter: hedge_odds.append(entry)

                        for s in source_odds:
                            opp_team = next((t for t in [game['home_team'], game['away_team']] if t != s['team']), None)
                            eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                            if not eligible_hedges: continue
                            best_h = max(eligible_hedges, key=lambda x: x['price'])
                            s_m, h_m = get_multiplier(s['price']), get_multiplier(best_h['price'])

                            if promo_type == "Profit Boost (%)":
                                b_s_m = s_m * (1 + (boost_val / 100))
                                h_needed = round((max_wager * (1 + b_s_m)) / (1 + h_m))
                                profit = min(((max_wager * b_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                rating = profit
                            elif promo_type == "Bonus Bet":
                                h_needed = round((max_wager * s_m) / (1 + h_m))
                                profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                rating = (profit / max_wager) * 100
                            else: # No-Sweat
                                h_needed = round((max_wager * (s_m + 0.30)) / (h_m + 1))
                                profit = min(((max_wager * s_m) - h_needed), ((h_needed * h_m) + (max_wager * 0.70) - max_wager))
                                rating = (profit / max_wager) * 100

                            if profit > -5.0:
                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}", "sport": sport.split('_')[-1].upper(),
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                    "profit": profit, "hedge": h_needed, "rating": rating,
                                    "s_team": s['team'], "s_book": s['book_name'], "s_price": s['price'],
                                    "h_team": best_h['team'], "h_book": best_h['book_name'], "h_price": best_h['price']
                                })

        st.write("### TOP 10 OPPORTUNITIES")
        top_10 = sorted(all_opps, key=lambda x: x['rating'], reverse=True)[:10]
        for i, op in enumerate(top_10):
            roi = op['rating'] if promo_type != "Profit Boost (%)" else (op['profit'] / max_wager) * 100
            with st.expander(f"RANK {i+1} ｜ {op['sport']} ({op['time']}) ｜ PROFIT: ${op['profit']:.2f} ({int(roi)}%)"):
                c1, c2, c3 = st.columns(3)
                c1.info(f"**{op['s_book'].upper()}**\n\nBet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                c2.success(f"**{op['h_book'].upper()}**\n\nBet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                c3.metric("NET PROFIT", f"${op['profit']:.2f}")

# --- MULTI-PROMO OPTIMIZER (API SCANNER) ---
st.write("---")
st.subheader("MULTI-PROMO OPTIMIZER")
with st.expander("COMBINE TWO DIFFERENT PROMOS (AUTO-SCAN)", expanded=True):
    with st.form("multi_promo_scan_form"):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### SIDE A (PROMO 1)")
            a_strat = st.selectbox("STRATEGY A", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="as1")
            a_book = st.selectbox("BOOK A", ["draftkings", "fanduel", "betmgm", "espnbet"], key="ab1")
            a_wager_max = st.number_input("MAX WAGER A ($)", value=50.0)
            a_boost = st.number_input("BOOST A (%)", value=50) if a_strat == "Profit Boost (%)" else 0
        with col_r:
            st.markdown("### SIDE B (PROMO 2)")
            b_strat = st.selectbox("STRATEGY B", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Cash (No Promo)"], key="as2")
            b_book = st.selectbox("BOOK B", ["fanduel", "draftkings", "betmgm", "espnbet"], key="ab2")
            b_wager_max = st.number_input("MAX WAGER B ($)", value=50.0)
            b_boost = st.number_input("BOOST B (%)", value=0) if b_strat == "Profit Boost (%)" else 0

        run_multi_scan = st.form_submit_button("RUN MULTI-PROMO SCANNER", use_container_width=True)

if run_multi_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    multi_results = []
    with st.spinner("FINDING CROSS-BOOK MATCHES..."):
        # Uses selected sports from main input section
        for sport in selected_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': f"{a_book},{b_book}", 'oddsFormat': 'american'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                games = res.json()
                for game in games:
                    odds_a, odds_b = [], []
                    for bm in game['bookmakers']:
                        for m in bm['markets']:
                            for o in m['outcomes']:
                                if bm['key'] == a_book: odds_a.append(o)
                                if bm['key'] == b_book: odds_b.append(o)
                    
                    for o_a in odds_a:
                        for o_b in odds_b:
                            if o_a['name'] == o_b['name']: continue # Opposing teams only
                            m_a, m_b = get_multiplier(o_a['price']), get_multiplier(o_b['price'])
                            
                            # Effective Multiplier Logic
                            eff_m_a = m_a * (1 + a_boost/100) if a_strat == "Profit Boost (%)" else m_a
                            loss_a_val = 0 if a_strat == "Bonus Bet" else (0.30 if a_strat == "No-Sweat Bet" else 1.0)
                            
                            eff_m_b = m_b * (1 + b_boost/100) if b_strat == "Profit Boost (%)" else m_b
                            loss_b_val = 0 if b_strat == "Bonus Bet" else (0.30 if b_strat == "No-Sweat Bet" else 1.0)

                            # Calculate ratio for perfect hedge
                            # WagerA * (EffMA + LossA_val) = WagerB * (EffMB + LossB_val)
                            ratio = (eff_m_a + loss_a_val) / (eff_m_b + loss_b_val)
                            
                            # Determine optimal stakes based on BOTH caps
                            final_w_a = a_wager_max
                            final_w_b = final_w_a * ratio
                            
                            if final_w_b > b_wager_max:
                                final_w_b = b_wager_max
                                final_w_a = final_w_b / ratio

                            # Final Profit Calculation
                            profit = (final_w_a * eff_m_a) - (final_w_b * (1.0 if b_strat == "Cash (No Promo)" or b_strat == "Profit Boost (%)" else (0.30 if b_strat == "No-Sweat Bet" else 0)))
                            
                            multi_results.append({
                                "game": f"{game['away_team']} vs {game['home_team']}",
                                "profit": profit, "w_a": final_w_a, "w_b": final_w_b, 
                                "a_team": o_a['name'], "a_odds": o_a['price'],
                                "b_team": o_b['name'], "b_odds": o_b['price'], "sport": sport.split('_')[-1].upper()
                            })

    top_multi = sorted(multi_results, key=lambda x: x['profit'], reverse=True)[:10]
    for i, item in enumerate(top_multi):
        with st.expander(f"MULTI-RANK {i+1} ｜ {item['sport']} ｜ PROFIT: ${item['profit']:.2f}"):
            c1, c2, c3 = st.columns(3)
            c1.info(f"**{a_book.upper()}**\n\nBet **${item['w_a']:.2f}** on {item['a_team']} @ **{item['a_odds']:+}**")
            c2.success(f"**{b_book.upper()}**\n\nBet **${item['w_b']:.2f}** on {item['b_team']} @ **{item['b_odds']:+}**")
            c3.metric("NET PROFIT", f"${item['profit']:.2f}")

# --- MANUAL CALCULATOR ---
st.write("---")
st.subheader("MANUAL CALCULATOR")
with st.expander("OPEN MANUAL CALCULATOR", expanded=False):
    with st.form("manual_calc_form"):
        m_promo = st.radio("STRATEGY", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True, key="m_strat")
        m_book = st.text_input("BOOK NAME", value="DraftKings")
        m_sport = st.text_input("SPORT", value="NBA")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_s_p = st.text_input("SOURCE ODDS", value="250")
            m_w = st.text_input("WAGER ($)", value="50.0")
            m_b = st.text_input("BOOST %", value="50") if m_promo == "Profit Boost (%)" else "0"
        with m_col2:
            m_h_p = st.text_input("HEDGE ODDS", value="-280")
            m_c = st.text_input("REFUND %", value="70") if m_promo == "No-Sweat Bet" else "0"
        
        if st.form_submit_button("CALCULATE HEDGE", use_container_width=True):
            try:
                ms_p, mw, mh_p = float(m_s_p), float(m_w), float(m_h_p)
                ms_m, mh_m = get_multiplier(ms_p), get_multiplier(mh_p)
                if m_promo == "Profit Boost (%)":
                    m_h = round((mw * (1 + ms_m * (1 + float(m_b)/100))) / (1 + mh_m))
                    m_p = min(((mw * ms_m * (1 + float(m_b)/100)) - m_h), ((m_h * mh_m) - mw))
                elif m_promo == "Bonus Bet":
                    m_h = round((mw * ms_m) / (1 + mh_m))
                    m_p = min(((mw * ms_m) - m_h), (m_h * mh_m))
                else: 
                    m_h = round((mw * (ms_m + (1 - float(m_c)/100))) / (mh_m + 1))
                    m_p = min(((mw * ms_m) - m_h), ((m_h * mh_m) + (mw * float(m_c)/100) - mw))
                st.write(f"**{m_book.upper()} | {m_sport.upper()}**")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("HEDGE AMOUNT", f"${m_h:.0f}"); rc2.metric("NET PROFIT", f"${m_p:.2f}"); rc3.metric("ROI", f"{((m_p/mw)*100):.1f}%")
            except: st.error("INVALID NUMBERS.")
