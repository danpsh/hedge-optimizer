import streamlit as st
import requests
from datetime import datetime, timezone, timedelta
from itertools import permutations

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter Master", layout="wide")

# Local time for game display: auto-handles CST/CDT. Falls back to a fixed
# CDT offset if the tz database isn't present on the host.
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Chicago")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=-5))

def fmt_local(commence_utc):
    return commence_utc.astimezone(LOCAL_TZ).strftime("%m/%d %I:%M %p")

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

# Main Boost Engine is 2-way only; soccer (3-way) is owned by the soccer engine.
two_way_sports = [k for k in sports_map.keys() if k != "FIFA World Cup"]

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

# --- MAIN BOOST ENGINE (2-WAY MARKETS ONLY) ---
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

                    # 2-WAY MARKETS ONLY (soccer/3-way handled by the soccer engine)
                    if len(unique_outcomes) != 2:
                        continue

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
                                    "time": fmt_local(commence_time),
                                    "exact_profit": exact_profit, "exact_hedge": raw_h,
                                    "s_team": s['team'], "s_book": s['book_title'], "s_price": s['price'],
                                    "h_book": best_h['book_title'], "h_team": best_h['team'], "h_price": best_h['price'],
                                    "wager": p['wager'], "strat": p['strat'], "used_boost": p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0
                                })
            else:
                st.error(f"Could not fetch data for {sport_label}")
        status.update(label="Scan Complete", state="complete")
    return all_opps


