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

# --- SHARED DATA ---
book_map = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "BetMGM": "betmgm",
    "theScore / ESPN": "espnbet",
    "Bet365": "bet365",
    "Caesars": "caesars",
    "All Books": "allbooks"
}

sports_map = {
    "NBA": "basketball_nba", 
    "NCAAB": "basketball_ncaab", 
    "NCAAW": "basketball_wncaab",
    "NHL": "icehockey_nhl", 
    "Boxing": "boxing_boxing", 
    "MMA": "mma_mixed_martial_arts" 
}
sport_labels = list(sports_map.keys())

# --- HEADER AREA ---
st.title("Promo Converter")
quota_placeholder = st.empty()
quota_placeholder.markdown("**Quota:** Not scanned yet")

# --- SECTION 1: PROMO CONVERTER (GLOBAL SCANNER) ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book_display = st.radio("Source book (Promo)", ["DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            source_book = book_map[source_book_display]
        with col_hedge:
            hedge_book_display = st.radio("Hedge book (Filter)", ["All Books", "DraftKings", "FanDuel", "BetMGM", "theScore / ESPN"], horizontal=True)
            hedge_filter = book_map[hedge_book_display]

        st.divider()
        st.write("**Select sports to scan:**")
        selected_sports = []
        all_clicked = st.checkbox("Select all", value=st.session_state.select_all)
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
            
        run_scan = st.form_submit_button("Run optimizer", use_container_width=True)

