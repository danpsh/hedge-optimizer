import streamlit as st
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter Master", layout="wide")

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
    .soccer-header {
        background-color: #fff7ed;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 5px solid #ea580c;
    }
    .betget-header {
        background-color: #f0fdf4;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 5px solid #16a34a;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")
LOCAL_TZ = ZoneInfo("America/Chicago")  # auto-handles CST/CDT (replaces hardcoded -6h)

def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

def fmt_local(commence_utc):
    return commence_utc.astimezone(LOCAL_TZ).strftime("%m/%d %I:%M %p")

book_map = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet",
    "BetMGM": "betmgm"
}

# Split sports: standard scanner = 2-way US markets; soccer module = 3-way
us_sports_map = {
    "WNBA": "basketball_wnba",
    "MLB": "baseball_mlb"
}
soccer_map = {
    "FIFA World Cup": "soccer_fifa_world_cup"
}
all_sports_map = {**us_sports_map, **soccer_map}  # Bet & Get searches everything

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

def parse_boosters(input_str):
    if not input_str.strip():
        return [0]
    vals = []
    for x in input_str.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            vals.append(float(x))  # allows decimals like 12.5
        except ValueError:
            continue
    return vals if vals else [0]

# ========================================================
# STANDARD SCANNER ENGINE (2-WAY ONLY)
# ========================================================
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
            sport_key = us_sports_map[sport_label]
            games, remaining = fetch_odds(sport_key)

            if games:
                st.session_state.api_quota = remaining
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    if commence_time <= now_utc or commence_time > lookahead_limit:
                        continue

                    flat_odds = []
                    for bm in game['bookmakers']:
                        if bm['key'] == source_book_key or bm['key'] in allowed_hedge_keys:
                            for o in bm['markets'][0]['outcomes']:
                                flat_odds.append({
                                    'book_key': bm['key'],
                                    'book_title': bm['title'],
                                    'team': o['name'],
                                    'price': o['price']
                                })

                    if not flat_odds:
                        continue
                    unique_outcomes = list(set([o['team'] for o in flat_odds]))

                    # 2-WAY MARKETS ONLY
                    if len(unique_outcomes) == 2:
                        source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                        hedge_odds = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]

                        for s in source_odds:
                            hedge_teams = [t for t in unique_outcomes if t != s['team']]
                            if len(hedge_teams) != 1:
                                continue
                            opp_team = hedge_teams[0]

                            eligible = [h for h in hedge_odds if h['team'] == opp_team]
                            if eligible:
                                best_h = max(eligible, key=lambda x: x['price'])
                                sm = get_multiplier(s['price'])
                                hm = get_multiplier(best_h['price'])

                                best_2way_profit = -999999
                                best_2way_record = {}
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
                                        "sport": sport_label, "market_type": "2-way",
                                        "time": fmt_local(commence_time),
                                        "exact_profit": best_2way_profit, "exact_hedge": best_2way_record['hedge'],
                                        "s_team": s['team'], "s_book": s['book_title'], "s_price": s['price'],
                                        "h_book": best_h['book_title'], "h_team": best_h['team'], "h_price": best_h['price'],
                                        "wager": p['wager'], "strat": p['strat'], "used_boost": best_2way_record['used_boost']
                                    })
            else:
                st.error(f"Could not fetch data for {sport_label}")
        status.update(label="Scan Complete", state="complete")
    return all_opps

