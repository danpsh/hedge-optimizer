import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Promo Converter Master", layout="wide")

# --- PROFESSIONAL THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;600;700&family=Roboto+Mono+&display=swap');
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
        status.update(label=f"Scan Complete", state="complete")
    return all_opps


# --- ENGINE: SOCCER 3-WAY MATRIX WITH COMPLETE SPLIT CASH OVERRIDES ON ALL 3 LEGS ---
def run_multi_book_soccer_scan(sc):
    book1_key = book_map[sc['book1']]
    book2_key = book_map[sc['book2']]
    book3_key = book_map[sc['book3']]
    allowed_keys = list(book_map.values())
    
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    soccer_opps = []

    with st.status("Parsing complex tri-booster 3-Way line structures...", expanded=False) as status:
        sport_key = sports_map["FIFA World Cup"]
        games, remaining = fetch_odds(sport_key)
        if games:
            st.session_state.api_quota = remaining
            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit: continue

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
                            # --- RESTORED MAPPING BINDING ---
                            if o1['book_key'] != book1_key or o2['book_key'] != book2_key or o3['book_key'] != book3_key: continue

                            # --- LEG 1 PROMO PROCESSING ---
                            w1_total = sc['wager1']
                            w1_promo = w1_total
                            w1_cash = 0.0
                            if sc['strat1'] != "Straight Cash" and sc['cap1_val'] > 0 and w1_total > sc['cap1_val']:
                                w1_promo = sc['cap1_val']
                                w1_cash = w1_total - w1_promo

                            m1_raw = get_multiplier(o1['price'])
                            m1_boosted = m1_raw * (1 + (sc['boost1'] / 100)) if sc['strat1'] == "Profit Boost (%)" else m1_raw

                            if sc['strat1'] == "Bonus Bet":
                                target_pay = (w1_promo * m1_boosted) + (w1_cash * (1 + m1_raw))
                                outlay1 = w1_cash
                            else: 
                                target_pay = (w1_promo * (1 + m1_boosted)) + (w1_cash * (1 + m1_raw))
                                outlay1 = w1_total

                            # --- LEG 2 PROMO PROCESSING (WITH ARB SPLITTING) ---
                            m2_raw = get_multiplier(o2['price'])
                            m2_boosted = m2_raw * (1 + (sc['boost2'] / 100)) if sc['strat2'] == "Profit Boost (%)" else m2_raw

                            div_promo2 = m2_boosted if sc['strat2'] == "Bonus Bet" else (1 + m2_boosted)
                            div_cash2 = 1 + m2_raw

                            if sc['strat2'] != "Straight Cash" and sc['cap2_val'] > 0:
                                max_promo_payout2 = sc['cap2_val'] * div_promo2
                                if target_pay > max_promo_payout2:
                                    w2_promo = sc['cap2_val']
                                    w2_cash = (target_pay - max_promo_payout2) / div_cash2
                                else:
                                    w2_promo = target_pay / div_promo2
                                    w2_cash = 0.0
                            else:
                                if sc['strat2'] == "Straight Cash":
                                    w2_promo = 0.0
                                    w2_cash = target_pay / div_cash2
                                else:
                                    w2_promo = target_pay / div_promo2
                                    w2_cash = 0.0

                            w2_total = w2_promo + w2_cash
                            outlay2 = w2_cash if sc['strat2'] == "Bonus Bet" else w2_total

                            # --- LEG 3 PROMO PROCESSING (WITH ARB SPLITTING) ---
                            m3_raw = get_multiplier(o3['price'])
                            m3_boosted = m3_raw * (1 + (sc['boost3'] / 100)) if sc['strat3'] == "Profit Boost (%)" else m3_raw

                            div_promo3 = m3_boosted if sc['strat3'] == "Bonus Bet" else (1 + m3_boosted)
                            div_cash3 = 1 + m3_raw

                            if sc['strat3'] != "Straight Cash" and sc['cap3_val'] > 0:
                                max_promo_payout3 = sc['cap3_val'] * div_promo3
                                if target_pay > max_promo_payout3:
                                    w3_promo = sc['cap3_val']
                                    w3_cash = (target_pay - max_promo_payout3) / div_cash3
                                else:
                                    w3_promo = target_pay / div_promo3
                                    w3_cash = 0.0
                            else:
                                if sc['strat3'] == "Straight Cash":
                                    w3_promo = 0.0
                                    w3_cash = target_pay / div_cash3
                                else:
                                    w3_promo = target_pay / div_promo3
                                    w3_cash = 0.0

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
            if not games: continue
            st.session_state.api_quota = remaining

            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit: continue

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

        status.update(label="Bet & Get Optimization Complete", state="complete")
    return bg_opps