# --- ENGINE: SOCCER 3-WAY MATRIX (PROMO + CAP/CASH SPLIT, ALL-PERMUTATION OPTIMIZER) ---
# Each of the 3 chosen books carries its own promo config (strat / boost / cap).
# Book 1 is the anchor: its bet size is fixed and sets the equal-payout target.
# The engine tries every book->outcome assignment per game and keeps the best,
# so a book's promo lands on whichever outcome maximizes the locked profit.
def run_multi_book_soccer_scan(sc):
    ordered_books = [book_map[sc['book1']], book_map[sc['book2']], book_map[sc['book3']]]
    leg_cfgs = [
        {'strat': sc['strat1'], 'boost': sc['boost1'], 'cap': sc['cap1_val']},
        {'strat': sc['strat2'], 'boost': sc['boost2'], 'cap': sc['cap2_val']},
        {'strat': sc['strat3'], 'boost': sc['boost3'], 'cap': sc['cap3_val']},
    ]
    anchor_wager = sc['wager1']
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    soccer_opps = []

    def anchor_calc(price, cfg, wager):
        w_total = wager
        w_promo, w_cash = w_total, 0.0
        if cfg['strat'] != "Straight Cash" and cfg['cap'] > 0 and w_total > cfg['cap']:
            w_promo = cfg['cap']
            w_cash = w_total - cfg['cap']
        m_raw = get_multiplier(price)
        m_boost = m_raw * (1 + cfg['boost'] / 100) if cfg['strat'] == "Profit Boost (%)" else m_raw
        if cfg['strat'] == "Bonus Bet":
            target = w_promo * m_boost + w_cash * (1 + m_raw)
            outlay = w_cash
        else:  # Straight Cash / Profit Boost / No-Sweat
            target = w_promo * (1 + m_boost) + w_cash * (1 + m_raw)
            outlay = w_total
        return target, outlay, w_total, w_promo, w_cash

    def hedge_calc(price, target, cfg):
        m_raw = get_multiplier(price)
        m_boost = m_raw * (1 + cfg['boost'] / 100) if cfg['strat'] == "Profit Boost (%)" else m_raw
        div_promo = m_boost if cfg['strat'] == "Bonus Bet" else (1 + m_boost)
        div_cash = 1 + m_raw
        if cfg['strat'] != "Straight Cash" and cfg['cap'] > 0:
            max_promo_payout = cfg['cap'] * div_promo
            if target > max_promo_payout:
                w_promo = cfg['cap']
                w_cash = (target - max_promo_payout) / div_cash
            else:
                w_promo = target / div_promo if div_promo else 0.0
                w_cash = 0.0
        else:
            if cfg['strat'] == "Straight Cash":
                w_promo = 0.0
                w_cash = target / div_cash
            else:
                w_promo = target / div_promo if div_promo else 0.0
                w_cash = 0.0
        w_total = w_promo + w_cash
        outlay = w_cash if cfg['strat'] == "Bonus Bet" else w_total
        return w_total, w_promo, w_cash, outlay

    def boost_shown(cfg):
        return cfg['boost'] if cfg['strat'] == "Profit Boost (%)" else 0

    with st.status("Optimizing multi-book 3-way soccer lines...", expanded=False) as status:
        games, remaining = fetch_odds(sports_map["FIFA World Cup"])
        if games:
            st.session_state.api_quota = remaining
            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit:
                    continue

                # price/title lookups restricted to the three chosen books
                price = {bk: {} for bk in ordered_books}
                title = {}
                outcomes_set = set()
                for bm in game['bookmakers']:
                    if bm['key'] in price:
                        title[bm['key']] = bm['title']
                        for o in bm['markets'][0]['outcomes']:
                            price[bm['key']][o['name']] = o['price']
                            outcomes_set.add(o['name'])

                if len(outcomes_set) != 3:
                    continue
                outcomes = list(outcomes_set)

                best = None
                # perm[i] is the outcome assigned to ordered_books[i]
                for perm in permutations(outcomes):
                    p1 = price[ordered_books[0]].get(perm[0])
                    p2 = price[ordered_books[1]].get(perm[1])
                    p3 = price[ordered_books[2]].get(perm[2])
                    if p1 is None or p2 is None or p3 is None:
                        continue

                    target, outlay1, w1t, w1p, w1c = anchor_calc(p1, leg_cfgs[0], anchor_wager)
                    w2t, w2p, w2c, outlay2 = hedge_calc(p2, target, leg_cfgs[1])
                    w3t, w3p, w3c, outlay3 = hedge_calc(p3, target, leg_cfgs[2])
                    net_profit = target - (outlay1 + outlay2 + outlay3)

                    if best is None or net_profit > best['net_profit']:
                        best = {
                            'net_profit': net_profit,
                            'legs': [
                                {'team': perm[0], 'price': p1, 'total': w1t, 'promo': w1p, 'cash': w1c, 'cfg': leg_cfgs[0], 'book': title[ordered_books[0]]},
                                {'team': perm[1], 'price': p2, 'total': w2t, 'promo': w2p, 'cash': w2c, 'cfg': leg_cfgs[1], 'book': title[ordered_books[1]]},
                                {'team': perm[2], 'price': p3, 'total': w3t, 'promo': w3p, 'cash': w3c, 'cfg': leg_cfgs[2], 'book': title[ordered_books[2]]},
                            ]
                        }

                if best is not None:
                    L = best['legs']
                    soccer_opps.append({
                        "game": f"{game.get('away_team')} vs {game.get('home_team')}",
                        "time": fmt_local(commence_time),
                        "net_profit": best['net_profit'],
                        "o1_book": L[0]['book'], "o1_team": L[0]['team'], "o1_price": L[0]['price'], "o1_wager": L[0]['total'], "o1_promo": L[0]['promo'], "o1_cash": L[0]['cash'], "o1_strat": L[0]['cfg']['strat'], "o1_boost": boost_shown(L[0]['cfg']),
                        "o2_book": L[1]['book'], "o2_team": L[1]['team'], "o2_price": L[1]['price'], "o2_wager": L[1]['total'], "o2_promo": L[1]['promo'], "o2_cash": L[1]['cash'], "o2_strat": L[1]['cfg']['strat'], "o2_boost": boost_shown(L[1]['cfg']),
                        "o3_book": L[2]['book'], "o3_team": L[2]['team'], "o3_price": L[2]['price'], "o3_wager": L[2]['total'], "o3_promo": L[2]['promo'], "o3_cash": L[2]['cash'], "o3_strat": L[2]['cfg']['strat'], "o3_boost": boost_shown(L[2]['cfg']),
                    })
        status.update(label="Soccer Engine Optimization Complete", state="complete")
    return soccer_opps


