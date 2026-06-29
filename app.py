import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter", layout="wide")

# --- CONSTANTS ---
CENTRAL      = ZoneInfo("America/Chicago")
CONV_NOSWEAT = 0.65
CONV_BETGET  = 0.65
SOCCER_SPORTS = {"FIFA World Cup"}

# --- PROFESSIONAL THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto+Mono&display=swap');
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
    [data-testid="stExpander"] summary {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
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
        background-color: #f0f9ff;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 5px solid #0284c7;
    }
    .betget-header {
        background-color: #f0fdf4;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 5px solid #16a34a;
    }
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
        align-items: stretch;
    }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        height: 100%;
        padding: 0.6rem 0.8rem !important;
    }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
        gap: 0.4rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")

def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

book_map = {
    "DraftKings":      "draftkings",
    "FanDuel":         "fanduel",
    "theScore / ESPN": "espnbet",
    "BetMGM":          "betmgm"
}

sports_map = {
    "WNBA":           "basketball_wnba",
    "MLB":            "baseball_mlb",
    "FIFA World Cup": "soccer_fifa_world_cup"
}


# --- CACHED API FETCHING ---
@st.cache_data(ttl=300)
def fetch_odds(sport_key, market='h2h'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        'apiKey':     API_KEY,
        'regions':    'us,us2',
        'markets':    market,
        'oddsFormat': 'american'
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return res.json(), res.headers.get('x-requests-remaining', "0")
        return None, "Error"
    except requests.exceptions.RequestException:
        return None, "Error"


# --- FLAT ODDS HELPERS ---

def _get_market(bm, market_key):
    return next((m for m in bm['markets'] if m['key'] == market_key), None)

def build_flat_odds_h2h(game, allowed_keys):
    """Standard h2h — passes all outcomes through as-is."""
    flat = []
    for bm in game['bookmakers']:
        if bm['key'] not in allowed_keys:
            continue
        market = _get_market(bm, 'h2h')
        if not market:
            continue
        for o in market['outcomes']:
            flat.append({
                'book_key':   bm['key'],
                'book_title': bm['title'],
                'team':       o['name'],
                'price':      o['price']
            })
    return flat

def build_flat_odds_3way(game, allowed_keys):
    """3-way match result — only includes bookmakers offering all 3 outcomes."""
    flat = []
    for bm in game['bookmakers']:
        if bm['key'] not in allowed_keys:
            continue
        market = _get_market(bm, 'h2h')
        if not market:
            continue
        if len(market['outcomes']) != 3:
            continue
        for o in market['outcomes']:
            flat.append({
                'book_key':   bm['key'],
                'book_title': bm['title'],
                'team':       o['name'],
                'price':      o['price']
            })
    return flat


# ================================================================
# MAIN BOOST ENGINE
# All sports use h2h. Outcome count routes the logic:
#   2 outcomes → 2-way arb (covers soccer qualifier/to-advance lines)
#   3 outcomes → 3-way arb (non-soccer sports with draw)
# ================================================================
def run_promo_scan(p):
    if not p['hedge_books']:
        allowed_hedge_keys = [v for k, v in book_map.items() if v != book_map[p['book']]]
    else:
        allowed_hedge_keys = [book_map[b] for b in p['hedge_books'] if book_map[b] != book_map[p['book']]]

    source_book_key = book_map[p['book']]
    allowed_keys    = [source_book_key] + allowed_hedge_keys

    today_date    = datetime.now(CENTRAL).date()
    tomorrow_date = today_date + timedelta(days=1)

    all_opps = []

    with st.status("Running scan...", expanded=False) as status:
        for sport_label in p['sports']:
            sport_key = sports_map[sport_label]
            games, remaining = fetch_odds(sport_key, market='h2h')

            if not games:
                st.error(f"Could not fetch data for {sport_label}")
                continue

            st.session_state.api_quota = remaining

            for game in games:
                commence_time   = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                game_date_local = commence_time.astimezone(CENTRAL).date()

                if game_date_local not in [today_date, tomorrow_date]:
                    continue

                flat_odds = build_flat_odds_h2h(game, allowed_keys)
                if not flat_odds:
                    continue

                game_label      = f"{game.get('away_team', 'Away')} vs {game.get('home_team', 'Home')}"
                game_time       = commence_time.astimezone(CENTRAL).strftime("%m/%d %I:%M %p")
                unique_outcomes = list(set(o['team'] for o in flat_odds))

                # --- 2-WAY BRANCH (includes soccer qualifier lines) ---
                if len(unique_outcomes) == 2:
                    source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                    hedge_odds  = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]

                    for s in source_odds:
                        hedge_teams = [t for t in unique_outcomes if t != s['team']]
                        if not hedge_teams: continue
                        opp_team = hedge_teams[0]

                        eligible = [h for h in hedge_odds if h['team'] == opp_team]
                        if not eligible: continue

                        best_h = max(eligible, key=lambda x: x['price'])
                        sm     = get_multiplier(s['price'])
                        hm     = get_multiplier(best_h['price'])

                        if p['strat'] == "Profit Boost (%)":
                            sm_eff        = sm * (1 + p['boost_val'] / 100)
                            target_payout = p['wager'] * (1 + sm_eff)
                            raw_h         = target_payout / (1 + hm)
                            exact_profit  = target_payout - p['wager'] - raw_h
                        elif p['strat'] == "Bonus Bet":
                            target_payout = p['wager'] * sm
                            raw_h         = target_payout / (1 + hm)
                            exact_profit  = target_payout - raw_h
                        else:  # No-Sweat
                            target_payout = p['wager'] * (1 + sm)
                            raw_h         = (target_payout - p['wager'] * CONV_NOSWEAT) / (1 + hm)
                            exact_profit  = target_payout - p['wager'] - raw_h

                        if exact_profit > -10.0:
                            all_opps.append({
                                "game":         game_label,
                                "sport":        sport_label,
                                "market_type":  "2-way",
                                "market_label": "Qualifier" if sport_label in SOCCER_SPORTS else "Match Result",
                                "time":         game_time,
                                "exact_profit": exact_profit,
                                "exact_hedge":  raw_h,
                                "s_team":       s['team'],
                                "s_book":       s['book_title'],
                                "s_price":      s['price'],
                                "h_book":       best_h['book_title'],
                                "h_team":       best_h['team'],
                                "h_price":      best_h['price'],
                                "wager":        p['wager'],
                                "strat":        p['strat'],
                                "used_boost":   p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0
                            })

                # --- 3-WAY BRANCH ---
                elif len(unique_outcomes) == 3:
                    outcome_groups = {
                        team: [o for o in flat_odds if o['team'] == team]
                        for team in unique_outcomes
                    }
                    outcome_list = list(outcome_groups.items())

                    for i, (_, odds_t1) in enumerate(outcome_list):
                        for j, (_, odds_t2) in enumerate(outcome_list):
                            if j == i: continue
                            for k, (_, odds_t3) in enumerate(outcome_list):
                                if k == i or k == j: continue
                                for o1 in odds_t1:
                                    for o2 in odds_t2:
                                        for o3 in odds_t3:
                                            books_used = [o1['book_key'], o2['book_key'], o3['book_key']]
                                            if len(set(books_used)) != 3: continue
                                            if source_book_key not in books_used: continue

                                            all_legs = [o1, o2, o3]
                                            src_idx  = next(n for n, o in enumerate(all_legs) if o['book_key'] == source_book_key)
                                            src_o    = all_legs[src_idx]
                                            hedge_os = [o for n, o in enumerate(all_legs) if n != src_idx]
                                            ho1, ho2 = hedge_os[0], hedge_os[1]

                                            sm  = get_multiplier(src_o['price'])
                                            hm1 = get_multiplier(ho1['price'])
                                            hm2 = get_multiplier(ho2['price'])

                                            if p['strat'] == "Profit Boost (%)":
                                                sm_eff       = sm * (1 + p['boost_val'] / 100)
                                                target_pay   = p['wager'] * (1 + sm_eff)
                                                h1_stake     = target_pay / (1 + hm1)
                                                h2_stake     = target_pay / (1 + hm2)
                                                exact_profit = target_pay - p['wager'] - h1_stake - h2_stake
                                            elif p['strat'] == "Bonus Bet":
                                                target_pay   = p['wager'] * sm
                                                h1_stake     = target_pay / (1 + hm1)
                                                h2_stake     = target_pay / (1 + hm2)
                                                exact_profit = target_pay - h1_stake - h2_stake
                                            else:  # No-Sweat
                                                target_pay   = p['wager'] * (1 + sm)
                                                h1_stake     = (target_pay - p['wager'] * CONV_NOSWEAT) / (1 + hm1)
                                                h2_stake     = (target_pay - p['wager'] * CONV_NOSWEAT) / (1 + hm2)
                                                exact_profit = target_pay - p['wager'] - h1_stake - h2_stake

                                            if exact_profit > -10.0:
                                                all_opps.append({
                                                    "game":         game_label,
                                                    "sport":        sport_label,
                                                    "market_type":  "3-way",
                                                    "market_label": "Match Result",
                                                    "time":         game_time,
                                                    "exact_profit": exact_profit,
                                                    "wager":        p['wager'],
                                                    "strat":        p['strat'],
                                                    "s_team":       src_o['team'],
                                                    "s_book":       src_o['book_title'],
                                                    "s_price":      src_o['price'],
                                                    "exact_w1":     p['wager'],
                                                    "h1_book":      ho1['book_title'],
                                                    "h1_team":      ho1['team'],
                                                    "h1_price":     ho1['price'],
                                                    "exact_hedge1": h1_stake,
                                                    "h2_book":      ho2['book_title'],
                                                    "h2_team":      ho2['team'],
                                                    "h2_price":     ho2['price'],
                                                    "exact_hedge2": h2_stake,
                                                    "used_boost":   p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0
                                                })

        status.update(label="Scan complete.", state="complete")

    # Deduplicate — the 3-way permutation loop produces the same game/book-set
    # multiple times with hedge legs in different column order.
    # Keep the single best profit per unique (game, promo_book, frozenset_of_all_books).
    seen = {}
    for op in all_opps:
        if op['market_type'] == '3-way':
            key = (op['game'], op['s_book'],
                   frozenset([op['s_book'], op['h1_book'], op['h2_book']]))
        else:
            key = (op['game'], op['s_book'], op['h_book'])
        if key not in seen or op['exact_profit'] > seen[key]['exact_profit']:
            seen[key] = op
    return list(seen.values())