# --- RENDER FUNCTIONS ---
def display_results(all_opps, p):
    st.markdown(f"<div class='promo-header'><h3>Results for {p['book']} - {p['strat']}</h3></div>", unsafe_allow_html=True)
    sorted_opps = sorted(all_opps, key=lambda x: x['exact_profit'], reverse=True)
    
    if not sorted_opps:
        st.warning(f"No profitable matches found.")
    else:
        for i, op in enumerate(sorted_opps[:15]):
            conv_str = f" | Using {op['used_boost']}% Boost" if op.get('market_type') == "2-way" and op.get('used_boost', 0) > 0 else ""
            header_title = f"RANK {i+1} | {op['time']} | {op['game']}{conv_str} | Profit: ${op['exact_profit']:.2f}"
            
            with st.expander(header_title):
                if op.get('market_type') == "3-way":
                    c1, c2, c3 = st.columns(3)
                    with c1: st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['exact_w1']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                    with c2: st.success(f"**{op['h1_book'].upper()}**\n\nStake: **${op['exact_hedge1']:.2f}**\n\nLine: **{op['h1_team']}** @ **{op['h1_price']:+}**")
                    with c3: st.success(f"**{op['h2_book'].upper()}**\n\nStake: **${op['exact_hedge2']:.2f}**\n\nLine: **{op['h2_team']}** @ **{op['h2_price']:+}**")
                else:
                    c_main, c_hedge = st.columns([1.5, 2])
                    with c_main: st.info(f"**{op['s_book'].upper()}**\n\nStake: **${op['wager']:.2f}**\n\nLine: **{op['s_team']}** @ **{op['s_price']:+}**")
                    with c_hedge: st.success(f"**{op['h_book'].upper()}**\n\nStake: **${op['exact_hedge']:.2f}**\n\nLine: **{op['h_team']}** @ **{op['h_price']:+}**")
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
                
                # Leg 1 Panel
                with cl1:
                    b1_str = f" ({op['o1_strat']} +{op['o1_boost']}% 🎉)" if op['o1_boost'] > 0 else f" ({op['o1_strat']})"
                    st.info(f"**OUTCOME 1**\n\n**{op['o1_book']}**\n*{b1_str}*\n\nTotal Bet: **${op['o1_wager']:.2f}**\n\n↳ Booster Stake: `${op['o1_promo']:.2f}`\n\n↳ Cash Override: `${op['o1_cash']:.2f}`\n\n{op['o1_team']} @ {op['o1_price']:+}")
                
                # Leg 2 Panel
                with cl2:
                    b2_str = f" ({op['o2_strat']} +{op['o2_boost']}% 🎉)" if op['o2_boost'] > 0 else f" ({op['o2_strat']})"
                    st.success(f"**OUTCOME 2**\n\n**{op['o2_book']}**\n*{b2_str}*\n\nTotal Bet: **${op['o2_wager']:.2f}**\n\n↳ Booster Stake: `${op['o2_promo']:.2f}`\n\n↳ Cash Override: `${op['o2_cash']:.2f}`\n\n{op['o2_team']} @ {op['o2_price']:+}")
                
                # Leg 3 Panel
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
            b = st.selectbox("Source Book", list(book_map.keys()))
            s = st.selectbox("Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        with col2:
            w = st.number_input("Wager Amount ($)", min_value=0.0, value=0.0, step=5.0)
            main_boost_val = st.number_input("Boost Value (%)", min_value=0, value=0, step=5, help="Only applies if Promo Type is set to Profit Boost (%)", disabled=(s != "Profit Boost (%)"))
        with col3:
            hb = st.multiselect("Hedge Book(s)", [k for k in book_map.keys() if k != b], placeholder="All Books")
        with col4:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=[], placeholder="Select sports...")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            run_scan = st.form_submit_with_clicks(label="Execute Universal Scan Engine")

    if run_scan:
        params = {'book': b, 'strat': s, 'wager': w, 'boost_val': main_boost_val, 'hedge_books': hb, 'sports': sp}
        if not sp:
            st.error("Please pick at least one tier-1 sport in the filter pool before firing.")
        else:
            results = run_promo_scan(params)
            display_results(results, params)