# ========================================================
# SOCCER MATRIX ENGINE (3-WAY, 1-2 SOURCE BOOKS, EQUAL-PROFIT)
# ========================================================
def run_soccer_scan(cfg):
    source_keys = cfg['source_keys']          # 1 or 2 book keys that carry your promo
    budget = cfg['budget']                    # total stake spread across all 3 legs
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    opps = []

    with st.status(f"Scanning Soccer Matrix ({len(source_keys)}-source)...", expanded=False) as status:
        for sport_label in cfg['sports']:
            sport_key = soccer_map[sport_label]
            games, remaining = fetch_odds(sport_key)
            if not games:
                st.error(f"Could not fetch data for {sport_label}")
                continue
            st.session_state.api_quota = remaining

            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit:
                    continue

                flat_odds = []
                for bm in game['bookmakers']:
                    if bm['key'] in book_map.values():
                        for o in bm['markets'][0]['outcomes']:
                            flat_odds.append({
                                'book_key': bm['key'], 'book_title': bm['title'],
                                'team': o['name'], 'price': o['price']
                            })

                outcomes = list(set(o['team'] for o in flat_odds))
                if len(outcomes) != 3:
                    continue  # soccer 3-way only

                legs_by_outcome = [[o for o in flat_odds if o['team'] == t] for t in outcomes]

                best = None
                for l1 in legs_by_outcome[0]:
                    for l2 in legs_by_outcome[1]:
                        for l3 in legs_by_outcome[2]:
                            books = [l1['book_key'], l2['book_key'], l3['book_key']]
                            if len(set(books)) != 3:
                                continue  # each leg on a distinct book
                            # source constraint: all designated source books must appear
                            if not all(sk in books for sk in source_keys):
                                continue

                            # boosts apply only to legs placed on a source book
                            bl1 = cfg['boosts'].get(l1['book_key'], [0]) if l1['book_key'] in source_keys else [0]
                            bl2 = cfg['boosts'].get(l2['book_key'], [0]) if l2['book_key'] in source_keys else [0]
                            bl3 = cfg['boosts'].get(l3['book_key'], [0]) if l3['book_key'] in source_keys else [0]

                            for b1 in bl1:
                                for b2 in bl2:
                                    for b3 in bl3:
                                        d1 = 1 + get_multiplier(l1['price']) * (1 + b1 / 100)
                                        d2 = 1 + get_multiplier(l2['price']) * (1 + b2 / 100)
                                        d3 = 1 + get_multiplier(l3['price']) * (1 + b3 / 100)
                                        inv = (1 / d1) + (1 / d2) + (1 / d3)
                                        if inv <= 0:
                                            continue
                                        R = budget / inv          # guaranteed equal return
                                        s1, s2, s3 = R / d1, R / d2, R / d3
                                        profit = R - budget
                                        if best is None or profit > best['profit']:
                                            best = {
                                                'profit': profit, 'roi': profit / budget if budget else 0, 'R': R,
                                                'legs': [
                                                    {'book': l1['book_title'], 'team': l1['team'], 'price': l1['price'],
                                                     'stake': s1, 'boost': b1, 'is_source': l1['book_key'] in source_keys},
                                                    {'book': l2['book_title'], 'team': l2['team'], 'price': l2['price'],
                                                     'stake': s2, 'boost': b2, 'is_source': l2['book_key'] in source_keys},
                                                    {'book': l3['book_title'], 'team': l3['team'], 'price': l3['price'],
                                                     'stake': s3, 'boost': b3, 'is_source': l3['book_key'] in source_keys},
                                                ]
                                            }

                if best is not None:
                    opps.append({
                        "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                        "sport": sport_label, "time": fmt_local(commence_time),
                        "profit": best['profit'], "roi": best['roi'], "return": best['R'],
                        "budget": budget, "legs": best['legs']
                    })
        status.update(label="Soccer Matrix scan complete", state="complete")
    return opps