# ================================================================
# 3-WAY SOCCER ENGINE — match result h2h with draw included
# ================================================================
def run_multi_book_soccer_scan(sc):
    book1_key  = book_map[sc['book1']]
    book2_keys = [book_map[b] for b in sc['book2']] if sc['book2'] else list(book_map.values())
    book3_keys = [book_map[b] for b in sc['book3']] if sc['book3'] else list(book_map.values())
    allowed_keys = list(book_map.values())

    today_date = datetime.now(CENTRAL).date()
    end_date   = sc['lookahead_end_date']

    soccer_opps = []

    with st.status("Running scan...", expanded=False) as status:
        for league_label in sc['leagues']:
            sport_key = sports_map[league_label]
            games, remaining = fetch_odds(sport_key, market='h2h')
            if not games:
                continue

            st.session_state.api_quota = remaining

            for game in games:
                commence_time   = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                game_date_local = commence_time.astimezone(CENTRAL).date()

                if not (today_date <= game_date_local <= end_date):
                    continue

                flat_odds = build_flat_odds_3way(game, allowed_keys)
                if not flat_odds:
                    continue

                unique_outcomes = list(set(o['team'] for o in flat_odds))
                if len(unique_outcomes) != 3:
                    continue

                t1, t2, draw = unique_outcomes[0], unique_outcomes[1], unique_outcomes[2]
                odds_t1   = [o for o in flat_odds if o['team'] == t1]
                odds_t2   = [o for o in flat_odds if o['team'] == t2]
                odds_draw = [o for o in flat_odds if o['team'] == draw]

                for o1 in odds_t1:
                    for o2 in odds_t2:
                        for o3 in odds_draw:
                            if o1['book_key'] == o2['book_key'] or \
                               o1['book_key'] == o3['book_key'] or \
                               o2['book_key'] == o3['book_key']:
                                continue
                            if o1['book_key'] != book1_key:      continue
                            if o2['book_key'] not in book2_keys: continue
                            if o3['book_key'] not in book3_keys: continue

                            def leg_payout(w_total, strat, boost_pct, m_raw, cap_val):
                                m_boosted = m_raw * (1 + boost_pct / 100) if strat == "Profit Boost (%)" else m_raw
                                if strat != "Straight Cash" and cap_val > 0 and w_total > cap_val:
                                    w_promo = cap_val
                                    w_cash  = w_total - cap_val
                                else:
                                    w_promo = w_total if strat != "Straight Cash" else 0.0
                                    w_cash  = 0.0    if strat != "Straight Cash" else w_total
                                if strat == "Bonus Bet":
                                    raw_pay = (w_promo * m_boosted) + (w_cash * (1 + m_raw))
                                    outlay  = w_cash
                                elif strat == "No-Sweat Bet":
                                    raw_pay = (w_promo * (1 + m_raw)) + (w_cash * (1 + m_raw))
                                    outlay  = w_total
                                else:
                                    raw_pay = (w_promo * (1 + m_boosted)) + (w_cash * (1 + m_raw))
                                    outlay  = w_total
                                return raw_pay, outlay, w_promo, w_cash

                            m1_raw = get_multiplier(o1['price'])
                            target_pay, outlay1, w1_promo, w1_cash = leg_payout(
                                sc['wager1'], sc['strat1'], sc['boost1'], m1_raw, sc['cap1_val']
                            )
                            w1_total = sc['wager1']

                            m2_raw     = get_multiplier(o2['price'])
                            m2_boosted = m2_raw * (1 + sc['boost2'] / 100) if sc['strat2'] == "Profit Boost (%)" else m2_raw
                            div_promo2 = m2_boosted if sc['strat2'] == "Bonus Bet" else (1 + m2_boosted)
                            div_cash2  = 1 + m2_raw

                            if sc['strat2'] != "Straight Cash" and sc['cap2_val'] > 0:
                                max_promo_pay2 = sc['cap2_val'] * div_promo2
                                if target_pay > max_promo_pay2:
                                    w2_promo = sc['cap2_val']
                                    w2_cash  = (target_pay - max_promo_pay2) / div_cash2
                                else:
                                    w2_promo = target_pay / div_promo2
                                    w2_cash  = 0.0
                            elif sc['strat2'] == "Straight Cash":
                                w2_promo, w2_cash = 0.0, target_pay / div_cash2
                            else:
                                w2_promo, w2_cash = target_pay / div_promo2, 0.0

                            w2_total = w2_promo + w2_cash
                            outlay2  = w2_cash if sc['strat2'] == "Bonus Bet" else w2_total

                            m3_raw     = get_multiplier(o3['price'])
                            m3_boosted = m3_raw * (1 + sc['boost3'] / 100) if sc['strat3'] == "Profit Boost (%)" else m3_raw
                            div_promo3 = m3_boosted if sc['strat3'] == "Bonus Bet" else (1 + m3_boosted)
                            div_cash3  = 1 + m3_raw

                            if sc['strat3'] != "Straight Cash" and sc['cap3_val'] > 0:
                                max_promo_pay3 = sc['cap3_val'] * div_promo3
                                if target_pay > max_promo_pay3:
                                    w3_promo = sc['cap3_val']
                                    w3_cash  = (target_pay - max_promo_pay3) / div_cash3
                                else:
                                    w3_promo = target_pay / div_promo3
                                    w3_cash  = 0.0
                            elif sc['strat3'] == "Straight Cash":
                                w3_promo, w3_cash = 0.0, target_pay / div_cash3
                            else:
                                w3_promo, w3_cash = target_pay / div_promo3, 0.0

                            w3_total = w3_promo + w3_cash
                            outlay3  = w3_cash if sc['strat3'] == "Bonus Bet" else w3_total

                            net_profit = target_pay - (outlay1 + outlay2 + outlay3)

                            soccer_opps.append({
                                "game":     f"{game.get('away_team')} vs {game.get('home_team')}",
                                "time":     commence_time.astimezone(CENTRAL).strftime("%m/%d %I:%M %p"),
                                "net_profit": net_profit,
                                "o1_book":  o1['book_title'], "o1_team": o1['team'], "o1_price": o1['price'],
                                "o1_wager": w1_total, "o1_promo": w1_promo, "o1_cash": w1_cash,
                                "o1_strat": sc['strat1'], "o1_boost": sc['boost1'] if sc['strat1'] == "Profit Boost (%)" else 0,
                                "o2_book":  o2['book_title'], "o2_team": o2['team'], "o2_price": o2['price'],
                                "o2_wager": w2_total, "o2_promo": w2_promo, "o2_cash": w2_cash,
                                "o2_strat": sc['strat2'], "o2_boost": sc['boost2'] if sc['strat2'] == "Profit Boost (%)" else 0,
                                "o3_book":  o3['book_title'], "o3_team": o3['team'], "o3_price": o3['price'],
                                "o3_wager": w3_total, "o3_promo": w3_promo, "o3_cash": w3_cash,
                                "o3_strat": sc['strat3'], "o3_boost": sc['boost3'] if sc['strat3'] == "Profit Boost (%)" else 0,
                            })

        status.update(label="Scan complete.", state="complete")

    seen = {}
    for op in soccer_opps:
        key = (op['game'], frozenset([op['o1_book'], op['o2_book'], op['o3_book']]))
        if key not in seen or op['net_profit'] > seen[key]['net_profit']:
            seen[key] = op
    return list(seen.values())


