import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Soccer Multi-Boost Converter", layout="wide")

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

# --- UTILS & DATA MAPS ---
API_KEY = st.secrets.get("ODDS_API_KEY", "")

def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

BOOK_MAP = {
    "DraftKings": "draftkings", 
    "FanDuel": "fanduel",
    "ESPN Bet": "espnbet", 
    "BetMGM": "betmgm"
}

SPORTS_MAP = {
    "FIFA World Cup": "soccer_fifa_world_cup",
    "MLS": "soccer_usa_mls",
    "UEFA Champions League": "soccer_uefa_champions_league"
}

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
    return None, "Error"

# --- HELPER: PARSE STRING TO LIST OF INTS ---
def parse_boosters(input_str):
    if not input_str.strip():
        return [0]
    try:
        vals = [int(x.strip()) for x in input_str.split(",") if x.strip().isdigit()]
        return vals if vals else [0]
    except:
        return [0]

# --- 3-WAY MULTI-BOOST SCAN ENGINE ---
def run_soccer_scan(config):
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(days=5)
    all_opps = []

    with st.status("Scanning active soccer markets...", expanded=False) as status:
        for sport_label, sport_key in SPORTS_MAP.items():
            games, remaining = fetch_odds(sport_key)
            if not games:
                continue
            st.session_state.api_quota = remaining

            for game in games:
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if commence_time <= now_utc or commence_time > lookahead_limit:
                    continue

                # Gather all available books and odds outcomes for this game
                flat_odds = []
                for bm in game['bookmakers']:
                    if bm['key'] in BOOK_MAP.values():
                        outcomes = bm['markets'][0]['outcomes']
                        for o in outcomes:
                            flat_odds.append({
                                'book_key': bm['key'],
                                'book_title': bm['title'],
                                'team': o['name'],
                                'price': o['price']
                            })

                # Extract the 3 unique soccer outcomes (Team 1, Team 2, Draw)
                unique_teams = list(set([o['team'] for o in flat_odds]))
                if len(unique_teams) != 3:
                    continue

                t1, t2, draw = unique_teams[0], unique_teams[1], unique_teams[2]

                # Filter entries by outcome bucket
                odds_t1 = [o for o in flat_odds if o['team'] == t1]
                odds_t2 = [o for o in flat_odds if o['team'] == t2]
                odds_draw = [o for o in flat_odds if o['team'] == draw]

                # Match valid 3-way combinations across different sportsbooks
                for o1 in odds_t1:
                    for o2 in odds_t2:
                        for o3 in odds_draw:
                            # Prevent placing more than 1 outcome on the exact same bookmaker platform
                            if o1['book_key'] == o2['book_key'] or o1['book_key'] == o3['book_key'] or o2['book_key'] == o3['book_key']:
                                continue

                            # Pull lists of boosters mapped to these bookmakers
                            b1_list = config['boosters'].get(o1['book_key'], [0])
                            b2_list = config['boosters'].get(o2['book_key'], [0])
                            b3_list = config['boosters'].get(o3['book_key'], [0])

                            best_combination_profit = -999999
                            best_boost_scenario = {}

                            # Cycle through every permutation of available boosters for this 3-way line split
                            for b1 in b1_list:
                                for b2 in b2_list:
                                    for b3 in b3_list:
                                        
                                        # Calculate boosted multipliers
                                        m1 = get_multiplier(o1['price']) * (1 + (b1 / 100))
                                        m2 = get_multiplier(o2['price']) * (1 + (b2 / 100))
                                        m3 = get_multiplier(o3['price']) * (1 + (b3 / 100))

                                        # Arbitrage weights mapping based on a fixed base unit wager ($100 standard)
                                        base_wager = config['base_wager']
                                        
                                        # Assume Outcome 1 is our main target stake
                                        target_payout = base_wager * (1 + m1)
                                        
                                        # Determine required clean hedge weights on outcomes 2 and 3
                                        h2_stake = target_payout / (1 + m2)
                                        h3_stake = target_payout / (1 + m3)
                                        
                                        total_outlay = base_wager + h2_stake + h3_stake
                                        net_profit = target_payout - total_outlay

                                        if net_profit > best_combination_profit:
                                            best_combination_profit = net_profit
                                            best_boost_scenario = {
                                                'profit': net_profit,
                                                'w1': base_wager, 'w2': h2_stake, 'w3': h3_stake,
                                                'b1': b1, 'b2': b2, 'b3': b3
                                            }

                            if best_combination_profit > -5.0:  # Show high-efficiency conversions/near-arbs
                                all_opps.append({
                                    "game": f"{game.get('away_team', 'Away Team')} vs {game.get('home_team', 'Home Team')}",
                                    "sport": sport_label,
                                    "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                    "profit": best_boost_scenario['profit'],
                                    "o1": o1, "w1": best_boost_scenario['w1'], "b1": best_boost_scenario['b1'],
                                    "o2": o2, "w2": best_boost_scenario['w2'], "b2": best_boost_scenario['b2'],
                                    "o3": o3, "w3": best_boost_scenario['w3'], "b3": best_boost_scenario['b3']
                                })

        status.update(label="Global Soccer Scan Complete", state="complete")
    return all_opps