# --- DEDICATED BET & GET SCAN ENGINE ---
def run_bet_get_scan(bg):
    source_book_key = book_map[bg['book']]
    allowed_hedge_keys = [v for k, v in book_map.items() if v != source_book_key]
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    bg_opps = []

    projected_bonus_value = bg['bonus_val'] * 0.70

    with st.status(f"Hunting cheapest qualification routes for {bg['book']}...", expanded=False) as status:
        for sport_label in bg['sports']:
            sport_key = sports_map[sport_label]
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

# --- RENDER FUNCTIONS ---
def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} - {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)

    if not sorted_opps:
        st.warning("No profitable 2-way matches found.")
    else:
        for i, op in enumerate(sorted_opps[:15]):
            conv_str = f" | Using {op['used_boost']}% Boost" if op.get('used_boost', 0) > 0 else ""
            header_title = f"RANK {i+1} | {op['time']} | {op['game']}{conv_str} | Profit: ${op['exact_profit']:.2f}"

            with st.expander(header_title):
                c_main, c_hedge = st.columns([1.5, 2])
                with c_main:
                    st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['wager']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c_hedge:
                    st.success(f"**{op['h_book'].upper()}**\n\nStake: **${op['exact_hedge']:.2f}**\n\nLine: **{op['h_team']}** @ **{op['h_price']:+}**")
                st.metric("Net Arbitrage Profit", f"${op['exact_profit']:.2f}")

def display_soccer_results(opps):
    st.markdown("<div class='soccer-header'><h3>Optimized Multi-Book Soccer Arbitrage Paths</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['net_profit'], reverse=True)

    if not sorted_opps:
        st.warning("No matches pairing your designated book criteria were discovered.")
    else:
        for i, op in enumerate(sorted_opps[:10]):
            header = f"SOCCER MATCH {i+1} | Return: ${op['net_profit']:.2f} | {op['time']} | {op['game']}"
            with st.expander(header):
                cl1, cl2, cl3 = st.columns(3)

                with cl1:
                    b1_str = f" ({op['o1_strat']} +{op['o1_boost']}% 🎉)" if op['o1_boost'] > 0 else f" ({op['o1_strat']})"
                    st.info(f"**OUTCOME 1**\n\n**{op['o1_book']}**\n*{b1_str}*\n\nTotal Bet: **${op['o1_wager']:.2f}**\n\n↳ Booster Stake: `${op['o1_promo']:.2f}`\n\n↳ Cash Override: `${op['o1_cash']:.2f}`\n\n{op['o1_team']} @ {op['o1_price']:+}")

                with cl2:
                    b2_str = f" ({op['o2_strat']} +{op['o2_boost']}% 🎉)" if op['o2_boost'] > 0 else f" ({op['o2_strat']})"
                    st.success(f"**OUTCOME 2**\n\n**{op['o2_book']}**\n*{b2_str}*\n\nTotal Bet: **${op['o2_wager']:.2f}**\n\n↳ Booster Stake: `${op['o2_promo']:.2f}`\n\n↳ Cash Override: `${op['o2_cash']:.2f}`\n\n{op['o2_team']} @ {op['o2_price']:+}")

                with cl3:
                    b3_str = f" ({op['o3_strat']} +{op['o3_boost']}% 🎉)" if op['o3_boost'] > 0 else f" ({op['o3_strat']})"
                    st.warning(f"**OUTCOME 3**\n\n**{op['o3_book']}**\n*{b3_str}*\n\nTotal Bet: **${op['o3_wager']:.2f}**\n\n↳ Booster Stake: `${op['o3_promo']:.2f}`\n\n↳ Cash Override: `${op['o3_cash']:.2f}`\n\n{op['o3_team']} @ {op['o3_price']:+}")

                st.metric("Risk-Free Profit Generated", f"${op['net_profit']:.2f}")

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

# --- INITIALIZE STATE QUEUES ---
if 'promos' not in st.session_state:
    st.session_state.promos = []

# ========================================================
# TOP MODULE: MAIN BOOST ENGINE (2-WAY)
# ========================================================
with st.expander("Main Boost Engine (2-Way)", expanded=True):
    with st.form("promo_form", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
            main_boost_val = st.number_input("Boost Value (%)", min_value=0, value=0, step=5, help="Only applies if Promo Type is set to Profit Boost (%)", disabled=(s != "Profit Boost (%)"))
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=5.0)
        with col3:
            hb = st.multiselect("Hedge Book(s)", [k for k in book_map.keys() if k != b], placeholder="All Books")
        with col4:
            sp = st.multiselect("Sports Filter", two_way_sports, default=[], placeholder="Select sports...")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: add_to_q = st.form_submit_button("Add to Queue", use_container_width=True)
        with btn_col2: quick_scan = st.form_submit_button("Quick Scan", use_container_width=True)

# --- EXECUTE TOP CONFIG ACTIONS ---
if quick_scan:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        temp_p = {"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "boost_val": main_boost_val}
        results = run_promo_scan(temp_p)
        display_results(results, temp_p)

if add_to_q:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb, "boost_val": main_boost_val})