# ================================================================
# BET & GET ENGINE
# ================================================================
def run_bet_get_scan(bg):
    source_book_key    = book_map[bg['book']]
    allowed_hedge_keys = [v for k, v in book_map.items() if v != source_book_key]
    allowed_keys       = [source_book_key] + allowed_hedge_keys

    today_date    = datetime.now(CENTRAL).date()
    tomorrow_date = today_date + timedelta(days=1)

    bg_opps = []
    projected_bonus_value = bg['bonus_val'] * CONV_BETGET

    with st.status("Running scan...", expanded=False) as status:
        for sport_label in bg['sports']:
            sport_key = sports_map[sport_label]
            games, remaining = fetch_odds(sport_key, market='h2h')
            if not games:
                continue

            st.session_state.api_quota = remaining

            for game in games:
                commence_time   = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                game_date_local = commence_time.astimezone(CENTRAL).date()

                if game_date_local not in [today_date, tomorrow_date]:
                    continue

                flat_odds = build_flat_odds_h2h(game, allowed_keys)
                if not flat_odds:
                    continue

                unique_outcomes = list(set(o['team'] for o in flat_odds))
                game_label = f"{game.get('away_team')} vs {game.get('home_team')}"
                game_time  = commence_time.astimezone(CENTRAL).strftime("%m/%d %I:%M %p")

                if len(unique_outcomes) == 3:
                    odds_t1   = [o for o in flat_odds if o['team'] == unique_outcomes[0]]
                    odds_t2   = [o for o in flat_odds if o['team'] == unique_outcomes[1]]
                    odds_draw = [o for o in flat_odds if o['team'] == unique_outcomes[2]]

                    for o1 in odds_t1:
                        for o2 in odds_t2:
                            for o3 in odds_draw:
                                if o1['book_key'] == o2['book_key'] or \
                                   o1['book_key'] == o3['book_key'] or \
                                   o2['book_key'] == o3['book_key']:
                                    continue
                                if o1['book_key'] != source_book_key:
                                    continue

                                sm  = get_multiplier(o1['price'])
                                hm1 = get_multiplier(o2['price'])
                                hm2 = get_multiplier(o3['price'])

                                target_payout   = bg['wager'] * (1 + sm)
                                h1_stake        = target_payout / (1 + hm1)
                                h2_stake        = target_payout / (1 + hm2)
                                qualifying_loss = target_payout - bg['wager'] - h1_stake - h2_stake
                                net_promo_value = projected_bonus_value + qualifying_loss

                                bg_opps.append({
                                    "game": game_label, "sport": sport_label,
                                    "market_type": "3-way", "time": game_time,
                                    "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                                    "s_book": o1['book_title'], "s_team": o1['team'], "s_price": o1['price'], "s_wager": bg['wager'],
                                    "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "h1_wager": h1_stake,
                                    "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "h2_wager": h2_stake,
                                })

                elif len(unique_outcomes) == 2:
                    source_odds = [o for o in flat_odds if o['book_key'] == source_book_key]
                    hedge_odds  = [o for o in flat_odds if o['book_key'] in allowed_hedge_keys]

                    for s in source_odds:
                        opp_team = [t for t in unique_outcomes if t != s['team']]
                        if not opp_team: continue
                        eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team[0]]
                        if not eligible_hedges: continue

                        best_h          = max(eligible_hedges, key=lambda x: x['price'])
                        sm              = get_multiplier(s['price'])
                        hm              = get_multiplier(best_h['price'])
                        target_payout   = bg['wager'] * (1 + sm)
                        h_stake         = target_payout / (1 + hm)
                        qualifying_loss = target_payout - bg['wager'] - h_stake
                        net_promo_value = projected_bonus_value + qualifying_loss

                        bg_opps.append({
                            "game": game_label, "sport": sport_label,
                            "market_type": "2-way", "time": game_time,
                            "qualifying_loss": qualifying_loss, "net_value": net_promo_value,
                            "s_book": s['book_title'], "s_team": s['team'], "s_price": s['price'], "s_wager": bg['wager'],
                            "h1_book": best_h['book_title'], "h1_team": best_h['team'], "h1_price": best_h['price'], "h1_wager": h_stake,
                        })

        status.update(label="Scan complete.", state="complete")
    return bg_opps


