import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- TECH THEME CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
    }
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; font-family: 'Courier New', monospace; font-weight: 800;
    }
    .stButton>button {
        background-color: #1e1e1e; color: #00ff88; border: none; border-radius: 8px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# --- SHARED DATA (STRICT LIST) ---
book_map = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "theScore / ESPN": "espnbet",
    "BetMGM": "betmgm"
}

sports_map = {
    "NBA": "basketball_nba", 
    "NCAAB": "basketball_ncaab", 
    "NHL": "icehockey_nhl", 
    "Boxing": "boxing_boxing", 
    "MMA": "mma_mixed_martial_arts" 
}
sport_labels = list(sports_map.keys())

# --- HEADER ---
st.title("Promo Converter")
quota_placeholder = st.empty()

# --- GAMEPLAN ARCHITECT ---
st.subheader("Gameplan architect")
with st.expander("Step 1: Input your available promos", expanded=True):
    if 'promos' not in st.session_state: st.session_state.promos = []

    with st.form("gp_form"):
        ga, gb, gc = st.columns([2,2,1])
        with ga:
            gp_b = st.selectbox("Book", list(book_map.keys()), key="gpb")
            gp_s = st.selectbox("Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="gps")
        with gb:
            gp_w = st.number_input("Wager amount ($)", min_value=1.0, value=25.0, key="gpw")
            gp_v = st.number_input("Boost % (if applicable)", min_value=0, value=50, key="gpv")
        with gc:
            gp_sp = st.multiselect("Sports to search", sport_labels, default=["NBA"], key="gpsp")
        
        if st.form_submit_button("Add promo to list"):
            st.session_state.promos.append({"book": gp_b, "strat": gp_s, "wager": gp_w, "val": gp_v, "sports": gp_sp})

    if st.session_state.promos:
        st.write("### Your promo list")
        # Identify the active books for this session
        user_books = list(set([book_map[p['book']] for p in st.session_state.promos]))
        
        for i, p in enumerate(st.session_state.promos):
            st.info(f"**{i+1}. {p['book']}** {p['strat']} (${p['wager']}) | Searching: {', '.join(p['sports'])}")
        
        if st.button("Clear list"): 
            st.session_state.promos = []
            st.rerun()

        st.divider()
        api_key = st.secrets.get("ODDS_API_KEY", "")
        
        if st.button("Generate live gameplan", use_container_width=True):
            if not api_key:
                st.error("Missing API Key in secrets.")
            else:
                now_utc = datetime.now(timezone.utc)
                
                for p in st.session_state.promos:
                    st.write(f"## Best opportunities for: {p['book']} {p['strat']}")
                    
                    found_plays = []
                    with st.spinner(f"Scanning upcoming {p['sports']} for matches on DK, FD, theScore, MGM..."):
                        for sport_label in p['sports']:
                            sport_key = sports_map[sport_label]
                            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                            
                            # Filter API request to ONLY the selected books
                            book_csv = ",".join(user_books)
                            params = {
                                'apiKey': api_key, 
                                'regions': 'us,us2', 
                                'markets': 'h2h', 
                                'bookmakers': book_csv, 
                                'oddsFormat': 'american'
                            }
                            res = requests.get(url, params=params)
                            
                            if res.status_code == 200:
                                games = res.json()
                                for game in games:
                                    # Filter out live games
                                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                                    if commence_time <= now_utc:
                                        continue 
                                    
                                    s_odds, h_odds = [], []
                                    for bm in game['bookmakers']:
                                        for m in bm['markets']:
                                            for o in m['outcomes']:
                                                # Source side (the book for this specific promo)
                                                if bm['key'] == book_map[p['book']]:
                                                    s_odds.append(o)
                                                # Hedge side (MUST be one of the four books provided)
                                                h_odds.append({'price': o['price'], 'team': o['name'], 'book': bm['title']})
                                    
                                    for so in s_odds:
                                        opp_team = next((t for t in [game['home_team'], game['away_team']] if t != so['name']), None)
                                        eligible_h = [ho for ho in h_odds if ho['team'] == opp_team]
                                        
                                        if eligible_h:
                                            # Find best hedge price among the four user-defined books
                                            best_h = max(eligible_h, key=lambda x: x['price'])
                                            
                                            sm, hm = get_multiplier(so['price']), get_multiplier(best_h['price'])
                                            
                                            if p['strat'] == "Profit Boost (%)":
                                                boosted_sm = sm * (1 + (p['val']/100))
                                                hamt = (p['wager'] * (1 + boosted_sm)) / (1 + hm)
                                                profit = (p['wager'] * boosted_sm) - hamt
                                            elif p['strat'] == "Bonus Bet":
                                                hamt = (p['wager'] * sm) / (1 + hm)
                                                profit = (p['wager'] * sm) - hamt
                                            else: # No-Sweat (Refund evaluated at 70% conversion)
                                                hamt = (p['wager'] * (sm + 0.30)) / (hm + 1)
                                                profit = (p['wager'] * sm) - hamt

                                            found_plays.append({
                                                "game": f"{game['away_team']} vs {game['home_team']}",
                                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M%p"),
                                                "profit": profit, "hamt": hamt, "s_team": so['name'],
                                                "s_price": so['price'], "h_team": best_h['team'],
                                                "h_book": best_h['book'], "h_price": best_h['price'],
                                                "sport": sport_label
                                            })

                    # Rank by raw profit
                    top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
                    
                    if top_plays:
                        for play in top_plays:
                            with st.container():
                                st.markdown(f"**{play['game']}** ({play['sport']} - {play['time']})")
                                c1, c2, c3 = st.columns(3)
                                c1.info(f"Bet ${p['wager']} on {play['s_team']} @ {play['s_price']:+}")
                                c2.success(f"Hedge ${play['hamt']:.2f} on {play['h_book']} @ {play['h_price']:+}")
                                c3.metric("Estimated profit", f"${play['profit']:.2f}")
                    else:
                        st.info("No matchups found using DK, FD, theScore, or MGM for this promo.")