# ========================================================
# ADVANCED LAYER: COMPLEX SOCCER MATRIX ENGINE
# ========================================================
with st.expander("Complex Soccer Engine (Multi-Book Tri-Booster Router)", expanded=False):
    st.caption("Calculate 3-way arbitrage models across up to three independent promos simultaneously with dynamic overflow cash splitting.")
    
    with st.form("soccer_form"):
        sc1, sc2, sc3 = st.columns(3)
        
        with sc1:
            st.markdown("##### Leg 1 (Outcome A)")
            s_b1 = st.selectbox("Book 1", list(book_map.keys()), key="sb1")
            s_st1 = st.selectbox("Promo 1", ["Straight Cash", "Profit Boost (%)", "Bonus Bet"], key="sst1")
            s_w1 = st.number_input("Target Primary Wager ($)", min_value=0.0, value=10.0, step=5.0, key="sw1")
            s_bst1 = st.number_input("Boost % (Leg 1)", min_value=0, value=0, step=5, key="sbst1")
            s_cap1 = st.number_input("Promo Max Cap ($)", min_value=0.0, value=0.0, help="0 means uncapped/no cash split needed", key="scap1")
            
        with sc2:
            st.markdown("##### Leg 2 (Outcome B)")
            s_b2 = st.selectbox("Book 2", list(book_map.keys()), key="sb2")
            s_st2 = st.selectbox("Promo 2", ["Straight Cash", "Profit Boost (%)", "Bonus Bet"], key="sst2")
            st.write(" *Stake determined dynamically based on Leg 1 payoff structural layout*")
            s_bst2 = st.number_input("Boost % (Leg 2)", min_value=0, value=0, step=5, key="sbst2")
            s_cap2 = st.number_input("Promo Max Cap ($)", min_value=0.0, value=0.0, help="0 means uncapped", key="scap2")
            
        with sc3:
            st.markdown("##### Leg 3 (Draw)")
            s_b3 = st.selectbox("Book 3", list(book_map.keys()), key="sb3")
            s_st3 = st.selectbox("Promo 3", ["Straight Cash", "Profit Boost (%)", "Bonus Bet"], key="sst3")
            st.write(" *Stake determined dynamically based on Leg 1 payoff structural layout*")
            s_bst3 = st.number_input("Boost % (Leg 3)", min_value=0, value=0, step=5, key="sbst3")
            s_cap3 = st.number_input("Promo Max Cap ($)", min_value=0.0, value=0.0, help="0 means uncapped", key="scap3")

        soccer_scan = st.form_submit_with_clicks(label="Execute Triple-Leg Optimized Run")

    if soccer_scan:
        soccer_params = {
            'book1': s_b1, 'strat1': s_st1, 'wager1': s_w1, 'boost1': s_bst1, 'cap1_val': s_cap1,
            'book2': s_b2, 'strat2': s_st2, 'boost2': s_bst2, 'cap2_val': s_cap2,
            'book3': s_b3, 'strat3': s_st3, 'boost3': s_bst3, 'cap3_val': s_cap3
        }
        soc_results = run_multi_book_soccer_scan(soccer_params)
        display_soccer_results(soc_results)

# ========================================================
# OPTIMIZATION LAYER: DEDICATED BET & GET TRACKER
# ========================================================
with st.expander("Bet & Get Tracker", expanded=False):
    st.caption("Calculate the exact qualifying equity cost for 'Bet $X, Get $Y' vouchers to lock down optimal returns.")
    
    with st.form("bet_get_form"):
        bg_col1, bg_col2, bg_col3 = st.columns(3)
        with bg_col1:
            bg_b = st.selectbox("Target Book (Qualifier placement)", list(book_map.keys()), key="bg_b")
            bg_w = st.number_input("Required Qualification Stake ($)", min_value=5.0, value=25.0, step=5.0, key="bg_w")
        with bg_col2:
            bg_bonus = st.number_input("Expected Bonus Voucher Received ($)", min_value=0.0, value=10.0, step=5.0, key="bg_bonus")
        with bg_col3:
            bg_sp = st.multiselect("Eligible Sport Leagues", list(sports_map.keys()), default=list(sports_map.keys())[:2], key="bg_sp")
            
        bg_scan = st.form_submit_with_clicks(label="Map Minimal Qualifying Loss Paths")

    if bg_scan:
        bg_params = {'book': bg_b, 'wager': bg_w, 'bonus_val': bg_bonus, 'sports': bg_sp}
        bg_results = run_bet_get_scan(bg_params)
        display_bet_get_results(bg_results, bg_params)