# ================================================================
# RENDER FUNCTIONS
# ================================================================
def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} — {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)

    if not sorted_opps:
        st.warning("No profitable matches found.")
        return

    for i, op in enumerate(sorted_opps[:15]):
        boost_str   = f" | +{op['used_boost']}% Boost" if op.get('used_boost', 0) > 0 else ""
        market_str  = f" | {op.get('market_label', '')}" if op.get('market_label') else ""
        profit      = op['exact_profit']
        profit_sign = '+' if profit >= 0 else ''
        if op['strat'] == "Bonus Bet":
            bonus_wager = op.get('exact_w1', op.get('wager', 0))
            conv_rate   = (profit / bonus_wager * 100) if bonus_wager > 0 else 0
            conv_str    = f" ({conv_rate:.1f}% conv)"
        else:
            conv_str = ""
        header = f"#{i+1} | {op['time']} | {op['game']}{boost_str}{market_str} | {profit_sign}${profit:.2f}{conv_str}"

        with st.expander(header):
            if op.get('market_type') == "3-way":
                c1, c2, c3 = st.columns(3)
                with c1: st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['exact_w1']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c2: st.success(f"**{op['h1_book'].upper()}**\n\nStake: **${op['exact_hedge1']:.2f}**\n\nLine: **{op['h1_team']}** @ **{op['h1_price']:+}**")
                with c3: st.success(f"**{op['h2_book'].upper()}**\n\nStake: **${op['exact_hedge2']:.2f}**\n\nLine: **{op['h2_team']}** @ **{op['h2_price']:+}**")
            else:
                c_main, c_hedge = st.columns([1.5, 2])
                with c_main:  st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['wager']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c_hedge: st.success(f"**{op['h_book'].upper()}**\n\nStake: **${op['exact_hedge']:.2f}**\n\nLine: **{op['h_team']}** @ **{op['h_price']:+}**")
            st.metric("Net Arbitrage Profit", f"${op['exact_profit']:.2f}")


