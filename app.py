import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# --- PROFESSIONAL THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;600;700&family=Roboto+Mono&display=swap');
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

# --- RESTORED ORIGINAL SPORTS MANIFEST ---
sports_map = {
    "WNBA": "basketball_wnba",
    "MLB": "baseball_mlb",
    "FIFA World Cup": "soccer_fifa_world_cup"
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

# --- HELPER: SAFE STRING TO BOOSTER ARRAY PARSER ---
def parse_boosters(input_str):
    if not input_str.strip():
        return [0]
    try:
        vals = [int(x.strip()) for x in input_str.split(",") if x.strip().isdigit()]
        return vals if vals else [0]
    except:
        return [0]

# --- UNIVERSAL SCAN ENGINE (2-WAY & 3-WAY MULTI-BOOSTER CAPABLE) ---
def run_promo_scan(p):
    if not p['hedge_books']:
        allowed_hedge_keys = [v for k, v in book_map.items() if v != book_map[p['book']]]
    else:
        allowed_hedge_keys = [book_map[b] for b in p['hedge_books'] if book_map[b] != book_map[p['book']]]

    source_book_key = book_map[p['book']]
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
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

                    # Harvest lines from acceptable books
                    flat_odds = []
                    for bm in game['bookmakers']:
                        if bm['key'] == source_book_key or bm['key'] in allowed_hedge_keys:
                            outcomes = bm['markets'][0]['outcomes']
                            for o in outcomes:
                                flat_odds.append({
                                    'book_key': bm['key'], 
                                    'book_title': bm['title'], 
                                    'team': o['name'], 
                                    'price': o['price']
                                })
                    
                    if not flat_odds: 
                        continue

                    unique_outcomes = list(set([o['team'] for o in flat_odds]))

                    # ----------------------------------------------------
                    # INTERCEPT: 3-WAY SOCCER MARKETS
                    # ----------------------------------------------------
                    if len(unique_outcomes) == 3:
                        t1, t2, draw = unique_outcomes[0], unique_outcomes[1], unique_outcomes[2]
                        
                        odds_t1 = [o for o in flat_odds if o['team'] == t1]
                        odds_t2 = [o for o in flat_odds if o['team'] == t2]
                        odds_draw = [o for o in flat_odds if o['team'] == draw]

                        for o1 in odds_t1:
                            for o2 in odds_t2:
                                for o3 in odds_draw:
                                    # Cross-book validity checkpoint
                                    if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']:
                                        continue
                                    
                                    # Ensure the source book is anchored as one of the legs
                                    if source_book_key not in [o1['book_key'], o2['book_key'], o3['book_key']]:
                                        continue

                                    # Gather specific book inventories mapped into payload
                                    b1_list = p['all_boosts'].get(o1['book_key'], [0])
                                    b2_list = p['all_boosts'].get(o2['book_key'], [0])
                                    b3_list = p['all_boosts'].get(o3['book_key'], [0])

                                    best_3way_profit = -999999
                                    best_3way_record = {}

                                    for b1 in b1_list:
                                        for b2 in b2_list:
                                            for b3 in b3_list:
                                                
                                                # Strat modifications
                                                if p['strat'] == "Profit Boost (%)":
                                                    m1 = get_multiplier(o1['price']) * (1 + (b1 / 100))
                                                    m2 = get_multiplier(o2['price']) * (1 + (b2 / 100))
                                                    m3 = get_multiplier(o3['price']) * (1 + (b3 / 100))
                                                    
                                                    # Run standard Arbitrage optimization logic using fixed base budget
                                                    target_pay = p['wager'] * (1 + m1)
                                                    h2_stake = target_pay / (1 + m2)
                                                    h3_stake = target_pay / (1 + m3)
                                                    exact_profit = target_pay - p['wager'] - h2_stake - h3_stake
                                                
                                                elif p['strat'] == "Bonus Bet":
                                                    # Bonus bet typically applied on the main source book anchor leg
                                                    m1 = get_multiplier(o1['price']) if o1['book_key'] != source_book_key else get_multiplier(o1['price'])
                                                    m2 = get_multiplier(o2['price'])
                                                    m3 = get_multiplier(o3['price'])
                                                    
                                                    target_pay = p['wager'] * get_multiplier(o1['price']) if o1['book_key'] == source_book_key else p['wager'] * m1
                                                    h2_stake = target_pay / (1 + m2)
                                                    h3_stake = target_pay / (1 + m3)
                                                    exact_profit = target_pay - (0 if o1['book_key'] == source_book_key else p['wager']) - h2_stake - h3_stake
                                                
                                                else: # No-Sweat Bet
                                                    mc = 0.65
                                                    m1 = get_multiplier(o1['price'])
                                                    m2 = get_multiplier(o2['price'])
                                                    m3 = get_multiplier(o3['price'])
                                                    
                                                    target_pay = p['wager'] * (1 + m1)
                                                    h2_stake = (target_pay - (p['wager'] * mc)) / (1 + m2)
                                                    h3_stake = (target_pay - (p['wager'] * mc)) / (1 + m3)
                                                    exact_profit = target_pay - p['wager'] - h2_stake - h3_stake

                                                if exact_profit > best_3way_profit:
                                                    best_3way_profit = exact_profit
                                                    best_3way_record = {
                                                        'profit': exact_profit, 'w1': p['wager'], 'w2': h2_stake, 'w3': h3_stake,
                                                        'b1': b1, 'b2': b2, 'b3': b3
                                                    }

                                    if best_3way_profit > -10.0:
                                        all_opps.append({
                                            "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                                            "sport": sport_label,
                                            "market_type": "3-way",
                                            "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                            "exact_profit": best_3way_record['profit'],
                                            "wager": p['wager'],
                                            "strat": p['strat'],
                                            "b1_label": best_3way_record['b1'], "b2_label": best_3way_record['b2'], "b3_label": best_3way_record['b3'],
                                            "s_team": o1['team'], "s_book": o1['book_title'], "s_price": o1['price'], "exact_w1": best_3way_record['w1'],
                                            "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "exact_hedge1": best_3way_record['w2'],
                                            "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "exact_hedge2": best_3way_record['w3'],
                                        })

                    # ----------------------------------------------------
                    # STANDARD: 2-WAY MARKETS
                    # ----------------------------------------------------
                    elif len(unique_outcomes) == 2:
                        source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                        hedge_odds = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]
                        
                        for s in source_odds:
                            hedge_teams = [t for t in unique_outcomes if t != s['team']]
                            if len(hedge_teams) != 1: continue
                            opp_team = hedge_teams[0]
                            
                            eligible = [h for h in hedge_odds if h['team'] == opp_team]
                            if eligible:
                                best_h = max(eligible, key=lambda x: x['price'])
                                sm = get_multiplier(s['price'])
                                hm = get_multiplier(best_h['price'])
                                
                                best_2way_profit = -999999
                                best_2way_record = {}
                                
                                # Access current source book booster inventory options
                                active_boosters = p['all_boosts'].get(source_book_key, [0])
                                
                                for b_val in active_boosters:
                                    if p['strat'] == "Profit Boost (%)":
                                        bsm = sm * (1 + (b_val / 100))
                                        target_payout = p['wager'] * (1 + bsm)
                                        raw_h = target_payout / (1 + hm)
                                        exact_profit = target_payout - p['wager'] - raw_h
                                        
                                    elif p['strat'] == "Bonus Bet":
                                        target_payout = p['wager'] * sm
                                        raw_h = target_payout / (1 + hm)
                                        exact_profit = target_payout - raw_h
                                        
                                    else:  # No-Sweat Bet
                                        mc = 0.65
                                        target_payout = p['wager'] * (1 + sm)
                                        raw_h = (target_payout - (p['wager'] * mc)) / (1 + hm)
                                        exact_profit = target_payout - p['wager'] - raw_h
                                        
                                    if exact_profit > best_2way_profit:
                                        best_2way_profit = exact_profit
                                        best_2way_record = {"profit": exact_profit, "hedge": raw_h, "used_boost": b_val}

                                if best_2way_profit > -10.0:
                                    all_opps.append({
                                        "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                                        "sport": sport_label,
                                        "market_type": "2-way",
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "exact_profit": best_2way_record['profit'],
                                        "exact_hedge": best_2way_record['hedge'],
                                        "s_team": s['team'], "s_book": s['book_title'], "s_price": s['price'],
                                        "h_book": best_h['book_title'], "h_team": best_h['team'], "h_price": best_h['price'],
                                        "wager": p['wager'],
                                        "strat": p['strat'],
                                        "used_boost": best_2way_record['used_boost']
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
        for i, op in enumerate(sorted_opps[:15]):
            if op['strat'] == "Bonus Bet":
                conv_rate = (op['exact_profit'] / op['wager']) * 100
                conv_str = f" | {conv_rate:.1f}% Conversion"
            elif op['strat'] == "Profit Boost (%)" and op.get('market_type') == "2-way" and op.get('used_boost', 0) > 0:
                conv_str = f" | Using {op['used_boost']}% Boost"
            elif op.get('market_type') == "3-way":
                conv_str = f" | 3-Way Cross-Optimized Match"
            else:
                conv_str = ""

            header_title = f"RANK {i+1} | {op['time']} | {op['game']}{conv_str} | Profit: ${op['exact_profit']:.2f}"
            
            with st.expander(header_title):
                st.write(f"**Full Match Details:** {op['sport']} | {op['game']} | Start Time: {op['time']}")
                
                if op.get('market_type') == "3-way":
                    c_main, c_hedge1, c_hedge2 = st.columns([1.2, 1.2, 1.2])
                    b1_lbl = f" ({op['b1_label']}% Boost)" if op['b1_label'] > 0 else ""
                    b2_lbl = f" ({op['b2_label']}% Boost)" if op['b2_label'] > 0 else ""
                    b3_lbl = f" ({op['b3_label']}% Boost)" if op['b3_label'] > 0 else ""
                    
                    with c_main:
                        st.caption(f"LEG 1 BOOK: **{op['s_book'].upper()}{b1_lbl}**")
                        st.info(f"Bet **${op['exact_w1']:.2f}** on **{op['s_team']}** @ **{op['s_price']:+}**")
                    with c_hedge1:
                        st.caption(f"LEG 2 BOOK: **{op['h1_book'].upper()}{b2_lbl}**")
                        st.success(f"Bet **${op['exact_hedge1']:.2f}** on **{op['h1_team']}** @ **{op['h1_price']:+}**")
                    with c_hedge2:
                        st.caption(f"LEG 3 BOOK: **{op['h2_book'].upper()}{b3_lbl}**")
                        st.success(f"Bet **${op['exact_hedge2']:.2f}** on **{op['h2_team']}** @ **{op['h2_price']:+}**")
                        st.metric("Optimal Profit", f"${op['exact_profit']:.2f}")
                
                else:
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

# --- NEW ASYMMETRICAL BOOSTER STATE SUBSURFACE MANAGEMENT ---
st.markdown("### 🛠️ Multi-Book Booster Matrix Configuration")
col_b1, col_b2, col_b3, col_b4 = st.columns(4)
with col_b1:
    dk_v = st.text_input("DraftKings Boosts (%)", value="0, 25", help="Comma separated values like 0, 25, 50")
with col_b2:
    fd_v = st.text_input("FanDuel Boosts (%)", value="0, 50")
with col_b3:
    espn_v = st.text_input("theScore / ESPN Boosts (%)", value="0")
with col_b4:
    mgm_v = st.text_input("BetMGM Boosts (%)", value="0")

global_boost_map = {
    'draftkings': parse_boosters(dk_v),
    'fanduel': parse_boosters(fd_v),
    'espnbet': parse_boosters(espn_v),
    'betmgm': parse_boosters(mgm_v)
}

st.write("")

with st.expander("Promo Configuration", expanded=True):
    with st.form("promo_form", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=0.0, value=100.0, step=10.0)
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
        temp_p = {"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "all_boosts": global_boost_map}
        results = run_promo_scan(temp_p)
        display_results(results, temp_p)

if add_to_q:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "all_boosts": global_boost_map})

if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        q_col1, q_col2 = st.columns([9.2, 0.8])
        with q_col1:
            hedge_label = ", ".join(p['hedge_books']) if p['hedge_books'] else "ALL"
            st.info(f"**{p['book'].upper()}** vs **{hedge_label}** | {p['strat']} | ${p['wager']} | {', '.join(p['sports'])}")
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
