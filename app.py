import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

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
st.title("Promo Converter")
quota_placeholder = st.empty()
quota_placeholder.markdown("**Quota:** Not scanned yet")

# --- INPUT AREA ---
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
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book_display = st.radio("Source Book (Promo)", ["DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            source_book = book_map[source_book_display]
        with col_hedge:
            hedge_book_display = st.radio("Hedge Book (Filter)", ["All Books", "DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            hedge_filter = book_map[hedge_book_display]

        st.divider()
        
        st.write("**Select Sports to Scan:**")
        sports_map = {
            "NBA": "basketball_nba", 
            "NCAAB": "basketball_ncaab", 
            "NCAAW": "basketball_wncaab",
            "NHL": "icehockey_nhl",
            "Boxing": "boxing_boxing",
            "MMA": "mma_mixed_martial_arts" 
        }
        sport_labels = list(sports_map.keys())
        selected_sports = []

        all_clicked = st.checkbox("Select All", value=st.session_state.select_all)

        sport_cols = st.columns(len(sport_labels))
        for i, label in enumerate(sport_labels):
            with sport_cols[i]:
                if st.checkbox(label, value=all_clicked, key=f"cb_{label}"):
                    selected_sports.append(sports_map[label])

        st.divider()
        col_w, col_b = st.columns([1, 1])
        with col_w:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")
        with col_b:
            boost_val_raw = st.text_input("Boost (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
            
        run_scan = st.form_submit_button("Run Optimizer", use_container_width=True)

# --- SCAN LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key! Please add ODDS_API_KEY to your Streamlit secrets.")
    elif not selected_sports:
        st.warning("Please select at least one sport.")
    else:
        try:
            max_wager = float(max_wager_raw)
            boost_val = float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,williamhill_us,caesars,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner("Scanning markets..."):
            for sport in selected_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    quota_placeholder.markdown(f"**Quota Remaining:** {res.headers.get('x-requests-remaining', 'N/A')}")
                    games = res.json()
                    for game in games:
                        commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if commence_time <= now_utc: continue 
                        
                        source_odds = []
                        hedge_odds = []

                        for book in game['bookmakers']:
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book_name': book['title'], 'team': o['name'], 'price': o['price']}
                                    if book['key'] == source_book:
                                        source_odds.append(entry)
                                    if hedge_filter == "allbooks" or book['key'] == hedge_filter:
                                        hedge_odds.append(entry)

                        for s in source_odds:
                            opp_team = next((t for t in [game['home_team'], game['away_team']] if t != s['team']), None)
                            eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                            if not eligible_hedges: continue
                            
                            best_h = max(eligible_hedges, key=lambda x: x['price'])
                            
                            s_m = get_multiplier(s['price'])
                            h_m = get_multiplier(best_h['price'])

                            if promo_type == "Profit Boost (%)":
                                b_s_m = s_m * (1 + (boost_val / 100))
                                h_needed = round((max_wager * (1 + b_s_m)) / (1 + h_m))
                                profit = min(((max_wager * b_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                rating = profit
                            elif promo_type == "Bonus Bet":
                                h_needed = round((max_wager * s_m) / (1 + h_m))
                                profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                rating = (profit / max_wager) * 100
                            else: # No-Sweat Math
                                mc = 0.70 
                                h_needed = round((max_wager * (s_m + (1 - mc))) / (h_m + 1))
                                profit = min(((max_wager * s_m) - h_needed), ((h_needed * h_m) + (max_wager * mc) - max_wager))
                                rating = (profit / max_wager) * 100

                            if profit > -5.0:
                                s_display = sport.split('_')[-1].upper()
                                all_opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "sport": s_display,
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                    "profit": profit, "hedge": h_needed, "rating": rating,
                                    "s_team": s['team'], "s_book": s['book_name'], "s_price": s['price'],
                                    "h_team": best_h['team'], "h_book": best_h['book_name'], "h_price": best_h['price']
                                })

        st.write("### Top 10 Opportunities")
        top_10 = sorted(all_opps, key=lambda x: x['rating'], reverse=True)[:10]

        if len(top_10) >= 1:
            all_hedge_vals = sorted([op['hedge'] for op in top_10])
            green_cutoff = all_hedge_vals[min(2, len(all_hedge_vals)-1)]

            for i, op in enumerate(top_10):
                dot = "🟢" if op['hedge'] <= green_cutoff else "🔴"
                roi = op['rating'] if promo_type != "Profit Boost (%)" else (op['profit'] / max_wager) * 100
                title = f"{dot} **Rank {i+1}** ｜ {op['sport']} ({op['time']}) ｜ Profit: ${op['profit']:.2f} ({int(roi)}%) ｜ Hedge: ${op['hedge']:.0f}"
                
                with st.expander(title):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.caption(f"SOURCE: {op['s_book'].upper()}")
                        st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                    with c2:
                        st.caption(f"HEDGE: {op['h_book'].upper()}")
                        st.success(f"Bet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
                        st.write(f"**{op['game']}**")
        else:
            st.info("No viable opportunities found.")

# --- MANUAL CALCULATOR ---
st.write("---")
st.subheader("Manual Calculator")
with st.expander("Open Manual Calculator", expanded=False):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True, key="m_strat")
        m_book = st.text_input("Book Name", value="DraftKings")
        m_sport = st.text_input("Sport", value="NBA")
        
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_s_p = st.text_input("Source Odds", value="250")
            m_w = st.text_input("Wager ($)", value="50.0")
            m_b = st.text_input("Boost %", value="50") if m_promo == "Profit Boost (%)" else "0"
        with m_col2:
            m_h_p = st.text_input("Hedge Odds", value="-280")
            m_c = st.text_input("Refund %", value="70") if m_promo == "No-Sweat Bet" else "0"
        
        if st.form_submit_button("Calculate Hedge", use_container_width=True):
            try:
                ms_p, mw, mh_p = float(m_s_p), float(m_w), float(m_h_p)
                ms_m = get_multiplier(ms_p)
                mh_m = get_multiplier(mh_p)
                
                if m_promo == "Profit Boost (%)":
                    boosted_m = ms_m * (1 + float(m_b)/100)
                    m_h = round((mw * (1 + boosted_m)) / (1 + mh_m))
                    m_p = min(((mw * boosted_m) - m_h), ((m_h * mh_m) - mw))
                elif m_promo == "Bonus Bet":
                    m_h = round((mw * ms_m) / (1 + mh_m))
                    m_p = min(((mw * ms_m) - m_h), (m_h * mh_m))
                else: 
                    mc = float(m_c)/100 
                    m_h = round((mw * (ms_m + (1 - mc))) / (mh_m + 1))
                    m_p = min(((mw * ms_m) - m_h), ((m_h * mh_m) + (mw * mc) - mw))
                
                st.write(f"**{m_book} | {m_sport}**")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Hedge Amount", f"${m_h:.0f}")
                rc2.metric("Net Profit", f"${m_p:.2f}")
                rc3.metric("ROI", f"{((m_p/mw)*100):.1f}%")
            except: 
                st.error("Please enter valid numbers.")

# --- AUTOMATED MULTI-PROMO OPTIMIZER ---
st.write("---")
st.subheader("🔄 Multi-Promo Scanner (Auto-API)")
with st.expander("Find Top 10 Multi-Promo Opportunities", expanded=True):
    with st.form("auto_multi_promo"):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Side A (Promo 1)")
            auto_strat_a = st.selectbox("Type A", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="asa")
            auto_book_a = st.selectbox("Book A", ["draftkings", "fanduel", "betmgm", "espnbet"], key="aba")
            auto_wager_a = st.number_input("Wager/Max A ($)", value=50.0)
            auto_boost_a = st.number_input("Boost A %", value=50) if auto_strat_a == "Profit Boost (%)" else 0
            
        with col_r:
            st.markdown("### Side B (Promo 2)")
            auto_strat_b = st.selectbox("Type B", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Cash (No Promo)"], key="asb")
            auto_book_b = st.selectbox("Book B", ["fanduel", "draftkings", "betmgm", "espnbet", "bet365"], key="abb")
            auto_boost_b = st.number_input("Boost B %", value=0) if auto_strat_b == "Profit Boost (%)" else 0

        st.info("This will scan live games and find the best 10 matches where these two promos interact.")
        run_multi_scan = st.form_submit_button("Scan Multi-Promo Markets", use_container_width=True)

if run_multi_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("API Key missing.")
    else:
        results = []
        # We scan all sports from your main list
        with st.spinner(f"Matching {auto_book_a} promos against {auto_book_b}..."):
            for sport in selected_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': f"{auto_book_a},{auto_book_b}"}
                res = requests.get(url, params=params)
                
                if res.status_code == 200:
                    games = res.json()
                    for game in games:
                        odds_a, odds_b = [], []
                        for bm in game['bookmakers']:
                            for m in bm['markets']:
                                for o in m['outcomes']:
                                    d = {'team': o['name'], 'price': o['price']}
                                    if bm['key'] == auto_book_a: odds_a.append(d)
                                    if bm['key'] == auto_book_b: odds_b.append(d)
                        
                        # Compare outcomes (Team 1 on Book A vs Team 2 on Book B)
                        for s_a in odds_a:
                            for s_b in odds_b:
                                if s_a['team'] == s_b['team']: continue # Can't bet same side
                                
                                m_a, m_b = get_multiplier(s_a['price']), get_multiplier(s_b['price'])
                                
                                # Logic for Side A
                                if auto_strat_a == "Profit Boost (%)":
                                    win_a, loss_a = (auto_wager_a * m_a * (1 + auto_boost_a/100)), -auto_wager_a
                                elif auto_strat_a == "Bonus Bet":
                                    win_a, loss_a = (auto_wager_a * m_a), 0
                                else: # No-Sweat
                                    win_a, loss_a = (auto_wager_a * m_a), -auto_wager_a * 0.30

                                # Calculate Optimal Hedge for Side B
                                if auto_strat_b == "Profit Boost (%)":
                                    w_b = (win_a - loss_a) / (m_b * (1 + auto_boost_b/100) + 1)
                                    win_b_total = (w_b * m_b * (1 + auto_boost_b/100)) + loss_a
                                elif auto_strat_b == "Bonus Bet":
                                    w_b = (win_a - loss_a) / m_b
                                    win_b_total = (w_b * m_b) + loss_a
                                elif auto_strat_b == "No-Sweat Bet":
                                    w_b = (win_a - loss_a) / (m_b + 0.70)
                                    win_b_total = (w_b * m_b) + loss_a
                                else: # Pure Cash
                                    w_b = (win_a - loss_a) / (m_b + 1)
                                    win_b_total = (w_b * m_b) + loss_a

                                profit = (win_a - w_b + win_b_total) / 2 # Balanced profit
                                
                                results.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "profit": profit, "w_b": w_b,
                                    "a_team": s_a['team'], "a_odds": s_a['price'],
                                    "b_team": s_b['team'], "b_odds": s_b['price']
                                })

        # Sort and Display Top 10
        top_results = sorted(results, key=lambda x: x['profit'], reverse=True)[:10]
        for item in top_results:
            with st.container():
                st.markdown(f"#### {item['game']} | Profit: **${item['profit']:.2f}**")
                c1, c2 = st.columns(2)
                c1.write(f"**{auto_book_a}**: ${auto_wager_a} on {item['a_team']} @ {item['a_odds']:+}")
                c2.write(f"**{auto_book_b}**: ${item['w_b']:.2f} on {item['b_team']} @ {item['b_odds']:+}")
                st.divider()