def display_soccer_results(opps):
    st.markdown("<div class='soccer-header'><h3>3-Way Soccer Engine Results</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['net_profit'], reverse=True)

    if not sorted_opps:
        st.warning("No matches found for your designated book criteria.")
        return

    for i, op in enumerate(sorted_opps[:10]):
        profit      = op['net_profit']
        profit_sign = "+" if profit >= 0 else ""
        header      = f"#{i+1} | {op['time']} | {op['game']} | {profit_sign}${profit:.2f}"

        with st.expander(header):
            cl1, cl2, cl3 = st.columns(3)

            def leg_card(col, label, book, strat, boost, wager, promo, cash, team, price, color_fn):
                if boost > 0:
                    promo_label = f"{strat} +{boost}%"
                    promo_help  = f"Profit boost of {boost}% applied to this leg's odds."
                else:
                    promo_label = strat
                    promo_help  = {
                        "Straight Cash": "Standard cash bet — no promo applied.",
                        "Bonus Bet":     "Bonus bet: stake not returned on win, only profit.",
                        "No-Sweat Bet":  "No-sweat: ~65% of stake refunded as bonus if lost.",
                    }.get(strat, "")
                show_breakdown = strat != "Straight Cash"
                sep  = "\n\n"
                body = f"**{book}**" + sep + f"*{promo_label}*" + sep + f"Total Bet: **${wager:.2f}**" + sep
                if show_breakdown:
                    body += f"\u21b3 Promo Stake: `${promo:.2f}`" + sep
                    if cash > 0:
                        body += f"\u21b3 Cash Top-Up: `${cash:.2f}`" + sep
                body += f"**{team} @ {price:+}**"
                with col:
                    color_fn(body)
                    st.caption(f"**{label}** — {promo_help}")

            leg_card(cl1, "BET 1", op['o1_book'], op['o1_strat'], op['o1_boost'],
                     op['o1_wager'], op['o1_promo'], op['o1_cash'], op['o1_team'], op['o1_price'], st.info)
            leg_card(cl2, "BET 2", op['o2_book'], op['o2_strat'], op['o2_boost'],
                     op['o2_wager'], op['o2_promo'], op['o2_cash'], op['o2_team'], op['o2_price'], st.success)
            leg_card(cl3, "BET 3", op['o3_book'], op['o3_strat'], op['o3_boost'],
                     op['o3_wager'], op['o3_promo'], op['o3_cash'], op['o3_team'], op['o3_price'], st.warning)

            banner_color  = "#16a34a" if profit >= 0 else "#dc2626"
            banner_bg     = "#f0fdf4" if profit >= 0 else "#fef2f2"
            banner_border = "#bbf7d0" if profit >= 0 else "#fecaca"
            st.markdown(
                f"<div style='margin-top:12px;padding:14px 20px;background:{banner_bg};"
                f"border:1px solid {banner_border};border-left:5px solid {banner_color};"
                f"border-radius:8px;display:flex;align-items:center;gap:16px;'>"
                f"<span style='font-size:0.85rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em;'>Net Profit</span>"
                f"<span style='font-size:1.5rem;font-family:monospace;font-weight:700;color:{banner_color};'>{profit_sign}${profit:.2f}</span>"
                f"</div>",
                unsafe_allow_html=True
            )


def display_bet_get_results(opps, bg):
    st.markdown(f"<div class='betget-header'><h3>Bet and Get Engine — {bg['book']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['net_value'], reverse=True)

    if not sorted_opps:
        st.warning("No tight lines found for qualification.")
        return

    for i, op in enumerate(sorted_opps[:10]):
        sign   = "+" if op['net_value'] >= 0 else ""
        header = f"#{i+1} | {op['time']} | {op['game']} | {sign}${op['net_value']:.2f}"

        with st.expander(header):
            st.caption(f"**League:** {op['sport']} | Market: {op['market_type'].upper()}")

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
            with mc2: st.metric("Net Value Lock (Est. 65% Convert)", f"${op['net_value']:.2f}")


# ================================================================
# HEADER
# ================================================================
c_title, c_quota = st.columns([3, 1])
with c_title:
    st.title("Promo Converter")
with c_quota:
    if 'api_quota' not in st.session_state:
        st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)

st.divider()

# ================================================================
# MAIN BOOST ENGINE
# ================================================================
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
                main_boost_val = st.number_input(
                    "Boost Value (%)", min_value=0, value=0, step=5,
                    help="Only applies if Promo Type is set to Profit Boost (%)",
                    disabled=(s != "Profit Boost (%)")
                )
        with col3:
            with st.container(border=True):
                hb = st.multiselect("Hedge Book(s)", list(book_map.keys()), placeholder="All Books")
        with col4:
            with st.container(border=True):
                sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=[], placeholder="Select sports...")

        promo_submit = st.form_submit_button("Scan")

    if promo_submit:
        active_sports = sp if sp else list(sports_map.keys())
        p_config = {
            "book": b, "strat": s, "boost_val": main_boost_val,
            "wager": w, "hedge_books": hb, "sports": active_sports
        }
        results = run_promo_scan(p_config)
        display_results(results, p_config)