# ========================================================
# DEDICATED BET & GET SCAN ENGINE (unchanged)
# ========================================================
def run_bet_get_scan(bg):
    source_book_key = book_map[bg['book']]
    allowed_hedge_keys = [v for k, v in book_map.items() if v != source_book_key]
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    bg_opps = []

    projected_bonus_value = bg['bonus_val'] * 0.70

    with st.status(f"Hunting cheapest qualification routes for {bg['book']}...", expanded=False) as status:
        for sport_label in bg['sports']:
            sport_key = all_sports_map[sport_label]
            games, remaining = fetch_odds(sport_key)
            if not games:
                continue
            st.session_state.api_quota = remaining

            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit:
                    continue

                flat_odds = []
                for bm in game['bookmakers']:
                    if bm['key'] == source_book_key or bm['key'] in allowed_hedge_keys:
                        for o in bm['markets'][0]['outcomes']:
                            flat_odds.append({'book_key': bm['key'], 'book_title': bm['title'], 'team': o['name'], 'price': o['price']})

                unique_outcomes = list(set([o['team'] for o in flat_odds]))

                # 3-Way Bet & Get Logic
                if len(unique_outcomes) == 3:
                    odds_t1 = [o for o in flat_odds if o['team'] == unique_outcomes[0]]
                    odds_t2 = [o for o in flat_odds if o['team'] == unique_outcomes[1]]
                    odds_draw = [o for o in flat_odds if o['team'] == unique_outcomes[2]]

                    for o1 in odds_t1:
                        for o2 in odds_t2:
                            for o3 in odds_draw:
                                if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']:
                                    continue
                                if o1['book_key'] != source_book_key:
                                    continue

                                sm = get_multiplier(o1['price'])
                                hm1 = get_multiplier(o2['price'])
                                hm2 = get_multiplier(o3['price'])

                                target_payout = bg['wager'] * (1 + sm)
                                h1_stake = target_payout / (1 + hm1)
                                h2_stake = target_payout / (1 + hm2)

                                qualifying_loss = target_payout - bg['wager'] - h1_stake - h2_stake
                                net_promo_value = projected_bonus_value + qualifying_loss

                                bg_opps.append({
                                    "game": f"{game.get('away_team')} vs {game.get('home_team')}", "sport": sport_label, "market_type": "3-way", "time": fmt_local(commence_time),
                                    "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                                    "s_book": o1['book_title'], "s_team": o1['team'], "s_price": o1['price'], "s_wager": bg['wager'],
                                    "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "h1_wager": h1_stake,
                                    "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "h2_wager": h2_stake
                                })

                # 2-Way Bet & Get Logic
                elif len(unique_outcomes) == 2:
                    source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                    hedge_odds = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]

                    for s in source_odds:
                        opp_team = [t for t in unique_outcomes if t != s['team']][0]
                        eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                        if not eligible_hedges:
                            continue

                        best_h = max(eligible_hedges, key=lambda x: x['price'])
                        sm = get_multiplier(s['price'])
                        hm = get_multiplier(best_h['price'])

                        target_payout = bg['wager'] * (1 + sm)
                        h_stake = target_payout / (1 + hm)

                        qualifying_loss = target_payout - bg['wager'] - h_stake
                        net_promo_value = projected_bonus_value + qualifying_loss

                        bg_opps.append({
                            "game": f"{game.get('away_team')} vs {game.get('home_team')}", "sport": sport_label, "market_type": "2-way", "time": fmt_local(commence_time),
                            "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                            "s_book": s['book_title'], "s_team": s['team'], "s_price": s['price'], "s_wager": bg['wager'],
                            "h1_book": best_h['book_title'], "h1_team": best_h['team'], "h1_price": best_h['price'], "h1_wager": h_stake
                        })

        status.update(label="Bet & Get Optimization Complete", state="complete")
    return bg_opps

# ========================================================
# DISPLAY HELPERS
# ========================================================
def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} - {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)

    if not sorted_opps:
        st.warning("No profitable 2-way matches found.")
    else:
        for i, op in enumerate(sorted_opps[:15]):
            conv_str = f" | Using {op['used_boost']:g}% Boost" if op.get('used_boost', 0) > 0 else ""
            header_title = f"RANK {i+1} | {op['time']} | {op['game']}{conv_str} | Profit: ${op['exact_profit']:.2f}"

            with st.expander(header_title):
                c_main, c_hedge = st.columns([1.5, 2])
                with c_main:
                    st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['wager']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c_hedge:
                    st.success(f"**{op['h_book'].upper()}**\n\nStake: **${op['exact_hedge']:.2f}**\n\nLine: **{op['h_team']}** @ **{op['h_price']:+}**")
                st.metric("Net Arbitrage Profit", f"${op['exact_profit']:.2f}")