# --- RENDER SCAN QUEUE AREA ---
if st.session_state.promos:
    st.subheader("Scan Queue")
    for i, p in enumerate(st.session_state.promos):
        q_col1, q_col2 = st.columns([9.2, 0.8])
        with q_col1:
            hedge_label = ", ".join(p['hedge_books']) if p['hedge_books'] else "ALL"
            boost_str = f" (+{p['boost_val']}% Boost)" if p['strat'] == "Profit Boost (%)" else ""
            st.info(f"**{p['book'].upper()}** vs **{hedge_label}** | {p['strat']}{boost_str} | ${p['wager']} | {', '.join(p['sports'])}")
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

st.write("")
st.divider()

# ========================================================
# MIDDLE MODULE: MULTI-BOOK SOCCER ENGINE (PROMO + CAP/CASH SPLIT)
# ========================================================
st.markdown("### ⚽ Multi-Book Soccer Booster Engine (3-Way Leg Configs)")
with st.expander("Configure Multi-Source Book Soccer Boost Options", expanded=True):
    st.caption("Each book carries its own promo. Book 1 is the anchor (fixed bet size). "
               "The engine assigns each book to whichever outcome locks the most profit.")
    sc_c1, sc_c2, sc_c3 = st.columns(3)

    with sc_c1:
        st.subheader("Book 1 (Anchor)")
        sb1 = st.selectbox("Bookmaker leg A", list(book_map.keys()), index=0, key="sb1_k")
        sw1 = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=5.0, key="sw1_k", help="Base stake size to anchor the remaining leg math from.")
        ss1 = st.selectbox("Booster Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=1, key="ss1_k")
        cap1_val = st.number_input("Booster Wager ($)", min_value=0.0, value=0.0, step=5.0, key="cv1", help="Max promo-eligible stake. Overflow rolls to cash. 0 = no cap.", disabled=(ss1 == "Straight Cash"))
        sbo1 = st.number_input("Booster Value (%)", min_value=0, value=0, step=5, key="sbo1_k", disabled=(ss1 != "Profit Boost (%)"))

    with sc_c2:
        st.subheader("Book 2 (Leg B)")
        sb2 = st.selectbox("Bookmaker Leg B", list(book_map.keys()), index=1, key="sb2_k")
        ss2 = st.selectbox("Booster Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="ss2_k")
        cap2_val = st.number_input("Booster Wager ($)", min_value=0.0, value=0.0, step=5.0, key="cv2", help="Max promo-eligible stake. 0 = no cap.", disabled=(ss2 == "Straight Cash"))
        sbo2 = st.number_input("Booster Value (%)", min_value=0, value=0, step=5, key="sbo2_k", disabled=(ss2 != "Profit Boost (%)"))

    with sc_c3:
        st.subheader("Book 3 (Leg C)")
        sb3 = st.selectbox("Bookmaker Leg C", list(book_map.keys()), index=2, key="sb3_k")
        ss3 = st.selectbox("Booster Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="ss3_k")
        cap3_val = st.number_input("Booster Wager ($)", min_value=0.0, value=0.0, step=5.0, key="cv3", help="Max promo-eligible stake. 0 = no cap.", disabled=(ss3 == "Straight Cash"))
        sbo3 = st.number_input("Booster Value (%)", min_value=0, value=0, step=5, key="sbo3_k", disabled=(ss3 != "Profit Boost (%)"))

    if st.button("Execute Soccer Multi-Boost Optimization Scan", use_container_width=True):
        if sw1 <= 0:
            st.error("Please enter an initial Book 1 Wager Amount to establish base conversion targeting.")
        elif sb1 == sb2 or sb1 == sb3 or sb2 == sb3:
            st.error("Error: All 3 legs must be assigned to separate, distinct bookmakers to verify arbitrage coverage.")
        else:
            sc_payload = {
                "book1": sb1, "wager1": sw1, "strat1": ss1, "boost1": sbo1, "cap1_val": cap1_val,
                "book2": sb2, "strat2": ss2, "boost2": sbo2, "cap2_val": cap2_val,
                "book3": sb3, "strat3": ss3, "boost3": sbo3, "cap3_val": cap3_val
            }
            sc_results = run_multi_book_soccer_scan(sc_payload)
            st.session_state.soccer_results_cache = sc_results

if 'soccer_results_cache' in st.session_state:
    display_soccer_results(st.session_state.soccer_results_cache)
    if st.button("Clear Soccer Grid Display", use_container_width=True):
        del st.session_state.soccer_results_cache
        st.rerun()

st.write("")
st.divider()

# ========================================================
# BOTTOM MODULE: BET & GET FINDER
# ========================================================
st.markdown("### 🟢 Bet & Get Finder (No Boost Required)")
with st.expander("Configure Bet & Get Promotion Parameters", expanded=False):
    bg_book = st.selectbox("Qualifying Bookmaker Target", list(book_map.keys()), key="bg_b")

    col_w, col_v = st.columns(2)
    with col_w:
        bg_wager = st.number_input("Required Wager Amount ($)", min_value=0.0, value=0.0, key="bg_w")
    with col_v:
        bg_bonus = st.number_input("Bonus Bet Reward Expected ($)", min_value=0.0, value=0.0, key="bg_bon")

    bg_sports = st.multiselect("Leagues to Search", list(sports_map.keys()), default=[], key="bg_s", placeholder="Select sports...")

    if st.button("Find Cheapest Qualification Paths", use_container_width=True):
        if bg_wager <= 0 or bg_bonus <= 0 or not bg_sports:
            st.error("Fill out all parameters and select at least one league.")
        else:
            bg_payload = {"book": bg_book, "wager": bg_wager, "bonus_val": bg_bonus, "sports": bg_sports}
            bg_results = run_bet_get_scan(bg_payload)
            st.session_state.bg_results_cache = (bg_results, bg_payload)

if 'bg_results_cache' in st.session_state:
    display_bet_get_results(st.session_state.bg_results_cache[0], st.session_state.bg_results_cache[1])
    if st.button("Clear Bet & Get Display", use_container_width=True):
        del st.session_state.bg_results_cache
        st.rerun()