# --- INTERFACE HEADER ---
c_title, c_quota = st.columns([3, 1])
with c_title:
    st.title("Soccer Multi-Book Booster Optimizer")
    st.caption("Input your inventory of active profit boosts per sportsbook. The engine maps 3-way soccer configurations automatically.")
with c_quota:
    if 'api_quota' not in st.session_state: st.session_state.api_quota = "—"
    st.metric("API Quota Remaining", st.session_state.api_quota)

st.divider()

# --- CONFIGURATION MATRIX ---
st.subheader("Your Active Sportsbook Boost Inventory")
config_matrix = {}

col_dk, col_fd, col_espn, col_mgm = st.columns(4)

with col_dk:
    st.markdown("**DraftKings**")
    dk_in = st.text_input("Boost values (%)", value="0, 25", key="in_dk", help="Comma-separated list (e.g. 10, 25, 50)")
    config_matrix['draftkings'] = parse_boosters(dk_in)

with col_fd:
    st.markdown("**FanDuel**")
    fd_in = st.text_input("Boost values (%)", value="0, 50", key="in_fd", help="Comma-separated list")
    config_matrix['fanduel'] = parse_boosters(fd_in)

with col_espn:
    st.markdown("**ESPN Bet**")
    espn_in = st.text_input("Boost values (%)", value="0", key="in_espn")
    config_matrix['espnbet'] = parse_boosters(espn_in)

with col_mgm:
    st.markdown("**BetMGM**")
    mgm_in = st.text_input("Boost values (%)", value="0", key="in_mgm")
    config_matrix['betmgm'] = parse_boosters(mgm_in)

st.write("")
base_wager = st.number_input("Base Unit Wager Target ($)", min_value=10.0, value=100.0, step=10.0)

# --- RUN EXECUTION ---
if st.button("Calculate Optimal Multi-Boost Arbs", use_container_width=True):
    search_payload = {
        "boosters": config_matrix,
        "base_wager": base_wager
    }
    
    results = run_soccer_scan(search_payload)
    
    st.markdown("<div class='promo-header'><h3>Optimized 3-Way Match Splits Found</h3></div>", unsafe_allow_html=True)
    
    if not results:
        st.warning("No highly optimal multi-boost combinations found for the current matches. Check back as odds update.")
    else:
        sorted_results = sorted(results, key=lambda x: x['profit'], reverse=True)
        for i, match in enumerate(sorted_results[:10]):
            
            # Form dynamic badge labels showcasing which sportsbooks used which boosters
            b1_str = f" ({match['b1']}% boost)" if match['b1'] > 0 else ""
            b2_str = f" ({match['b2']}% boost)" if match['b2'] > 0 else ""
            b3_str = f" ({match['b3']}% boost)" if match['b3'] > 0 else ""
            
            header_text = f"RANK {i+1} | {match['game']} | Expected Profit: ${match['profit']:.2f}"
            
            with st.expander(header_text):
                st.caption(f"**Market Tier:** {match['sport']} | Match Commencement: {match['time']}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.info(f"**Outcome 1:** {match['o1']['team']}\n\n"
                            f"**Book:** {match['o1']['book_title']}{b1_str}\n\n"
                            f"**Odds:** {match['o1']['price']:+}\n\n"
                            f"**Optimal Stake:** ${match['w1']:.2f}")
                with c2:
                    st.success(f"**Outcome 2:** {match['o2']['team']}\n\n"
                            f"**Book:** {match['o2']['book_title']}{b2_str}\n\n"
                            f"**Odds:** {match['o2']['price']:+}\n\n"
                            f"**Optimal Stake:** ${match['w2']:.2f}")
                with c3:
                    st.success(f"**Outcome 3:** {match['o3']['team']}\n\n"
                            f"**Book:** {match['o3']['book_title']}{b3_str}\n\n"
                            f"**Odds:** {match['o3']['price']:+}\n\n"
                            f"**Optimal Stake:** ${match['w3']:.2f}")
                
                st.metric(label="Net Guaranteed Return", value=f"${match['profit']:.2f}")