def display_soccer_results(opps, cfg):
    title = " + ".join(cfg['source_labels'])
    st.markdown(f"<div class='soccer-header'><h3>Soccer Matrix — {title} ({len(cfg['source_keys'])}-source)</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['profit'], reverse=True)

    if not sorted_opps:
        st.warning("No 3-way soccer matches found for these books/leagues.")
        return

    for i, op in enumerate(sorted_opps[:15]):
        roi = op['roi'] * 100
        header = f"RANK {i+1} | {op['time']} | {op['game']} | Profit: ${op['profit']:.2f} ({roi:+.1f}%)"
        with st.expander(header):
            st.caption(f"{op['sport']} | Total deployed: ${op['budget']:.2f} | Guaranteed return (any outcome): ${op['return']:.2f}")
            cols = st.columns(3)
            for c, leg in zip(cols, op['legs']):
                tag = "SOURCE" if leg['is_source'] else "HEDGE"
                boost_txt = f" +{leg['boost']:g}%" if leg['is_source'] and leg['boost'] > 0 else ""
                box = c.info if leg['is_source'] else c.success
                box(f"**{tag}{boost_txt}**\n\n**{leg['book']}**\n\nStake: **${leg['stake']:.2f}**\n\n{leg['team']} @ {leg['price']:+}")
            st.metric("Guaranteed Profit", f"${op['profit']:.2f}", f"{roi:+.1f}% ROI")

def display_bet_get_results(opps, bg):
    st.markdown(f"<div class='betget-header'><h3>Optimized Qualification Paths for {bg['book']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['qualifying_loss'], reverse=True)

    if not sorted_opps:
        st.warning("No tight lines found for qualification.")
    else:
        for i, op in enumerate(sorted_opps[:10]):
            sign = "+" if op['net_value'] >= 0 else ""
            header = f"PATH {i+1} | Loss: ${op['qualifying_loss']:.2f} | Net Promo Lock: {sign}${op['net_value']:.2f} | {op['game']}"

            with st.expander(header):
                st.caption(f"**League Data:** {op['sport']} | Market: {op['market_type'].upper()}")

                if op['market_type'] == "3-way":
                    c1, c2, c3 = st.columns(3)
                    with c1: st.info(f"**REQUIRED (QUALIFIER)**\n\n**{op['s_book']}**\n\nBet: **${op['s_wager']:.2f}**\n\n{op['s_team']} @ {op['s_price']:+}")
                    with c2: st.success(f"**HEDGE LEG 1**\n\n**{op['h1_book']}**\n\nBet: **${op['h1_wager']:.2f}**\n\n{op['h1_team']} @ {op['h1_price']:+}")
                    with c3: st.success(f"**HEDGE LEG 2**\n\n**{op['h2_book']}**\n\nBet: **${op['h2_wager']:.2f}**\n\n{op['h2_team']} @ {op['h2_price']:+}")
                else:
                    c1, c2 = st.columns(2)
                    with c1: st.info(f"**REQUIRED (QUALIFIER)**\n\n**{op['s_book']}**\n\nBet: **${op['s_wager']:.2f}**\n\n{op['s_team']} @ {op['s_price']:+}")
                    with c2: st.success(f"**HEDGE LEG**\n\n**{op['h1_book']}**\n\nBet: **${op['h1_wager']:.2f}**\n\n{op['h1_team']} @ {op['h1_price']:+}")

                mc1, mc2 = st.columns(2)
                with mc1: st.metric("Qualifying Cost (Loss)", f"${op['qualifying_loss']:.2f}")
                with mc2: st.metric("Net Value Lock (Est. 70% Convert)", f"${op['net_value']:.2f}")

# --- HEADER AREA ---
c_title, c_quota = st.columns([3, 1])
with c_title:
    st.title("Promo Converter Matrix Engine")
with c_quota:
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)

st.divider()

# --- INITIALIZE STATE QUEUE ---
if 'promos' not in st.session_state:
    st.session_state.promos = []

# ========================================================
# SHARED BOOSTER MATRIX
# ========================================================
st.markdown("### 🛠️ Multi-Book Booster Matrix Configuration")
col_b1, col_b2, col_b3, col_b4 = st.columns(4)
with col_b1: dk_v = st.text_input("DraftKings Boosts (%)", value="0, 25")
with col_b2: fd_v = st.text_input("FanDuel Boosts (%)", value="0, 50")
with col_b3: espn_v = st.text_input("ESPN Boosts (%)", value="0")
with col_b4: mgm_v = st.text_input("BetMGM Boosts (%)", value="0")

global_boost_map = {
    'draftkings': parse_boosters(dk_v), 'fanduel': parse_boosters(fd_v),
    'espnbet': parse_boosters(espn_v), 'betmgm': parse_boosters(mgm_v)
}

st.write("")

# ========================================================
# STANDARD SCANNER (2-WAY US MARKETS) — formerly "Soccer Config"
# ========================================================
st.markdown("### 🏀 Standard Promo Scanner (2-Way)")
with st.expander("2-Way Config (WNBA / MLB)", expanded=True):
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
            sp = st.multiselect("Sports Filter", list(us_sports_map.keys()), default=["WNBA"], placeholder="Select sports...")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: add_to_q = st.form_submit_button("Add to Queue", use_container_width=True)
        with btn_col2: quick_scan = st.form_submit_button("Quick Scan", use_container_width=True)

if quick_scan:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        temp_p = {"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "all_boosts": global_boost_map}
        display_results(run_promo_scan(temp_p), temp_p)

if add_to_q:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "all_boosts": global_boost_map})

