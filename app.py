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

                    # 3-Way Conversion (Main Engine uses flat unboosted arrays unless passed custom parameters)
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

    with st.status("Parsing complex 3-Way line structures...", expanded=False) as status:
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

                            m1_raw = get_multiplier(o1['price'])
                            m2_raw = get_multiplier(o2['price'])
                            m3_raw = get_multiplier(o3['price'])

                            b1_boosts = [sc['boost1']] if b1_match else [0]
                            b2_boosts = [sc['boost2']] if b2_match else [0]

                            for b1 in b1_boosts:
                                for b2 in b2_boosts:
                                    m1 = m1_raw * (1 + (b1 / 100))
                                    m2 = m2_raw * (1 + (b2 / 100))
                                    m3 = m3_raw 

                                    target_pay = sc['wager1'] * (1 + m1)
                                    h2_stake = target_pay / (1 + m2)
                                    h3_stake = target_pay / (1 + m3)

                                    total_outlay = sc['wager1'] + h2_stake + h3_stake
                                    net_profit = target_pay - total_outlay

                                    soccer_opps.append({
                                        "game": f"{game.get('away_team')} vs {game.get('home_team')}",
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "net_profit": net_profit,
                                        "o1_book": o1['book_title'], "o1_team": o1['team'], "o1_price": o1['price'], "o1_wager": sc['wager1'], "o1_boost": b1,
                                        "o2_book": o2['book_title'], "o2_team": o2['team'], "o2_price": o2['price'], "o2_wager": h2_stake, "o2_boost": b2,
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
                        opp_team =
