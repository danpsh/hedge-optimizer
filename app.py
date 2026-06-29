import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Promo Converter", layout="wide")

CENTRAL      = ZoneInfo("America/Chicago")
CONV_NOSWEAT = 0.65
CONV_BETGET  = 0.65

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto+Mono&display=swap');
    .stApp { background-color: #f8fafc; color: #1e293b; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #0f172a !important; font-weight: 700 !important; }
    div[data-testid="stExpander"] { background-color:#ffffff !important; border:1px solid #e2e8f0 !important; border-radius:12px !important; box-shadow:0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color:#1e293b !important; color:#ffffff !important; border-radius:6px !important; font-weight:600 !important; }
    [data-testid="stMetricValue"] { font-family:'Roboto Mono',monospace; font-size:1.4rem !important; }
    [data-testid="stExpander"] summary { font-size:0.95rem !important; font-weight:500 !important; font-family:'Inter',sans-serif !important; }
    .promo-header  { background-color:#e2e8f0; padding:10px; border-radius:8px; margin-top:20px; margin-bottom:10px; border-left:5px solid #1e293b; }
    .soccer-header { background-color:#f0f9ff; padding:10px; border-radius:8px; margin-top:20px; margin-bottom:10px; border-left:5px solid #0284c7; }
    .betget-header { background-color:#f0fdf4; padding:10px; border-radius:8px; margin-top:20px; margin-bottom:10px; border-left:5px solid #16a34a; }
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] { align-items:stretch; }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] { background-color:#ffffff; border:1px solid #e2e8f0 !important; border-radius:12px !important; box-shadow:0 2px 4px rgba(0,0,0,0.05); height:100%; padding:0.6rem 0.8rem !important; }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] { gap:0.4rem !important; }
    </style>""", unsafe_allow_html=True)

API_KEY = st.secrets.get("ODDS_API_KEY", "")

book_map = {
    "DraftKings": "draftkings", "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet", "BetMGM": "betmgm"
}
sports_map = {
    "WNBA": "basketball_wnba", "MLB": "baseball_mlb",
    "FIFA World Cup": "soccer_fifa_world_cup"
}

def get_multiplier(o): return (o / 100) if o > 0 else (100 / abs(o))

@st.cache_data(ttl=300)
def fetch_odds(sport_key, market='h2h'):
    try:
        res = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
            params={'apiKey': API_KEY, 'regions': 'us,us2', 'markets': market, 'oddsFormat': 'american'},
            timeout=10
        )
        if res.status_code == 200:
            return res.json(), res.headers.get('x-requests-remaining', "0")
    except requests.exceptions.RequestException:
        pass
    return None, "Error"

def get_h2h(bm): return next((m for m in bm['markets'] if m['key'] == 'h2h'), None)

def flat_h2h(game, keys, exact_count=None):
    flat = []
    for bm in game['bookmakers']:
        if bm['key'] not in keys: continue
        m = get_h2h(bm)
        if not m or (exact_count and len(m['outcomes']) != exact_count): continue
        flat += [{'book_key': bm['key'], 'book_title': bm['title'], 'team': o['name'], 'price': o['price']} for o in m['outcomes']]
    return flat

def calc_profit(strat, wager, sm, hm, boost=0):
    if strat == "Profit Boost (%)":
        sm = sm * (1 + boost / 100)
        pay = wager * (1 + sm); h = pay / (1 + hm); return pay - wager - h, h
    elif strat == "Bonus Bet":
        pay = wager * sm; h = pay / (1 + hm); return pay - h, h
    else:  # No-Sweat
        pay = wager * (1 + sm); h = (pay - wager * CONV_NOSWEAT) / (1 + hm); return pay - wager - h, h

def leg_payout(w_total, strat, boost_pct, m_raw, cap_val):
    m_b = m_raw * (1 + boost_pct / 100) if strat == "Profit Boost (%)" else m_raw
    if strat != "Straight Cash" and cap_val > 0 and w_total > cap_val:
        wp, wc = cap_val, w_total - cap_val
    else:
        wp, wc = (w_total, 0.0) if strat != "Straight Cash" else (0.0, w_total)
    if strat == "Bonus Bet":
        return (wp * m_b) + (wc * (1 + m_raw)), wc, wp, wc
    elif strat == "No-Sweat Bet":
        return (w_total * (1 + m_raw)), w_total, wp, wc
    else:
        return (wp * (1 + m_b)) + (wc * (1 + m_raw)), w_total, wp, wc

def today_tomorrow():
    t = datetime.now(CENTRAL).date()
    return t, t + timedelta(days=1)

def local_date(commence_time):
    return datetime.fromisoformat(commence_time.replace('Z', '+00:00')).astimezone(CENTRAL)

# ================================================================
# MAIN BOOST ENGINE
# ================================================================
def run_promo_scan(p):
    src_key = book_map[p['book']]
    hedge_keys = [book_map[b] for b in p['hedge_books'] if book_map[b] != src_key] if p['hedge_books'] else [v for k, v in book_map.items() if v != src_key]
    all_keys = [src_key] + hedge_keys
    today, tomorrow = today_tomorrow()
    all_opps = []

    with st.status("Running scan...", expanded=False) as status:
        for sport in p['sports']:
            games, remaining = fetch_odds(sports_map[sport])
            if not games: st.error(f"No data for {sport}"); continue
            st.session_state.api_quota = remaining

            for game in games:
                ct = local_date(game['commence_time'])
                if ct.date() not in [today, tomorrow]: continue

                flat = flat_h2h(game, all_keys)
                if not flat: continue
                label = f"{game.get('away_team','Away')} vs {game.get('home_team','Home')}"
                gtime = ct.strftime("%m/%d %I:%M %p")
                teams = list(set(o['team'] for o in flat))

                if len(teams) == 2:
                    for s in [o for o in flat if o['book_key'] == src_key]:
                        opp = [t for t in teams if t != s['team']]
                        if not opp: continue
                        eligible = [h for h in flat if h['book_key'] in hedge_keys and h['team'] == opp[0]]
                        if not eligible: continue
                        best_h = max(eligible, key=lambda x: x['price'])
                        profit, raw_h = calc_profit(p['strat'], p['wager'], get_multiplier(s['price']), get_multiplier(best_h['price']), p['boost_val'])
                        if profit > -10.0:
                            all_opps.append({"game": label, "sport": sport, "market_type": "2-way", "time": gtime,
                                "exact_profit": profit, "exact_hedge": raw_h, "wager": p['wager'], "strat": p['strat'],
                                "s_team": s['team'], "s_book": s['book_title'], "s_price": s['price'],
                                "h_book": best_h['book_title'], "h_team": best_h['team'], "h_price": best_h['price'],
                                "used_boost": p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0})

                elif len(teams) == 3:
                    src_legs = [o for o in flat if o['book_key'] == src_key]
                    for src in src_legs:
                        hedge_pool = [o for o in flat if o['book_key'] in hedge_keys]
                        other_teams = [t for t in teams if t != src['team']]
                        # For each pair of hedge books covering the other two outcomes
                        for h1 in [o for o in hedge_pool if o['team'] == other_teams[0]]:
                            for h2 in [o for o in hedge_pool if o['team'] == other_teams[1] and o['book_key'] != h1['book_key']]:
                                sm = get_multiplier(src['price'])
                                hm1, hm2 = get_multiplier(h1['price']), get_multiplier(h2['price'])
                                if p['strat'] == "Profit Boost (%)":
                                    sm_eff = sm * (1 + p['boost_val'] / 100)
                                    pay = p['wager'] * (1 + sm_eff)
                                    s1, s2 = pay / (1 + hm1), pay / (1 + hm2)
                                    profit = pay - p['wager'] - s1 - s2
                                elif p['strat'] == "Bonus Bet":
                                    pay = p['wager'] * sm
                                    s1, s2 = pay / (1 + hm1), pay / (1 + hm2)
                                    profit = pay - s1 - s2
                                else:
                                    pay = p['wager'] * (1 + sm)
                                    s1 = (pay - p['wager'] * CONV_NOSWEAT) / (1 + hm1)
                                    s2 = (pay - p['wager'] * CONV_NOSWEAT) / (1 + hm2)
                                    profit = pay - p['wager'] - s1 - s2
                                if profit > -10.0:
                                    all_opps.append({"game": label, "sport": sport, "market_type": "3-way", "time": gtime,
                                        "exact_profit": profit, "wager": p['wager'], "strat": p['strat'],
                                        "s_team": src['team'], "s_book": src['book_title'], "s_price": src['price'], "exact_w1": p['wager'],
                                        "h1_book": h1['book_title'], "h1_team": h1['team'], "h1_price": h1['price'], "exact_hedge1": s1,
                                        "h2_book": h2['book_title'], "h2_team": h2['team'], "h2_price": h2['price'], "exact_hedge2": s2,
                                        "used_boost": p['boost_val'] if p['strat'] == "Profit Boost (%)" else 0})

        status.update(label="Scan complete.", state="complete")

    seen = {}
    for op in all_opps:
        key = (op['game'], op['s_book'], frozenset([op['s_book'], op.get('h1_book', op.get('h_book')), op.get('h2_book', op.get('h_book'))]))
        if key not in seen or op['exact_profit'] > seen[key]['exact_profit']:
            seen[key] = op
    return list(seen.values())


# ================================================================
# 3-WAY SOCCER ENGINE
# ================================================================
def run_multi_book_soccer_scan(sc):
    book1_key  = book_map[sc['book1']]
    book2_keys = [book_map[b] for b in sc['book2']] if sc['book2'] else list(book_map.values())
    book3_keys = [book_map[b] for b in sc['book3']] if sc['book3'] else list(book_map.values())
    today = datetime.now(CENTRAL).date()
    opps  = []

    with st.status("Running scan...", expanded=False) as status:
        for league in sc['leagues']:
            games, remaining = fetch_odds(sports_map[league])
            if not games: continue
            st.session_state.api_quota = remaining

            for game in games:
                ct = local_date(game['commence_time'])
                if not (today <= ct.date() <= sc['lookahead_end_date']): continue

                flat = flat_h2h(game, list(book_map.values()), exact_count=3)
                if not flat: continue
                teams = list(set(o['team'] for o in flat))
                if len(teams) != 3: continue

                for t1, t2, td in [(teams[0], teams[1], teams[2])]:
                    for o1 in [o for o in flat if o['team'] == t1 and o['book_key'] == book1_key]:
                        for o2 in [o for o in flat if o['team'] == t2 and o['book_key'] in book2_keys]:
                            for o3 in [o for o in flat if o['team'] == td and o['book_key'] in book3_keys]:
                                if len({o1['book_key'], o2['book_key'], o3['book_key']}) != 3: continue

                                m1 = get_multiplier(o1['price'])
                                pay, out1, wp1, wc1 = leg_payout(sc['wager1'], sc['strat1'], sc['boost1'], m1, sc['cap1_val'])

                                m2 = get_multiplier(o2['price'])
                                m2b = m2 * (1 + sc['boost2']/100) if sc['strat2'] == "Profit Boost (%)" else m2
                                dp2 = m2b if sc['strat2'] == "Bonus Bet" else (1 + m2b)
                                if sc['strat2'] != "Straight Cash" and sc['cap2_val'] > 0:
                                    mp2 = sc['cap2_val'] * dp2
                                    wp2, wc2 = (sc['cap2_val'], (pay - mp2) / (1 + m2)) if pay > mp2 else (pay / dp2, 0.0)
                                elif sc['strat2'] == "Straight Cash": wp2, wc2 = 0.0, pay / (1 + m2)
                                else: wp2, wc2 = pay / dp2, 0.0
                                out2 = wc2 if sc['strat2'] == "Bonus Bet" else (wp2 + wc2)

                                m3 = get_multiplier(o3['price'])
                                m3b = m3 * (1 + sc['boost3']/100) if sc['strat3'] == "Profit Boost (%)" else m3
                                dp3 = m3b if sc['strat3'] == "Bonus Bet" else (1 + m3b)
                                if sc['strat3'] != "Straight Cash" and sc['cap3_val'] > 0:
                                    mp3 = sc['cap3_val'] * dp3
                                    wp3, wc3 = (sc['cap3_val'], (pay - mp3) / (1 + m3)) if pay > mp3 else (pay / dp3, 0.0)
                                elif sc['strat3'] == "Straight Cash": wp3, wc3 = 0.0, pay / (1 + m3)
                                else: wp3, wc3 = pay / dp3, 0.0
                                out3 = wc3 if sc['strat3'] == "Bonus Bet" else (wp3 + wc3)

                                opps.append({
                                    "game": f"{game.get('away_team')} vs {game.get('home_team')}",
                                    "time": ct.strftime("%m/%d %I:%M %p"), "net_profit": pay - out1 - out2 - out3,
                                    "o1_book": o1['book_title'], "o1_team": o1['team'], "o1_price": o1['price'], "o1_wager": sc['wager1'], "o1_promo": wp1, "o1_cash": wc1, "o1_strat": sc['strat1'], "o1_boost": sc['boost1'] if sc['strat1'] == "Profit Boost (%)" else 0,
                                    "o2_book": o2['book_title'], "o2_team": o2['team'], "o2_price": o2['price'], "o2_wager": wp2+wc2, "o2_promo": wp2, "o2_cash": wc2, "o2_strat": sc['strat2'], "o2_boost": sc['boost2'] if sc['strat2'] == "Profit Boost (%)" else 0,
                                    "o3_book": o3['book_title'], "o3_team": o3['team'], "o3_price": o3['price'], "o3_wager": wp3+wc3, "o3_promo": wp3, "o3_cash": wc3, "o3_strat": sc['strat3'], "o3_boost": sc['boost3'] if sc['strat3'] == "Profit Boost (%)" else 0,
                                })

        status.update(label="Scan complete.", state="complete")

    seen = {}
    for op in opps:
        key = (op['game'], frozenset([op['o1_book'], op['o2_book'], op['o3_book']]))
        if key not in seen or op['net_profit'] > seen[key]['net_profit']: seen[key] = op
    return list(seen.values())


# ================================================================
# BET & GET ENGINE
# ================================================================
def run_bet_get_scan(bg):
    src_key   = book_map[bg['book']]
    hedge_keys = [v for k, v in book_map.items() if v != src_key]
    all_keys   = [src_key] + hedge_keys
    today, tomorrow = today_tomorrow()
    bonus_ev = bg['bonus_val'] * CONV_BETGET
    opps = []

    with st.status("Running scan...", expanded=False) as status:
        for sport in bg['sports']:
            games, remaining = fetch_odds(sports_map[sport])
            if not games: continue
            st.session_state.api_quota = remaining

            for game in games:
                ct = local_date(game['commence_time'])
                if ct.date() not in [today, tomorrow]: continue
                flat = flat_h2h(game, all_keys)
                if not flat: continue
                teams = list(set(o['team'] for o in flat))
                label = f"{game.get('away_team')} vs {game.get('home_team')}"
                gtime = ct.strftime("%m/%d %I:%M %p")

                if len(teams) == 3:
                    for o1 in [o for o in flat if o['book_key'] == src_key]:
                        for o2 in [o for o in flat if o['book_key'] in hedge_keys and o['team'] != o1['team']]:
                            for o3 in [o for o in flat if o['book_key'] in hedge_keys and o['team'] != o1['team'] and o['team'] != o2['team'] and o['book_key'] != o2['book_key']]:
                                pay = bg['wager'] * (1 + get_multiplier(o1['price']))
                                h1  = pay / (1 + get_multiplier(o2['price']))
                                h2  = pay / (1 + get_multiplier(o3['price']))
                                ql  = pay - bg['wager'] - h1 - h2
                                opps.append({"game": label, "sport": sport, "market_type": "3-way", "time": gtime,
                                    "qualifying_loss": ql, "net_value": bonus_ev + ql,
                                    "s_book": o1['book_title'], "s_team": o1['team'], "s_price": o1['price'], "s_wager": bg['wager'],
                                    "h1_book": o2['book_title'], "h1_team": o2['team'], "h1_price": o2['price'], "h1_wager": h1,
                                    "h2_book": o3['book_title'], "h2_team": o3['team'], "h2_price": o3['price'], "h2_wager": h2})

                elif len(teams) == 2:
                    for s in [o for o in flat if o['book_key'] == src_key]:
                        eligible = [h for h in flat if h['book_key'] in hedge_keys and h['team'] != s['team']]
                        if not eligible: continue
                        best_h = max(eligible, key=lambda x: x['price'])
                        pay = bg['wager'] * (1 + get_multiplier(s['price']))
                        h   = pay / (1 + get_multiplier(best_h['price']))
                        ql  = pay - bg['wager'] - h
                        opps.append({"game": label, "sport": sport, "market_type": "2-way", "time": gtime,
                            "qualifying_loss": ql, "net_value": bonus_ev + ql,
                            "s_book": s['book_title'], "s_team": s['team'], "s_price": s['price'], "s_wager": bg['wager'],
                            "h1_book": best_h['book_title'], "h1_team": best_h['team'], "h1_price": best_h['price'], "h1_wager": h})

        status.update(label="Scan complete.", state="complete")
    return opps


# ================================================================
# RENDER FUNCTIONS
# ================================================================
def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} — {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)
    if not sorted_opps: st.warning("No profitable matches found."); return

    for i, op in enumerate(sorted_opps[:15]):
        profit = op['exact_profit']
        ps = '+' if profit >= 0 else ''
        boost_str = f" | +{op['used_boost']}% Boost" if op.get('used_boost', 0) > 0 else ""
        conv_str  = f" ({profit / op.get('exact_w1', op.get('wager', 1)) * 100:.1f}% conv)" if op['strat'] == "Bonus Bet" else ""
        with st.expander(f"#{i+1} | {op['time']} | {op['game']}{boost_str} | {ps}${profit:.2f}{conv_str}"):
            if op['market_type'] == "3-way":
                c1, c2, c3 = st.columns(3)
                with c1: st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['exact_w1']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c2: st.success(f"**{op['h1_book'].upper()}**\n\nStake: **${op['exact_hedge1']:.2f}**\n\nLine: **{op['h1_team']}** @ **{op['h1_price']:+}**")
                with c3: st.success(f"**{op['h2_book'].upper()}**\n\nStake: **${op['exact_hedge2']:.2f}**\n\nLine: **{op['h2_team']}** @ **{op['h2_price']:+}**")
            else:
                c1, c2 = st.columns([1.5, 2])
                with c1: st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['wager']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                with c2: st.success(f"**{op['h_book'].upper()}**\n\nStake: **${op['exact_hedge']:.2f}**\n\nLine: **{op['h_team']}** @ **{op['h_price']:+}**")
            st.metric("Net Arbitrage Profit", f"${profit:.2f}")


def display_soccer_results(opps):
    st.markdown("<div class='soccer-header'><h3>3-Way Soccer Engine Results</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['net_profit'], reverse=True)
    if not sorted_opps: st.warning("No matches found."); return

    for i, op in enumerate(sorted_opps[:10]):
        profit = op['net_profit']; ps = "+" if profit >= 0 else ""
        with st.expander(f"#{i+1} | {op['time']} | {op['game']} | {ps}${profit:.2f}"):
            cl1, cl2, cl3 = st.columns(3)

            def leg_card(col, label, book, strat, boost, wager, promo, cash, team, price, fn):
                pl = f"{strat} +{boost}%" if boost > 0 else strat
                ph = {
                    "Straight Cash": "Standard cash — no promo.", "Bonus Bet": "Stake not returned on win.",
                    "No-Sweat Bet": "~65% stake refunded as bonus if lost."
                }.get(strat, f"Profit boost of {boost}% applied." if boost > 0 else "")
                body = f"**{book}**\n\n*{pl}*\n\nTotal Bet: **${wager:.2f}**\n\n"
                if strat != "Straight Cash":
                    body += f"\u21b3 Promo: `${promo:.2f}`\n\n"
                    if cash > 0: body += f"\u21b3 Cash: `${cash:.2f}`\n\n"
                body += f"**{team} @ {price:+}**"
                with col: fn(body); st.caption(f"**{label}** — {ph}")

            leg_card(cl1, "BET 1", op['o1_book'], op['o1_strat'], op['o1_boost'], op['o1_wager'], op['o1_promo'], op['o1_cash'], op['o1_team'], op['o1_price'], st.info)
            leg_card(cl2, "BET 2", op['o2_book'], op['o2_strat'], op['o2_boost'], op['o2_wager'], op['o2_promo'], op['o2_cash'], op['o2_team'], op['o2_price'], st.success)
            leg_card(cl3, "BET 3", op['o3_book'], op['o3_strat'], op['o3_boost'], op['o3_wager'], op['o3_promo'], op['o3_cash'], op['o3_team'], op['o3_price'], st.warning)

            bc = "#16a34a" if profit >= 0 else "#dc2626"
            bb = "#f0fdf4" if profit >= 0 else "#fef2f2"
            bbd = "#bbf7d0" if profit >= 0 else "#fecaca"
            st.markdown(f"<div style='margin-top:12px;padding:14px 20px;background:{bb};border:1px solid {bbd};border-left:5px solid {bc};border-radius:8px;display:flex;align-items:center;gap:16px;'>"
                        f"<span style='font-size:0.85rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em;'>Net Profit</span>"
                        f"<span style='font-size:1.5rem;font-family:monospace;font-weight:700;color:{bc};'>{ps}${profit:.2f}</span></div>", unsafe_allow_html=True)


def display_bet_get_results(opps, bg):
    st.markdown(f"<div class='betget-header'><h3>Bet and Get Engine — {bg['book']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(opps, key=lambda x: x['net_value'], reverse=True)
    if not sorted_opps: st.warning("No tight lines found."); return

    for i, op in enumerate(sorted_opps[:10]):
        sign = "+" if op['net_value'] >= 0 else ""
        with st.expander(f"#{i+1} | {op['time']} | {op['game']} | {sign}${op['net_value']:.2f}"):
            st.caption(f"**League:** {op['sport']} | Market: {op['market_type'].upper()}")
            if op['market_type'] == "3-way":
                c1, c2, c3 = st.columns(3)
                with c1: st.info(f"**QUALIFIER**\n\n**{op['s_book']}**\n\n${op['s_wager']:.2f} | {op['s_team']} @ {op['s_price']:+}")
                with c2: st.success(f"**HEDGE 1**\n\n**{op['h1_book']}**\n\n${op['h1_wager']:.2f} | {op['h1_team']} @ {op['h1_price']:+}")
                with c3: st.success(f"**HEDGE 2**\n\n**{op['h2_book']}**\n\n${op['h2_wager']:.2f} | {op['h2_team']} @ {op['h2_price']:+}")
            else:
                c1, c2 = st.columns(2)
                with c1: st.info(f"**QUALIFIER**\n\n**{op['s_book']}**\n\n${op['s_wager']:.2f} | {op['s_team']} @ {op['s_price']:+}")
                with c2: st.success(f"**HEDGE**\n\n**{op['h1_book']}**\n\n${op['h1_wager']:.2f} | {op['h1_team']} @ {op['h1_price']:+}")
            c1, c2 = st.columns(2)
            with c1: st.metric("Qualifying Cost", f"${op['qualifying_loss']:.2f}")
            with c2: st.metric("Net Value (65% conv)", f"${op['net_value']:.2f}")


# ================================================================
# LAYOUT
# ================================================================
c1, c2 = st.columns([3, 1])
with c1: st.title("Promo Converter")
with c2:
    if 'api_quota' not in st.session_state: st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)
st.divider()

with st.expander("Main Boost Engine", expanded=True):
    with st.form("promo_form", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            with st.container(border=True):
                b = st.selectbox("Source Book", list(book_map.keys()))
                s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            with st.container(border=True):
                w  = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=5.0)
                bv = st.number_input("Boost Value (%)", min_value=0, value=0, step=5, disabled=(s != "Profit Boost (%)"))
        with col3:
            with st.container(border=True):
                hb = st.multiselect("Hedge Book(s)", list(book_map.keys()), placeholder="All Books")
        with col4:
            with st.container(border=True):
                sp = st.multiselect("Sports Filter", list(sports_map.keys()), placeholder="Select sports...")
        if st.form_submit_button("Scan"):
            results = run_promo_scan({"book": b, "strat": s, "boost_val": bv, "wager": w, "hedge_books": hb, "sports": sp or list(sports_map.keys())})
            display_results(results, {"book": b, "strat": s, "boost_val": bv, "wager": w})

with st.expander("3-Way Soccer Engine", expanded=False):
    with st.form("soccer_form"):
        st.divider()
        sc1, sc2, sc3 = st.columns(3)
        def soccer_leg(col, label, key_prefix, is_multi=False):
            with col:
                with st.container(border=True):
                    st.subheader(label)
                    book = col.multiselect("Book(s)", list(book_map.keys()), placeholder="Select...", key=f"{key_prefix}_book") if is_multi else col.selectbox("Book", list(book_map.keys()), key=f"{key_prefix}_book")
                    strat = col.selectbox("Promo Type", ["Straight Cash", "Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key=f"{key_prefix}_strat")
                    boost = col.number_input("Boost %", min_value=0, value=0, step=5, key=f"{key_prefix}_boost")
                    stake = col.number_input("Stake ($)", min_value=0.0, value=0.0, step=5.0, key=f"{key_prefix}_stake")
                    cap   = col.number_input("Promo Cap ($)", min_value=0.0, value=0.0, key=f"{key_prefix}_cap")
                    return book, strat, boost, stake, cap
        sb1, ss1, sbv1, sw1, scap1 = soccer_leg(sc1, "Bet 1", "s1")
        sb2, ss2, sbv2, sw2, scap2 = soccer_leg(sc2, "Bet 2", "s2", is_multi=True)
        sb3, ss3, sbv3, sw3, scap3 = soccer_leg(sc3, "Bet 3", "s3", is_multi=True)
        if st.form_submit_button("Scan"):
            today = datetime.now(CENTRAL).date()
            cfg = {
                "book1": sb1, "strat1": ss1, "boost1": sbv1, "wager1": sw1, "cap1_val": scap1,
                "book2": sb2 or list(book_map.keys()), "strat2": ss2, "boost2": sbv2, "wager2": sw2, "cap2_val": scap2,
                "book3": sb3 or list(book_map.keys()), "strat3": ss3, "boost3": sbv3, "wager3": sw3, "cap3_val": scap3,
                "leagues": ["FIFA World Cup"], "lookahead_end_date": today + timedelta(days=2)
            }
            display_soccer_results(run_multi_book_soccer_scan(cfg))

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
                bg_sp = st.multiselect("Sports", list(sports_map.keys()))
        if st.form_submit_button("Scan"):
            display_bet_get_results(run_bet_get_scan({"book": bg_b, "wager": bg_w, "bonus_val": bg_v, "sports": bg_sp}), {"book": bg_b})