# --- RENDER SCAN QUEUE AREA ---
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
                display_results(run_promo_scan(promo_item), promo_item)
                st.divider()
    with clear_col:
        if st.button("Clear Queue", use_container_width=True):
            st.session_state.promos = []
            st.rerun()
    with cache_col:
        if st.button("Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.toast("Cache cleared!")

st.write("")
st.divider()

# ========================================================
# SOCCER MATRIX (3-WAY, 1-2 SOURCE BOOKS)
# ========================================================
st.markdown("### ⚽ Soccer Matrix (3-Way)")
with st.expander("Configure 3-Way Soccer Scan", expanded=True):
    sc_mode = st.radio("Source Mode", ["1 Source Book", "2 Source Books"], horizontal=True, key="sc_mode")
    n_src = 1 if sc_mode.startswith("1") else 2

    sc_c1, sc_c2 = st.columns(2)
    with sc_c1:
        src1 = st.selectbox("Source Book 1", list(book_map.keys()), key="sc_src1")
    with sc_c2:
        if n_src == 2:
            src2 = st.selectbox("Source Book 2", [k for k in book_map.keys() if k != src1], key="sc_src2")
        else:
            src2 = None

    sc_c3, sc_c4 = st.columns(2)
    with sc_c3:
        sc_budget = st.number_input("Total Stake Budget ($)", min_value=0.0, value=300.0, step=10.0, key="sc_budget",
                                    help="Spread across all 3 legs; the app sizes each so every outcome returns the same.")
    with sc_c4:
        sc_sports = st.multiselect("Soccer Leagues", list(soccer_map.keys()), default=list(soccer_map.keys()), key="sc_sports")

    if st.button("Scan Soccer Matrix", use_container_width=True, key="sc_run"):
        if not sc_sports:
            st.error("Select at least one league.")
        elif sc_budget <= 0:
            st.error("Enter a stake budget.")
        elif n_src == 2 and src2 is None:
            st.error("Pick a second source book.")
        else:
            source_labels = [src1] + ([src2] if src2 else [])
            source_keys = [book_map[l] for l in source_labels]
            soccer_cfg = {
                "source_keys": source_keys, "source_labels": source_labels,
                "budget": sc_budget, "sports": sc_sports, "boosts": global_boost_map
            }
            st.session_state.soccer_results = (run_soccer_scan(soccer_cfg), soccer_cfg)

if 'soccer_results' in st.session_state:
    display_soccer_results(st.session_state.soccer_results[0], st.session_state.soccer_results[1])
    if st.button("Clear Soccer Display", use_container_width=True, key="sc_clear"):
        del st.session_state.soccer_results
        st.rerun()

st.write("")
st.divider()

# ========================================================
# BET & GET FINDER (unchanged)
# ========================================================
st.markdown("### 🟢 Bet & Get Finder (No Boost Required)")
with st.expander("Configure Bet & Get Promotion Parameters", expanded=False):
    bg_book = st.selectbox("Qualifying Bookmaker Target", list(book_map.keys()), key="bg_b")

    col_w, col_v = st.columns(2)
    with col_w:
        bg_wager = st.number_input("Required Wager Amount ($)", min_value=10.0, value=100.0, key="bg_w")
    with col_v:
        bg_bonus = st.number_input("Bonus Bet Reward Expected ($)", min_value=5.0, value=20.0, key="bg_bon")

    bg_sports = st.multiselect("Leagues to Search", list(all_sports_map.keys()), default=list(all_sports_map.keys()), key="bg_s")

    if st.button("Find Cheapest Qualification Paths", use_container_width=True):
        bg_payload = {"book": bg_book, "wager": bg_wager, "bonus_val": bg_bonus, "sports": bg_sports}
        st.session_state.bg_results_cache = (run_bet_get_scan(bg_payload), bg_payload)

if 'bg_results_cache' in st.session_state:
    display_bet_get_results(st.session_state.bg_results_cache[0], st.session_state.bg_results_cache[1])
    if st.button("Clear Bet & Get Display", use_container_width=True):
        del st.session_state.bg_results_cache
        st.rerun()