# ================================================================
# 3-WAY SOCCER ENGINE
# ================================================================
with st.expander("3-Way Soccer Engine", expanded=False):
    with st.form("soccer_form"):
        today         = datetime.now(CENTRAL).date()
        lookahead_end = today + timedelta(days=2)

        st.divider()

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            with st.container(border=True):
                st.subheader("Bet 1")
                sb1   = st.selectbox("Book", list(book_map.keys()), index=0, key="sc_book1")
                ss1   = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type1")
                sbv1  = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost1")
                sw1   = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake1")
                scap1 = st.number_input("Promo Cap ($)", min_value=0.0, value=0.0, help="Max stake eligible for promo. 0 = no cap.", key="sc_cap1")
        with sc2:
            with st.container(border=True):
                st.subheader("Bet 2")
                sb2   = st.multiselect("Book(s)", list(book_map.keys()), default=[], placeholder="Select books...", key="sc_book2")
                ss2   = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type2")
                sbv2  = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost2")
                sw2   = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake2")
                scap2 = st.number_input("Promo Cap ($)", min_value=0.0, value=0.0, help="Max stake eligible for promo. 0 = no cap.", key="sc_cap2")
        with sc3:
            with st.container(border=True):
                st.subheader("Bet 3")
                sb3   = st.multiselect("Book(s)", list(book_map.keys()), default=[], placeholder="Select books...", key="sc_book3")
                ss3   = st.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="sc_type3")
                sbv3  = st.number_input("Boost %", min_value=0, value=0, step=5, key="sc_boost3")
                sw3   = st.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key="sc_stake3")
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


# ================================================================
# BET & GET ENGINE
# ================================================================
with st.expander("Bet and Get Engine", expanded=False):
    with st.form("bet_get_form"):
        bgc1, bgc2 = st.columns(2)
        with bgc1:
            with st.container(border=True):
                bg_b = st.selectbox("Book", list(book_map.keys()))
                bg_w = st.number_input("Qual. Stake ($)", min_value=0.0, value=0.0, step=5.0)
        with bgc2:
            with st.container(border=True):
                bg_v  = st.number_input("Bonus Value ($)", min_value=0.0, value=0.0, step=5.0)
                bg_sp = st.multiselect("Sports", list(sports_map.keys()), default=[])

        bg_submit = st.form_submit_button("Scan")

    if bg_submit:
        bg_config = {"book": bg_b, "wager": bg_w, "bonus_val": bg_v, "sports": bg_sp}
        bg_results = run_bet_get_scan(bg_config)
        display_bet_get_results(bg_results, bg_config)
