import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# ============================================================================
#  BOLD LEDGER THEME
# ============================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    .stApp { background-color:#f4f3ef; color:#1a1813; font-family:'Space Grotesk',sans-serif; }
    h1, h2, h3 { color:#1a1813 !important; font-family:'Space Grotesk',sans-serif !important; font-weight:700 !important; letter-spacing:-.01em; }
    [data-testid="stHeader"] { background:transparent; }

    [data-testid="stMetricValue"] { font-family:'JetBrains Mono',monospace; font-size:1.4rem !important; color:#1a1813; }
    [data-testid="stMetricLabel"] p { font-family:'JetBrains Mono',monospace !important; text-transform:uppercase; letter-spacing:.08em; font-size:.7rem !important; color:#9a9388 !important; }

    /* engine expanders look like cards */
    div[data-testid="stExpander"] {
        background:#ffffff !important; border:1px solid #e6e2d8 !important; border-radius:18px !important;
        box-shadow:0 8px 22px -16px rgba(60,50,30,.22); overflow:hidden;
    }
    div[data-testid="stExpander"] summary {
        font-family:'Space Grotesk',sans-serif !important; font-size:.95rem !important; font-weight:600 !important; color:#1a1813 !important;
    }

    /* form 'control-group' cards */
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] { align-items:stretch; }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] {
        background:#ffffff; border:1px solid #e6e2d8 !important; border-radius:16px !important;
        box-shadow:0 8px 22px -16px rgba(60,50,30,.18); height:100%; padding:.7rem .9rem !important;
    }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] { gap:.45rem !important; }

    /* buttons: ink pill */
    .stButton>button, div[data-testid="stFormSubmitButton"]>button {
        background:#1a1813 !important; color:#f4f3ef !important; border:none !important; border-radius:14px !important;
        font-family:'Space Grotesk',sans-serif !important; font-weight:700 !important; padding:.6rem 1rem !important;
    }
    .stButton>button:hover, div[data-testid="stFormSubmitButton"]>button:hover { background:#322d25 !important; color:#fff !important; }

    /* inputs / selects */
    div[data-baseweb="select"]>div, .stNumberInput input, .stTextInput input {
        background:#fbfaf7 !important; border:1.5px solid #e6e2d8 !important; border-radius:13px !important;
        color:#1a1813 !important; font-family:'Space Grotesk',sans-serif !important;
    }
    .stNumberInput input { font-family:'JetBrains Mono',monospace !important; font-weight:700 !important; }
    div[data-testid="stWidgetLabel"] p { color:#9a9388 !important; font-weight:600 !important; font-size:.72rem !important; }

    /* multiselect tags = ink chips */
    div[data-baseweb="tag"] { background:#1a1813 !important; color:#f4f3ef !important; border-radius:999px !important; font-family:'JetBrains Mono',monospace !important; font-weight:600 !important; }
    div[data-baseweb="tag"] svg { fill:#bdb7aa !important; }

    /* result cards */
    .pc-section { font:700 15px 'Space Grotesk',sans-serif; color:#1a1813; margin:20px 2px 12px; display:flex; justify-content:space-between; align-items:baseline; }
    .pc-section .c { font:600 11px 'JetBrains Mono',monospace; color:#9a9388; text-transform:uppercase; letter-spacing:.06em; }
    .pc-card { background:#fff; border:1px solid #e6e2d8; border-radius:18px; padding:15px; margin-bottom:12px; box-shadow:0 8px 22px -16px rgba(60,50,30,.22); }
    .pc-top { display:flex; justify-content:space-between; gap:11px; align-items:stretch; }
    .pc-head { min-width:0; display:flex; flex-direction:column; justify-content:center; }
    .pc-rankrow { display:flex; align-items:center; gap:7px; }
    .pc-rank { font:600 10px 'JetBrains Mono',monospace; color:#bdb7aa; }
    .pc-game { font:700 16px 'Space Grotesk',sans-serif; color:#1a1813; line-height:1.15; }
    .pc-meta { font:500 11px 'JetBrains Mono',monospace; color:#9a9388; margin-top:7px; }
    .pc-pill { flex:none; text-align:center; border-radius:14px; padding:9px 13px; display:flex; flex-direction:column; justify-content:center; }
    .pc-pos { background:#eaf3ed; } .pc-neg { background:#f6eceb; }
    .pc-profit { font:700 19px 'JetBrains Mono',monospace; }
    .pc-pos .pc-profit { color:#1f7a4d; } .pc-neg .pc-profit { color:#b23b3b; }
    .pc-sub { font:600 9px 'JetBrains Mono',monospace; margin-top:5px; }
    .pc-pos .pc-sub { color:#2f8a5a; } .pc-neg .pc-sub { color:#b23b3b; }
    .pc-conv { display:inline-block; font:700 10px 'JetBrains Mono',monospace; color:#1f7a4d; background:#eaf3ed; border-radius:7px; padding:5px 9px; margin-top:11px; }
    .pc-legs { margin-top:13px; display:flex; flex-direction:column; gap:7px; }
    .pc-leg { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; background:#f4f1ea; border-radius:11px; padding:9px 11px; }
    .pc-leg-l { min-width:0; }
    .pc-badge { font:700 9px 'Space Grotesk',sans-serif; padding:3px 7px; border-radius:6px; margin-right:7px; }
    .pc-bet { background:#1a1813; color:#f4f3ef; } .pc-hedge { background:#e2ddd2; color:#1a1813; }
    .pc-name { font:600 12px 'Space Grotesk',sans-serif; color:#46423a; }
    .pc-promo { font:500 11px 'Space Grotesk',sans-serif; color:#9a9388; margin-top:2px; }
    .pc-split { font:600 10px 'JetBrains Mono',monospace; color:#bdb7aa; margin-top:3px; }
    .pc-stake { font:700 12px 'JetBrains Mono',monospace; color:#1a1813; white-space:nowrap; }
    .pc-empty { background:#fff; border:1px dashed #e6e2d8; border-radius:18px; padding:26px; text-align:center; font:600 14px 'Space Grotesk',sans-serif; color:#9a9388; }
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

# --- UNIVERSAL SCAN ENGINE (MAIN BOOST ENGINE) ---
def run_promo_scan(p):
    if not p['hedge_books']:
        allowed_hedge_keys = [v for k, v in book_map.items() if v != book_map[p['book']]]
    else:
        allowed_hedge_keys = [book_map[b] for b in p['hedge_books'] if book_map[b] != book_map[p['book']]]

    source_book_key = book_map[p['book']]
    now_utc = datetime.now(timezone.utc)

    today_date = datetime.now().date()
    tomorrow_date = today_date + timedelta(days=1)

    all_opps = []

    with st.status("Running scan...", expanded=False) as status:
        for sport_label in p['sports']:
            sport_key = sports_map[sport_label]
            games, remaining = fetch_odds(sport_key)

            if games:
                st.session_state.api_quota = remaining
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    game_date_local = (commence_time - timedelta(hours=6)).date()

                    if game_date_local not in [today_date, tomorrow_date]:
                        continue

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

                    if not flat_odds: continue
                    unique_outcomes = list(set([o['team'] for o in flat_odds]))

                    # 3-Way Conversion
                    if len(unique_outcomes) == 3:
                        t1, t2, draw = unique_outcomes[0], unique_outcomes[1], unique_outcomes[2]
                        odds_t1 = [o for o in flat_odds if o['team'] == t1]
                        odds_t2 = [o for o in flat_odds if o['team'] == t2]
                        odds_draw = [o for o in flat_odds if o['team'] == draw]

                        for o1 in odds_t1:
                            for o2 in odds_t2:
                                for o3 in odds_draw:
                                    if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']: continue
                                    if source_book_key not in [o1['book_key'], o2['book_key'], o3['book_key']]: continue

                                    if p['strat'] == "Profit Boost (%)":
                                        m1 = get_multiplier(o1['price']) * (1 + (p['boost_val'] / 100)) if o1['book_key'] == source_book_key else get_multiplier(o1['price'])
                                        m2 = get_multiplier(o2['price']) * (1 + (p['boost_val'] / 100)) if o2['book_key'] == source_book_key else get_multiplier(o2['price'])
                                        m3 = get_multiplier(o3['price']) * (1 + (p['boost_val'] / 100)) if o3['book_key'] == source_book_key else get_multiplier(o3['price'])

                                        target_pay = p['wager'] * (1 + m1)
                                        h2_stake = target_pay / (1 + m2)
                                        h3_stake = target_pay / (1 + m3)
                                        exact_profit = target_pay - p['wager'] - h2_stake - h3_stake
                                    elif p['strat'] == "Bonus Bet":
                                        m1 = get_multiplier(o1['price'])
                                        m2 = get_multiplier(o2['price'])
                                        m3 = get_multiplier(o3['price'])
                                        target_pay = p['wager'] * get_multiplier(o1['price']) if o1['book_key'] == source_book_key else p['wager'] * m1
                                        h2_stake = target_pay / (1 + m2)
                                        h3_stake = target_pay / (1 + m3)
                                        exact_profit = target_pay - (0 if o1['book_key'] == source_book_key else p['wager']) - h2_stake - h3_stake
                                    else:
                                        mc = 0.65
                                        m1 = get_multiplier(o1['price'])
                                        m2 = get_multiplier(o2['price'])
                                        m3 = get_multiplier(o3['price'])
                                        target_pay = p['wager'] * (1 + m1)
                                        h2_stake = (target_pay - (p['wager'] * mc)) / (1 + m2)
                                        h3_stake = (target_pay - (p['wager'] * mc)) / (1 + m3)
                                        exact_profit = target_pay - p['wager'] - h2_stake - h3_stake

                                    if exact_profit > -10.0:
                                        all_opps.append({
                                            "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                                            "sport": sport_label, "market_type": "3-way",
                                            "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                            "exact_profit": exact_profit, "wager": p['wager'], "strat": p['strat'],
                                            "s_team": o1['team'], "s_book": o1['book_title'], "s_price": o1['price'], "exact_w1": p['wager'],
                                            "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "exact_hedge1": h2_stake,
                                            "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "exact_hedge2": h3_stake,
                                            "used_boost": p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0
                                        })

                    # --- STANDARD 2-WAY MARKETS ---
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
                                if p['strat'] == "Profit Boost (%)":
                                    sm = sm * (1 + (p['boost_val'] / 100))
                                hm = get_multiplier(best_h['price'])

                                if p['strat'] == "Profit Boost (%)":
                                    target_payout = p['wager'] * (1 + sm)
                                    raw_h = target_payout / (1 + hm)
                                    exact_profit = target_payout - p['wager'] - raw_h
                                elif p['strat'] == "Bonus Bet":
                                    target_payout = p['wager'] * sm
                                    raw_h = target_payout / (1 + hm)
                                    exact_profit = target_payout - raw_h
                                else:
                                    mc = 0.65
                                    target_payout = p['wager'] * (1 + sm)
                                    raw_h = (target_payout - (p['wager'] * mc)) / (1 + hm)
                                    exact_profit = target_payout - p['wager'] - raw_h

                                if exact_profit > -10.0:
                                    all_opps.append({
                                        "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                                        "sport": sport_label, "market_type": "2-way",
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "exact_profit": exact_profit, "exact_hedge": raw_h,
                                        "s_team": s['team'], "s_book": s['book_title'], "s_price": s['price'],
                                        "h_book": best_h['book_title'], "h_team": best_h['team'], "h_price": best_h['price'],
                                        "wager": p['wager'], "strat": p['strat'], "used_boost": p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0
                                    })
            else:
                st.error(f"Could not fetch data for {sport_label}")
        status.update(label="Scan complete.", state="complete")
    return all_opps


# --- ENGINE: SOCCER 3-WAY MATRIX WITH COMPLETE SPLIT CASH OVERRIDES ON ALL 3 LEGS ---
def run_multi_book_soccer_scan(sc):
    book1_key = book_map[sc['book1']]
    book2_keys = [book_map[b] for b in sc['book2']] if sc['book2'] else list(book_map.values())
    book3_keys = [book_map[b] for b in sc['book3']] if sc['book3'] else list(book_map.values())
    allowed_keys = list(book_map.values())

    today_date = datetime.now().date()
    end_date = sc['lookahead_end_date']

    soccer_opps = []

    with st.status("Running scan...", expanded=False) as status:
        for league_label in sc['leagues']:
            sport_key = sports_map[league_label]
            games, remaining = fetch_odds(sport_key)
            if games:
                st.session_state.api_quota = remaining
                for game in games:
                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                    game_date_local = (commence_time - timedelta(hours=6)).date()

                    if not (today_date <= game_date_local <= end_date):
                        continue

                    flat_odds = []
                    for bm in game['bookmakers']:
                        if bm['key'] in allowed_keys:
                            for o in bm['markets'][0]['outcomes']:
                                flat_odds.append({'book_key': bm['key'], 'book_title': bm['title'], 'team': o['name'], 'price': o['price']})

                    unique_outcomes = list(set([o['team'] for o in flat_odds]))
                    if len(unique_outcomes) != 3: continue

                    t1, t2, draw = unique_outcomes[0], unique_outcomes[1], unique_outcomes[2]
                    odds_t1 = [o for o in flat_odds if o['team'] == t1]
                    odds_t2 = [o for o in flat_odds if o['team'] == t2]
                    odds_draw = [o for o in flat_odds if o['team'] == draw]

                    for o1 in odds_t1:
                        for o2 in odds_t2:
                            for o3 in odds_draw:
                                if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']: continue
                                if o1['book_key'] != book1_key or o2['book_key'] not in book2_keys or o3['book_key'] not in book3_keys: continue

                                def leg_payout(w_total, strat, boost_pct, m_raw, cap_val):
                                    """Returns (target_payout, outlay, w_promo, w_cash) for one leg."""
                                    mc_nosweat = 0.65
                                    m_boosted = m_raw * (1 + boost_pct / 100) if strat == "Profit Boost (%)" else m_raw

                                    if strat != "Straight Cash" and cap_val > 0 and w_total > cap_val:
                                        w_promo = cap_val
                                        w_cash = w_total - cap_val
                                    else:
                                        w_promo = w_total if strat != "Straight Cash" else 0.0
                                        w_cash = 0.0 if strat != "Straight Cash" else w_total

                                    if strat == "Bonus Bet":
                                        raw_pay = (w_promo * m_boosted) + (w_cash * (1 + m_raw))
                                        outlay = w_cash
                                    elif strat == "No-Sweat Bet":
                                        raw_pay = (w_promo * (1 + m_raw)) + (w_cash * (1 + m_raw))
                                        outlay = w_total
                                    else:
                                        raw_pay = (w_promo * (1 + m_boosted)) + (w_cash * (1 + m_raw))
                                        outlay = w_total

                                    return raw_pay, outlay, w_promo, w_cash

                                m1_raw = get_multiplier(o1['price'])
                                target_pay, outlay1, w1_promo, w1_cash = leg_payout(
                                    sc['wager1'], sc['strat1'], sc['boost1'], m1_raw, sc['cap1_val']
                                )
                                w1_total = sc['wager1']

                                m2_raw = get_multiplier(o2['price'])
                                m2_boosted = m2_raw * (1 + sc['boost2'] / 100) if sc['strat2'] == "Profit Boost (%)" else m2_raw
                                div_promo2 = m2_boosted if sc['strat2'] == "Bonus Bet" else (1 + m2_boosted)
                                div_cash2 = 1 + m2_raw

                                if sc['strat2'] != "Straight Cash" and sc['cap2_val'] > 0:
                                    max_promo_pay2 = sc['cap2_val'] * div_promo2
                                    if target_pay > max_promo_pay2:
                                        w2_promo = sc['cap2_val']
                                        w2_cash = (target_pay - max_promo_pay2) / div_cash2
                                    else:
                                        w2_promo = target_pay / div_promo2
                                        w2_cash = 0.0
                                elif sc['strat2'] == "Straight Cash":
                                    w2_promo, w2_cash = 0.0, target_pay / div_cash2
                                else:
                                    w2_promo, w2_cash = target_pay / div_promo2, 0.0

                                w2_total = w2_promo + w2_cash
                                outlay2 = w2_cash if sc['strat2'] == "Bonus Bet" else w2_total

                                m3_raw = get_multiplier(o3['price'])
                                m3_boosted = m3_raw * (1 + sc['boost3'] / 100) if sc['strat3'] == "Profit Boost (%)" else m3_raw
                                div_promo3 = m3_boosted if sc['strat3'] == "Bonus Bet" else (1 + m3_boosted)
                                div_cash3 = 1 + m3_raw

                                if sc['strat3'] != "Straight Cash" and sc['cap3_val'] > 0:
                                    max_promo_pay3 = sc['cap3_val'] * div_promo3
                                    if target_pay > max_promo_pay3:
                                        w3_promo = sc['cap3_val']
                                        w3_cash = (target_pay - max_promo_pay3) / div_cash3
                                    else:
                                        w3_promo = target_pay / div_promo3
                                        w3_cash = 0.0
                                elif sc['strat3'] == "Straight Cash":
                                    w3_promo, w3_cash = 0.0, target_pay / div_cash3
                                else:
                                    w3_promo, w3_cash = target_pay / div_promo3, 0.0

                                w3_total = w3_promo + w3_cash
                                outlay3 = w3_cash if sc['strat3'] == "Bonus Bet" else w3_total

                                net_profit = target_pay - (outlay1 + outlay2 + outlay3)

                                soccer_opps.append({
                                    "game": f"{game.get('away_team')} vs {game.get('home_team')}",
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                    "net_profit": net_profit,
                                    "o1_book": o1['book_title'], "o1_team": o1['team'], "o1_price": o1['price'], "o1_wager": w1_total, "o1_promo": w1_promo, "o1_cash": w1_cash, "o1_strat": sc['strat1'], "o1_boost": sc['boost1'] if sc['strat1'] == "Profit Boost (%)" else 0,
                                    "o2_book": o2['book_title'], "o2_team": o2['team'], "o2_price": o2['price'], "o2_wager": w2_total, "o2_promo": w2_promo, "o2_cash": w2_cash, "o2_strat": sc['strat2'], "o2_boost": sc['boost2'] if sc['strat2'] == "Profit Boost (%)" else 0,
                                    "o3_book": o3['book_title'], "o3_team": o3['team'], "o3_price": o3['price'], "o3_wager": w3_total, "o3_promo": w3_promo, "o3_cash": w3_cash, "o3_strat": sc['strat3'], "o3_boost": sc['boost3'] if sc['strat3'] == "Profit Boost (%)" else 0
                                })
        status.update(label="Scan complete.", state="complete")

    seen = set()
    deduped = []
    for op in soccer_opps:
        key = (op['game'], frozenset([op['o1_book'], op['o2_book'], op['o3_book']]))
        if key not in seen:
            seen.add(key)
            deduped.append(op)
    return deduped


# --- DEDICATED BET & GET SCAN ENGINE ---
def run_bet_get_scan(bg):
    source_book_key = book_map[bg['book']]
    allowed_hedge_keys = [v for k, v in book_map.items() if v != source_book_key]
    now_utc = datetime.now(timezone.utc)

    today_date = datetime.now().date()
    tomorrow_date = today_date + timedelta(days=1)

    bg_opps = []

    projected_bonus_value = bg['bonus_val'] * 0.70

    with st.status("Running scan...", expanded=False) as status:
        for sport_label in bg['sports']:
            sport_key = sports_map[sport_label]
            games, remaining = fetch_odds(sport_key)
            if not games: continue
            st.session_state.api_quota = remaining

            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                game_date_local = (commence_time - timedelta(hours=6)).date()

                if game_date_local not in [today_date, tomorrow_date]:
                    continue

                flat_odds = []
                for bm in game['bookmakers']:
                    if bm['key'] == source_book_key or bm['key'] in allowed_hedge_keys:
                        for o in bm['markets'][0]['outcomes']:
                            flat_odds.append({'book_key': bm['key'], 'book_title': bm['title'], 'team': o['name'], 'price': o['price']})

                unique_outcomes = list(set([o['team'] for o in flat_odds]))

                if len(unique_outcomes) == 3:
                    odds_t1 = [o for o in flat_odds if o['team'] == unique_outcomes[0]]
                    odds_t2 = [o for o in flat_odds if o['team'] == unique_outcomes[1]]
                    odds_draw = [o for o in flat_odds if o['team'] == unique_outcomes[2]]

                    for o1 in odds_t1:
                        for o2 in odds_t2:
                            for o3 in odds_draw:
                                if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']: continue
                                if o1['book_key'] != source_book_key: continue

                                sm = get_multiplier(o1['price'])
                                hm1 = get_multiplier(o2['price'])
                                hm2 = get_multiplier(o3['price'])

                                target_payout = bg['wager'] * (1 + sm)
                                h1_stake = target_payout / (1 + hm1)
                                h2_stake = target_payout / (1 + hm2)

                                qualifying_loss = target_payout - bg['wager'] - h1_stake - h2_stake
                                net_promo_value = projected_bonus_value + qualifying_loss

                                bg_opps.append({
                                    "game": f"{game.get('away_team')} vs {game.get('home_team')}", "sport": sport_label, "market_type": "3-way", "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                    "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                                    "s_book": o1['book_title'], "s_team": o1['team'], "s_price": o1['price'], "s_wager": bg['wager'],
                                    "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "h1_wager": h1_stake,
                                    "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "h2_wager": h2_stake
                                })

                elif len(unique_outcomes) == 2:
                    source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                    hedge_odds = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]

                    for s in source_odds:
                        opp_team = [t for t in unique_outcomes if t != s['team']][0]
                        eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                        if not eligible_hedges: continue

                        best_h = max(eligible_hedges, key=lambda x: x['price'])
                        sm = get_multiplier(s['price'])
                        hm = get_multiplier(best_h['price'])

                        target_payout = bg['wager'] * (1 + sm)
                        h_stake = target_payout / (1 + hm)

                        qualifying_loss = target_payout - bg['wager'] - h_stake
                        net_promo_value = projected_bonus_value + qualifying_loss

                        bg_opps.append({
                            "game": f"{game.get('away_team')} vs {game.get('home_team')}", "sport": sport_label, "market_type": "2-way", "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                            "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                            "s_book": s['book_title'], "s_team": s['team'], "s_price": s['price'], "s_wager": bg['wager'],
                            "h1_book": best_h['book_title'], "h1_team": best_h['team'], "h1_price": best_h['price'], "h1_wager": h_stake
                        })

        status.update(label="Scan complete.", state="complete")
    return bg_opps


# ============================================================================
#  BOLD LEDGER RENDER HELPERS + FUNCTIONS
# ============================================================================
def _odds(p):   return f"+{int(p)}" if p >= 0 else f"{int(p)}"
def _money(x):  return f"${x:,.2f}"
def _signed(x): return ("+" if x >= 0 else "\u2212") + f"${abs(x):,.2f}"

def _pill(value, sub):
    cls = "pc-pos" if value >= 0 else "pc-neg"
    sub_html = f"<div class='pc-sub'>{sub}</div>" if sub else ""
    return f"<div class='pc-pill {cls}'><div class='pc-profit'>{_signed(value)}</div>{sub_html}</div>"

def _leg(kind, book, line, stake, promo=None, split=None):
    badge = "pc-bet" if kind in ("BET", "QUAL") else "pc-hedge"
    promo_html = f"<div class='pc-promo'>{promo}</div>" if promo else ""
    split_html = f"<div class='pc-split'>{split}</div>" if split else ""
    return (
        "<div class='pc-leg'><div class='pc-leg-l'>"
        f"<span class='pc-badge {badge}'>{kind}</span>"
        f"<span class='pc-name'>{book} \u00b7 {line}</span>"
        f"{promo_html}{split_html}</div>"
        f"<span class='pc-stake'>{_money(stake)}</span></div>"
    )

def _card(rank, game, meta, pill_html, legs_html, extra=""):
    return (
        "<div class='pc-card'><div class='pc-top'>"
        f"<div class='pc-head'><div class='pc-rankrow'><span class='pc-rank'>#{rank}</span>"
        f"<span class='pc-game'>{game}</span></div>"
        f"<div class='pc-meta'>{meta}</div></div>{pill_html}</div>{extra}"
        f"<div class='pc-legs'>{legs_html}</div></div>"
    )


# --- RENDER FUNCTIONS ---
def display_results(all_opps, p):
    st.markdown(
        f"<div class='pc-section'>Best plays \u2014 {p['book']} \u00b7 {p['strat']}"
        f"<span class='c'>{min(len(all_opps),15)} shown</span></div>",
        unsafe_allow_html=True,
    )
    opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)
    if not opps:
        st.markdown("<div class='pc-empty'>No profitable matches. Try a higher boost or more sports.</div>", unsafe_allow_html=True)
        return

    html = ""
    for i, op in enumerate(opps[:15]):
        profit = op['exact_profit']
        meta = f"{op['time']} \u00b7 {op['sport']} \u00b7 {op.get('market_type','').upper()}"

        if op.get('market_type') == "3-way":
            invested = op['exact_w1'] + op['exact_hedge1'] + op['exact_hedge2']
            legs = (
                _leg("BET",   op['s_book'],  f"{op['s_team']} {_odds(op['s_price'])}",  op['exact_w1']) +
                _leg("HEDGE", op['h1_book'], f"{op['h1_team']} {_odds(op['h1_price'])}", op['exact_hedge1']) +
                _leg("HEDGE", op['h2_book'], f"{op['h2_team']} {_odds(op['h2_price'])}", op['exact_hedge2'])
            )
        else:
            invested = op['wager'] + op['exact_hedge']
            legs = (
                _leg("BET",   op['s_book'], f"{op['s_team']} {_odds(op['s_price'])}", op['wager']) +
                _leg("HEDGE", op['h_book'], f"{op['h_team']} {_odds(op['h_price'])}", op['exact_hedge'])
            )

        roi = (profit / invested * 100) if invested else 0
        pill = _pill(profit, f"ROI {roi:.1f}%")

        extra = ""
        if op['strat'] == "Bonus Bet":
            bonus_w = op.get('exact_w1', op.get('wager', 0)) or 1
            extra = f"<div class='pc-conv'>{profit / bonus_w * 100:.1f}% conversion</div>"

        html += _card(i + 1, op['game'], meta, pill, legs, extra)

    st.markdown(html, unsafe_allow_html=True)


def display_soccer_results(opps):
    st.markdown(
        f"<div class='pc-section'>3-way soccer results<span class='c'>{min(len(opps),10)} shown</span></div>",
        unsafe_allow_html=True,
    )
    opps = sorted(opps, key=lambda x: x['net_profit'], reverse=True)
    if not opps:
        st.markdown("<div class='pc-empty'>No matches for your book criteria.</div>", unsafe_allow_html=True)
        return

    def _soccer_leg(op, n):
        strat = op[f'o{n}_strat']; boost = op[f'o{n}_boost']
        promo = f"{strat} +{boost}%" if boost else strat
        cash = op[f'o{n}_cash']; promo_amt = op[f'o{n}_promo']
        split = None
        if strat != "Straight Cash" and cash > 0.01:
            split = f"\u21b3 promo {_money(promo_amt)} \u00b7 cash {_money(cash)}"
        line = f"{op[f'o{n}_team']} {_odds(op[f'o{n}_price'])}"
        return _leg("BET" if n == 1 else "HEDGE", op[f'o{n}_book'], line, op[f'o{n}_wager'], promo=promo, split=split)

    html = ""
    for i, op in enumerate(opps[:10]):
        meta = f"{op['time']} \u00b7 FIFA"
        pill = _pill(op['net_profit'], "Net profit")
        legs = _soccer_leg(op, 1) + _soccer_leg(op, 2) + _soccer_leg(op, 3)
        html += _card(i + 1, op['game'], meta, pill, legs)

    st.markdown(html, unsafe_allow_html=True)


def display_bet_get_results(opps, bg):
    st.markdown(
        f"<div class='pc-section'>Net value \u2014 {bg['book']}<span class='c'>est. 70% convert</span></div>",
        unsafe_allow_html=True,
    )
    opps = sorted(opps, key=lambda x: x['net_value'], reverse=True)
    if not opps:
        st.markdown("<div class='pc-empty'>No tight lines found for qualification.</div>", unsafe_allow_html=True)
        return

    html = ""
    for i, op in enumerate(opps[:10]):
        meta = f"{op['time']} \u00b7 {op['sport']} \u00b7 {op['market_type'].upper()}"
        pill = _pill(op['net_value'], f"cost {_money(op['qualifying_loss'])}")
        legs = _leg("QUAL", op['s_book'], f"{op['s_team']} {_odds(op['s_price'])}", op['s_wager'])
        legs += _leg("HEDGE", op['h1_book'], f"{op['h1_team']} {_odds(op['h1_price'])}", op['h1_wager'])
        if op['market_type'] == "3-way":
            legs += _leg("HEDGE", op['h2_book'], f"{op['h2_team']} {_odds(op['h2_price'])}", op['h2_wager'])
        html += _card(i + 1, op['game'], meta, pill, legs)

    st.markdown(html, unsafe_allow_html=True)


# --- HEADER AREA ---
c_title, c_quota = st.columns([3, 1])
with c_title:
    st.title("Promo Converter")
with c_quota:
    if 'api_quota' not in st.session_state: st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)

st.divider()

# --- INITIALIZE STATE QUEUES ---
if 'promos' not in st.session_state: st.session_state.promos = []

# ========================================================
# TOP MODULE: MAIN BOOST ENGINE
# ========================================================
with st.expander("Main Boost Engine", expanded=True):
    with st.form("promo_form", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            with st.container(border=True):
                b = st.selectbox("Source Book", list(book_map.keys()))
                s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            with st.container(border=True):
                w = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=5.0)
                main_boost_val = st.number_input("Boost Value (%)", min_value=0, value=0, step=5, help="Only applies if Promo Type is set to Profit Boost (%)", disabled=(s != "Profit Boost (%)"))
        with col3:
            with st.container(border=True):
                hb = st.multiselect("Hedge Book(s)", list(book_map.keys()), placeholder="All Books")
        with col4:
            with st.container(border=True):
                sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=[], placeholder="Select sports...")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            promo_submit = st.form_submit_button("Scan")
        with btn_col2:
            add_queue = st.form_submit_button("Add to Multi-Run Queue")

    if promo_submit:
        active_sports = sp if sp else list(sports_map.keys())
        p_config = {"book": b, "strat": s, "boost_val": main_boost_val, "wager": w, "hedge_books": hb, "sports": active_sports, "conv_rate": 65}
        results = run_promo_scan(p_config)
        display_results(results, p_config)

# ========================================================
# LOWER MODULE: SOCCER MULTI-BOOK COMPLEX GRID (3-WAY)
# ========================================================
with st.expander("3-Way Soccer Engine", expanded=False):
    with st.form("soccer_form"):
        today = datetime.now().date()
        lookahead_end = today + timedelta(days=2)

        st.divider()

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            with st.container(border=True):
                st.subheader("Bet 1")
                sb1 = st.selectbox("Book", list(book_map.keys()), index=0, key="sc_book1")
                ss1 = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type1")
                sbv1 = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost1")
                sw1 = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake1")
                scap1 = st.number_input("Promo Cap ($)", min_value=0.0, value=0.0, help="Max stake eligible for promo. 0 = no cap.", key="sc_cap1")
        with sc2:
            with st.container(border=True):
                st.subheader("Bet 2")
                sb2 = st.multiselect("Book(s)", list(book_map.keys()), default=[], placeholder="Select books...", key="sc_book2")
                ss2 = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type2")
                sbv2 = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost2")
                sw2 = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake2")
                scap2 = st.number_input("Promo Cap ($)", min_value=0.0, value=0.0, help="Max stake eligible for promo. 0 = no cap.", key="sc_cap2")
        with sc3:
            with st.container(border=True):
                st.subheader("Bet 3")
                sb3 = st.multiselect("Book(s)", list(book_map.keys()), default=[], placeholder="Select books...", key="sc_book3")
                ss3 = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type3")
                sbv3 = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost3")
                sw3 = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake3")
                scap3 = st.number_input("Promo Cap ($)", min_value=0.0, value=0.0, help="Max stake eligible for promo. 0 = no cap.", key="sc_cap3")

        soccer_submit = st.form_submit_button("Scan")

    if soccer_submit:
        soccer_config = {
            "book1": sb1, "strat1": ss1, "boost1": sbv1, "wager1": sw1, "cap1_val": scap1,
            "book2": sb2 if sb2 else list(book_map.keys()), "strat2": ss2, "boost2": sbv2, "wager2": sw2, "cap2_val": scap2,
            "book3": sb3 if sb3 else list(book_map.keys()), "strat3": ss3, "boost3": sbv3, "wager3": sw3, "cap3_val": scap3,
            "leagues": ["FIFA World Cup"],
            "lookahead_end_date": lookahead_end
        }
        soccer_results = run_multi_book_soccer_scan(soccer_config)
        display_soccer_results(soccer_results)

# ========================================================
# BOTTOM MODULE: DEDICATED BET & GET QUALIFIER
# ========================================================
with st.expander("Bet and Get Engine", expanded=False):
    with st.form("bet_get_form"):
        bgc1, bgc2 = st.columns(2)
        with bgc1:
            with st.container(border=True):
                bg_b = st.selectbox("Book", list(book_map.keys()))
                bg_w = st.number_input("Qual. Stake ($)", min_value=0.0, value=0.0, step=5.0)
        with bgc2:
            with st.container(border=True):
                bg_v = st.number_input("Bonus Value ($)", min_value=0.0, value=0.0, step=5.0)
                bg_sp = st.multiselect("Sports", list(sports_map.keys()), default=[])

        bg_submit = st.form_submit_button("Scan")

    if bg_submit:
        bg_config = {"book": bg_b, "wager": bg_w, "bonus_val": bg_v, "sports": bg_sp}
        bg_results = run_bet_get_scan(bg_config)
        display_bet_get_results(bg_results, bg_config)
