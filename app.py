import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

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
                                        m1 = get_multiplier(o1['price'])
                                        m2 = get_multiplier(o2['price'])
                                        m3 = get_multiplier(o3['price'])
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
                                            "used_boost": 0
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
                                        "wager": p['wager'], "strat": p['strat'], "used_boost": 0
                                    })
            else:
                st.error(f"Could not fetch data for {sport_label}")
        status.update(label=f"Scan Complete", state="complete")
    return all_opps


# --- ENGINE: DUAL SOURCE BOOK 3-WAY SOCCER SCANNER ---
def run_multi_book_soccer_scan(sc):
    book1_key = book_map[sc['book1']]
    book2_key = book_map[sc['book2']] if sc['use_two_books'] else None
    allowed_keys = list(book_map.values())
    
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    soccer_opps = []

    with st.status("Parsing complex multi-booster 3-Way line structures...", expanded=False) as status:
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
                            if o1['book_key'] == o2['book_key'] == o3['book_key']: continue
                            
                            b1_match = (o1['book_key'] == book1_key)
                            b2_match = (o2['book_key'] == book2_key) if book2_key else False
                            
                            if not b1_match and not b2_match: continue

                            # --- HELPER FUNCTION TO GET RESOLVED TARGET RETURN FROM OUTCOME 1 ---
                            m1_raw = get_multiplier(o1['price'])
                            if b1_match:
                                if sc['strat1'] == "Profit Boost (%)":
                                    m1 = m1_raw * (1 + (sc['boost1'] / 100))
                                    target_pay = sc['wager1'] * (1 + m1)
                                    outlay1 = sc['wager1']
                                elif sc['strat1'] == "Bonus Bet":
                                    target_pay = sc['wager1'] * m1_raw
                                    outlay1 = 0
                                else: # No Sweat
                                    target_pay = sc['wager1'] * (1 + m1_raw)
                                    outlay1 = sc['wager1']
                            else:
                                target_pay = sc['wager1'] * (1 + m1_raw)
                                outlay1 = sc['wager1']

                            # --- SOLVE STAKES FOR OUTCOME 2 AND OUTCOME 3 ---
                            m2_raw = get_multiplier(o2['price'])
                            m3_raw = get_multiplier(o3['price'])

                            # Resolve Outcome 2 Stake
                            if b2_match:
                                if sc['strat2'] == "Profit Boost (%)":
                                    m2 = m2_raw * (1 + (sc['boost2'] / 100))
                                    h2_stake = target_pay / (1 + m2)
                                    outlay2 = h2_stake
                                elif sc['strat2'] == "Bonus Bet":
                                    h2_stake = target_pay / m2_raw
                                    outlay2 = 0
                                else: # No Sweat
                                    mc = 0.65
                                    # Adjust stake considering bonus back on loss
                                    h2_stake = (target_pay) / (1 + m2_raw) 
                                    outlay2 = h2_stake # Simple approximation for multi-variant calculation
                            else:
                                h2_stake = target_pay / (1 + m2_raw)
                                outlay2 = h2_stake

                            # Resolve Outcome 3 (Always pure market hedge)
                            h3_stake = target_pay / (1 + m3_raw)
                            outlay3 = h3_stake

                            net_profit = target_pay - (outlay1 + outlay2 + outlay3)

                            soccer_opps.append({
                                "game": f"{game.get('away_team')} vs {game.get('home_team')}",
                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                "net_profit": net_profit,
                                "o1_book": o1['book_title'], "o1_team": o1['team'], "o1_price": o1['price'], "o1_wager": sc['wager1'], "o1_strat": sc['strat1'], "o1_boost": sc['boost1'] if b1_match and sc['strat1'] == "Profit Boost (%)" else 0,
                                "o2_book": o2['book_title'], "o2_team": o2['team'], "o2_price": o2['price'], "o2_wager": h2_stake, "o2_strat": sc['strat2'] if b2_match else "Straight", "o2_boost": sc['boost2'] if b2_match and sc['strat2'] == "Profit Boost (%)" else 0,
                                "o3_book": o3['book_title'], "o3_team": o3['team'], "o3_price": o3['price'], "o3_wager": h3_stake
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
                
                b1_str = f" ({op['o1_strat']} +{op['o1_boost']}% 🎉)" if op['o1_boost'] > 0 else f" ({op['o1_strat']})"
                with cl1: st.info(f"**OUTCOME A**\n\n**{op['o1_book']}**\n*{b1_str}*\n\nBet: **${op['o1_wager']:.2f}**\n\n{op['o1_team']} @ {op['o1_price']:+}")
                
                b2_str = f" ({op['o2_strat']} +{op['o2_boost']}% 🎉)" if op['o2_boost'] > 0 else f" ({op['o2_strat']})"
                with cl2: st.success(f"**OUTCOME B**\n\n**{op['o2_book']}**\n*{b2_str}*\n\nBet: **${op['o2_wager']:.2f}**\n\n{op['o2_team']} @ {op['o2_price']:+}")
                
                with cl3: st.warning(f"**OUTCOME C (HEDGE)**\n\n**{op['o3_book']}**\n*Market Hedge*\n\nBet: **${op['o3_wager']:.2f}**\n\n{op['o3_team']} @ {op['o3_price']:+}")
                
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
            w = st.number_input("Wager Amount ($)", min_value=0.0, value=100.0, step=10.0)
        with col3:
            hb = st.multiselect("Hedge Book(s)", [k for k in book_map.keys() if k != b], placeholder="All Books")
        with col4:
            sp = st.multiselect("Sports Filter", list(sports_map.keys()), default=["MLB", "WNBA"], placeholder="Select sports...")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: add_to_q = st.form_submit_button("Add to Queue", use_container_width=True)
        with btn_col2: quick_scan = st.form_submit_button("Quick Scan", use_container_width=True)

# --- EXECUTE TOP CONFIG ACTIONS ---
if quick_scan:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        temp_p = {"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb}
        results = run_promo_scan(temp_p)
        display_results(results, temp_p)

if add_to_q:
    if not sp: st.error("Select at least one sport.")
    elif w <= 0: st.error("Enter a wager amount.")
    else:
        st.session_state.promos.append({"book": b, "strat": s, "wager": w, "sports": sp, "hedge_books": hb})

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
# MIDDLE MODULE: MULTI-BOOK SOCCER ENGINE
# ========================================================
st.markdown("### ⚽ Multi-Book Soccer Booster Engine (3-Way Markets)")
with st.expander("Configure Multi-Source Book Soccer Boost Options", expanded=True):
    sc_c1, sc_c2 = st.columns(2)
    
    with sc_c1:
        st.subheader("Book 1 Configuration")
        sb1 = st.selectbox("Primary Source Book (Outcome 1)", list(book_map.keys()), index=0, key="sb1_k")
        sw1 = st.number_input("Primary Book Bet Size ($)", min_value=5.0, value=100.0, step=5.0, key="sw1_k")
        ss1 = st.selectbox("Book 1 Booster Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, key="ss1_k")
        sbo1 = st.number_input("Book 1 Boost Value (%)", min_value=0, value=25, step=5, key="sbo1_k", disabled=(ss1 != "Profit Boost (%)"))

    with sc_c2:
        st.subheader("Book 2 Configuration")
        use_second = st.checkbox("Enable Second Boosted Source Book?", value=True, key="use_2nd")
        sb2 = st.selectbox("Secondary Source Book (Outcome 2)", list(book_map.keys()), index=1, disabled=not use_second, key="sb2_k")
        ss2 = st.selectbox("Book 2 Booster Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], index=0, disabled=not use_second, key="ss2_k")
        sbo2 = st.number_input("Book 2 Boost Value (%)", min_value=0, value=50, step=5, disabled=(not use_second or ss2 != "Profit Boost (%)"), key="sbo2_k")

    if st.button("Execute Soccer Multi-Boost Optimization Scan", use_container_width=True):
        sc_payload = {
            "book1": sb1, "wager1": sw1, "strat1": ss1, "boost1": sbo1,
            "use_two_books": use_second, "book2": sb2, "strat2": ss2, "boost2": sbo2
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
        bg_wager = st.number_input("Required Wager Amount ($)", min_value=10.0, value=100.0, key="bg_w")
    with col_v:
        bg_bonus = st.number_input("Bonus Bet Reward Expected ($)", min_value=5.0, value=20.0, key="bg_bon")
        
    bg_sports = st.multiselect("Leagues to Search", list(sports_map.keys()), default=list(sports_map.keys()), key="bg_s")
    
    if st.button("Find Cheapest Qualification Paths", use_container_width=True):
        bg_payload = {"book": bg_book, "wager": bg_wager, "bonus_val": bg_bonus, "sports": bg_sports}
        bg_results = run_bet_get_scan(bg_payload)
        st.session_state.bg_results_cache = (bg_results, bg_payload)

# Render results panel for Bet & Get right at the bottom zone
if 'bg_results_cache' in st.session_state:
    display_bet_get_results(st.session_state.bg_results_cache[0], st.session_state.bg_results_cache[1])
    if st.button("Clear Bet & Get Display", use_container_width=True):
        del st.session_state.bg_results_cache
        st.rerun()