if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API key!")
    elif not selected_sports:
        st.warning("Please select at least one sport.")
    else:
        try:
            max_wager, boost_val = float(max_wager_raw), float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner("Scanning markets..."):
            for sport in selected_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': "draftkings,fanduel,betmgm,bet365,williamhill_us,caesars,fanatics,espnbet", 'oddsFormat': 'american'}
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    quota_placeholder.markdown(f"**Quota remaining:** {res.headers.get('x-requests-remaining', 'N/A')}")
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

        st.write("### Top 10 opportunities")
        top_10 = sorted(all_opps, key=lambda x: x['rating'], reverse=True)[:10]
        for i, op in enumerate(top_10):
            roi = op['rating'] if promo_type != "Profit Boost (%)" else (op['profit'] / max_wager) * 100
            with st.expander(f"Rank {i+1} ｜ {op['sport']} ({op['time']}) ｜ Profit: ${op['profit']:.2f} ({int(roi)}%)"):
                c1, c2, c3 = st.columns(3)
                c1.info(f"**{op['s_book'].upper()}**\n\nBet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                c2.success(f"**{op['h_book'].upper()}**\n\nBet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                c3.metric("Net profit", f"${op['profit']:.2f}")

# --- SECTION 2: MULTI-PROMO OPTIMIZER ---
st.write("---")
st.subheader("Multi-promo optimizer")
with st.expander("Combine two different promos (Auto-scan)", expanded=True):
    with st.form("multi_promo_scan_form"):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Side A (Promo 1)")
            a_strat = st.selectbox("Strategy A", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="as1")
            a_book = st.selectbox("Book A", ["draftkings", "fanduel", "betmgm", "espnbet"], key="ab1")
            a_wager_max = st.number_input("Max wager A ($)", value=50.0)
            a_boost = st.number_input("Boost A (%)", value=50) if a_strat == "Profit Boost (%)" else 0
        with col_r:
            st.markdown("### Side B (Promo 2)")
            b_strat = st.selectbox("Strategy B", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Cash (No promo)"], key="as2")
            b_book = st.selectbox("Book B", ["fanduel", "draftkings", "betmgm", "espnbet"], key="ab2")
            b_wager_max = st.number_input("Max wager B ($)", value=50.0)
            b_boost = st.number_input("Boost B (%)", value=0) if b_strat == "Profit Boost (%)" else 0

        st.write("**Select sports for multi-scan:**")
        m_selected = st.multiselect("Sports type", sport_labels, default=["NBA", "NHL"])

        run_multi_scan = st.form_submit_button("Run multi-promo scanner", use_container_width=True)

if run_multi_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    multi_results = []
    now_utc = datetime.now(timezone.utc)
    with st.spinner("Finding cross-book matches..."):
        for label in m_selected:
            sport = sports_map[label]
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'bookmakers': f"{a_book},{b_book}", 'oddsFormat': 'american'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                games = res.json()
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    if commence_time <= now_utc: continue 
                    odds_a, odds_b = [], []
                    for bm in game['bookmakers']:
                        for m in bm['markets']:
                            for o in m['outcomes']:
                                if bm['key'] == a_book: odds_a.append(o)
                                if bm['key'] == b_book: odds_b.append(o)
                    
                    for o_a in odds_a:
                        for o_b in odds_b:
                            if o_a['name'] == o_b['name']: continue 
                            m_a, m_b = get_multiplier(o_a['price']), get_multiplier(o_b['price'])
                            eff_m_a = m_a * (1 + a_boost/100) if a_strat == "Profit Boost (%)" else m_a
                            loss_a_val = 0 if a_strat == "Bonus Bet" else (0.30 if a_strat == "No-Sweat Bet" else 1.0)
                            eff_m_b = m_b * (1 + b_boost/100) if b_strat == "Profit Boost (%)" else m_b
                            loss_b_val = 0 if b_strat == "Bonus Bet" else (0.30 if b_strat == "No-Sweat Bet" else 1.0)

                            ratio = (eff_m_a + loss_a_val) / (eff_m_b + loss_b_val)
                            final_w_a = a_wager_max
                            final_w_b = final_w_a * ratio
                            if final_w_b > b_wager_max:
                                final_w_b = b_wager_max
                                final_w_a = final_w_b / ratio

                            profit = (final_w_a * eff_m_a) - (final_w_b * (1.0 if b_strat in ["Cash (No promo)", "Profit Boost (%)"] else (0.30 if b_strat == "No-Sweat Bet" else 0)))
                            multi_results.append({
                                "game": f"{game['away_team']} vs {game['home_team']}",
                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                "profit": profit, "w_a": final_w_a, "w_b": final_w_b, "a_team": o_a['name'], "a_odds": o_a['price'],
                                "b_team": o_b['name'], "b_odds": o_b['price'], "sport": label
                            })

    top_multi = sorted(multi_results, key=lambda x: x['profit'], reverse=True)[:10]
    for i, item in enumerate(top_multi):
        with st.expander(f"Multi-rank {i+1} ｜ {item['sport']} ({item['time']}) ｜ Profit: ${item['profit']:.2f}"):
            c1, c2, c3 = st.columns(3)
            c1.info(f"**{a_book.upper()}**\n\nBet **${item['w_a']:.2f}** on {item['a_team']} @ **{item['a_odds']:+}**")
            c2.success(f"**{b_book.upper()}**\n\nBet **${item['w_b']:.2f}** on {item['b_team']} @ **{item['b_odds']:+}**")
            c3.metric("Net profit", f"${item['profit']:.2f}")

# --- SECTION 3: SINGLE PROMO TARGETER ---
st.write("---")
st.subheader("Single promo targeter")
with st.expander("Find the best play for a specific promo", expanded=True):
    with st.form("single_target_form"):
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            t_book = st.selectbox("Sportsbook", ["draftkings", "fanduel", "betmgm", "espnbet", "bet365"], key="t1")
            t_strat = st.selectbox("Boost type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="t2")
            t_wager = st.number_input("Max wager ($)", value=50.0)
        with t_col2:
            t_boost = st.number_input("Boost (%)", value=50) if t_strat == "Profit Boost (%)" else 0
            t_hedge_book = st.selectbox("Hedge against", ["All Books", "draftkings", "fanduel", "betmgm", "espnbet"], key="t3")
            t_target_sports = st.multiselect("Sports type", sport_labels, default=["NBA", "NHL"], key="t4")

        run_target_scan = st.form_submit_button("Find best play for this boost", use_container_width=True)

if run_target_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    target_results = []
    now_utc = datetime.now(timezone.utc)
    with st.spinner("Searching specific markets..."):
        for label in t_target_sports:
            sport = sports_map[label]
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h', 'oddsFormat': 'american'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                games = res.json()
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    if commence_time <= now_utc: continue 
                    s_odds, h_odds = [], []
                    for bm in game['bookmakers']:
                        for m in bm['markets']:
                            for o in m['outcomes']:
                                if bm['key'] == t_book: s_odds.append(o)
                                if t_hedge_book == "All Books" or bm['key'] == t_hedge_book: h_odds.append({'o': o, 'name': bm['title']})
                    
                    for so in s_odds:
                        opp_team = next((t for t in [game['home_team'], game['away_team']] if t != so['name']), None)
                        eligible = [ho for ho in h_odds if ho['o']['name'] == opp_team]
                        if eligible:
                            best_h = max(eligible, key=lambda x: x['o']['price'])
                            sm, hm = get_multiplier(so['price']), get_multiplier(best_h['o']['price'])
                            if t_strat == "Profit Boost (%)":
                                hamt = (t_wager * (1 + sm*(1+t_boost/100))) / (1 + hm)
                                prof = (t_wager * sm * (1+t_boost/100)) - hamt
                            elif t_strat == "Bonus Bet":
                                hamt = (t_wager * sm) / (1 + hm)
                                prof = (t_wager * sm) - hamt
                            else:
                                hamt = (t_wager * (sm + 0.30)) / (hm + 1)
                                prof = (t_wager * sm) - hamt
                            
                            target_results.append({
                                "game": f"{game['away_team']} vs {game['home_team']}",
                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                "profit": prof, "hamt": hamt, "s_team": so['name'], "s_price": so['price'],
                                "h_team": best_h['o']['name'], "h_book": best_h['name'], "h_price": best_h['o']['price'], "sport": label
                            })

    top_targets = sorted(target_results, key=lambda x: x['profit'], reverse=True)[:10]
    for i, res in enumerate(top_targets):
        with st.expander(f"Target Option {i+1} ｜ {res['sport']} ({res['time']}) ｜ Profit: ${res['profit']:.2f}"):
            c1, c2, c3 = st.columns(3)
            c1.info(f"**{t_book.upper()}**\n\nBet **${t_wager}** on {res['s_team']} @ **{res['s_price']:+}**")
            c2.success(f"**{res['h_book'].upper()}**\n\nBet **${res['hamt']:.2f}** on {res['h_team']} @ **{res['h_price']:+}**")
            c3.metric("Net profit", f"${res['profit']:.2f}")

# --- SECTION 4: MANUAL CALCULATOR ---
st.write("---")
st.subheader("Manual calculator")
with st.expander("Open manual calculator", expanded=False):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True, key="m_strat")
        m_book = st.text_input("Book name", value="DraftKings")
        m_sport = st.text_input("Sport", value="NBA")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            ms_p = st.text_input("Source odds", value="250")
            mw = st.text_input("Wager ($)", value="50.0")
            mb = st.text_input("Boost %", value="50") if m_promo == "Profit Boost (%)" else "0"
        with m_col2:
            mh_p = st.text_input("Hedge odds", value="-280")
            mc = st.text_input("Refund %", value="70") if m_promo == "No-Sweat Bet" else "0"
        
        if st.form_submit_button("Calculate hedge", use_container_width=True):
            try:
                msp, m_w, mhp = float(ms_p), float(mw), float(mh_p)
                msm, mhm = get_multiplier(msp), get_multiplier(mhp)
                if m_promo == "Profit Boost (%)":
                    mh = round((m_w * (1 + msm * (1 + float(mb)/100))) / (1 + mhm))
                    mp = min(((m_w * msm * (1 + float(mb)/100)) - mh), ((mh * mhm) - m_w))
                elif m_promo == "Bonus Bet":
                    mh = round((m_w * msm) / (1 + mhm))
                    mp = min(((m_w * msm) - mh), (mh * mhm))
                else: 
                    mh = round((m_w * (msm + (1 - float(mc)/100))) / (mhm + 1))
                    mp = min(((m_w * msm) - mh), ((mh * mhm) + (m_w * float(mc)/100) - m_w))
                st.write(f"**{m_book} | {m_sport}**")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Hedge amount", f"${mh:.0f}"); rc2.metric("Net profit", f"${mp:.2f}"); rc3.metric("ROI", f"{((mp/m_w)*100):.1f}%")
            except: st.error("Invalid numbers.")
