import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- STRICT WHITE & BLACK THEME ---
st.markdown("""
    <style>
    /* Global Background and Text */
    .stApp { 
        background-color: #ffffff !important; 
        color: #000000 !important; 
    }
    
    /* Force all text elements to black */
    h1, h2, h3, p, span, label, .stMarkdown, .stMetricValue, div {
        color: #000000 !important;
    }

    /* Remove color from expanders and containers */
    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #000000 !important;
        border-radius: 0px !important;
    }

    /* Remove color from Info/Success/Warning boxes */
    div[data-testid="stNotification"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }

    /* Metric Styling */
    [data-testid="stMetricValue"] { 
        font-family: monospace !important; 
    }

    /* Button Styling */
    .stButton>button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        border-radius: 0px !important;
        font-weight: bold;
    }
    
    .stButton>button:hover {
        background-color: #000000 !important;
        color: #ffffff !important;
    }

    /* Form and Input Borders */
    input, select, .stSelectbox {
        border: 1px solid #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# --- SHARED DATA ---
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

# --- GAMEPLAN ARCHITECT ---
st.subheader("Gameplan architect")
with st.expander("Step 1: Input your available promos", expanded=True):
    if 'promos' not in st.session_state: 
        st.session_state.promos = []

    with st.form("gp_form"):
        ga, gb, gc = st.columns([2,2,1])
        with ga:
            gp_b = st.selectbox("Book", list(book_map.keys()), key="gpb")
            gp_s = st.selectbox("Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="gps")
        with gb:
            gp_w = st.number_input("Wager amount ($)", min_value=1.0, value=25.0, key="gpw")
            gp_v = st.number_input("Boost % (if applicable)", min_value=0, value=50, key="gpv")
        with gc:
            gp_sp = st.multiselect("Sports to search", sport_labels, default=["NCAAB"], key="gpsp")
        
        if st.form_submit_button("Add promo to list"):
            st.session_state.promos.append({"book": gp_b, "strat": gp_s, "wager": gp_w, "val": gp_v, "sports": gp_sp})

    if st.session_state.promos:
        st.write("### Your promo list")
        user_books = list(set([book_map[p['book']] for p in st.session_state.promos]))
        
        for i, p in enumerate(st.session_state.promos):
            # Title logic to show % for Profit Boosts
            promo_title = f"{p['val']}% Profit Boost" if p['strat'] == "Profit Boost (%)" else p['strat']
            st.markdown(f"**{i+1}. {p['book']} {promo_title}** (${p['wager']}) | Searching: {', '.join(p['sports'])}")
        
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
                    p_header = f"{p['val']}% Profit Boost" if p['strat'] == "Profit Boost (%)" else p['strat']
                    st.write(f"## Best opportunities for: {p['book']} {p_header}")
                    
                    found_plays = []
                    with st.spinner(f"Scanning upcoming games..."):
                        for sport_label in p['sports']:
                            sport_key = sports_map[sport_label]
                            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
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
                                    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                                    if commence_time <= now_utc:
                                        continue 
                                    
                                    s_odds, h_odds = [], []
                                    for bm in game['bookmakers']:
                                        for m in bm['markets']:
                                            for o in m['outcomes']:
                                                if bm['key'] == book_map[p['book']]:
                                                    s_odds.append(o)
                                                h_odds.append({'price': o['price'], 'team': o['name'], 'book': bm['title']})
                                    
                                    for so in s_odds:
                                        opp_team = next((t for t in [game['home_team'], game['away_team']] if t != so['name']), None)
                                        eligible_h = [ho for ho in h_odds if ho['team'] == opp_team]
                                        
                                        if eligible_h:
                                            best_h = max(eligible_h, key=lambda x: x['price'])
                                            sm, hm = get_multiplier(so['price']), get_multiplier(best_h['price'])
                                            
                                            if p['strat'] == "Profit Boost (%)":
                                                boosted_sm = sm * (1 + (p['val']/100))
                                                hamt = (p['wager'] * (1 + boosted_sm)) / (1 + hm)
                                                profit = (p['wager'] * boosted_sm) - hamt
                                            elif p['strat'] == "Bonus Bet":
                                                hamt = (p['wager'] * sm) / (1 + hm)
                                                profit = (p['wager'] * sm) - hamt
                                            else: # No-Sweat
                                                hamt = (p['wager'] * (sm + 0.30)) / (hm + 1)
                                                profit = (p['wager'] * sm) - hamt

                                            found_plays.append({
                                                "game": f"{game['away_team']} vs {game['home_team']}",
                                                "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                                "profit": profit, "hamt": hamt, "s_team": so['name'],
                                                "s_price": so['price'], "h_team": best_h['team'],
                                                "h_book": best_h['book'], "h_price": best_h['price'],
                                                "sport": sport_label
                                            })

                    top_plays = sorted(found_plays, key=lambda x: x['profit'], reverse=True)[:5]
                    
                    if top_plays:
                        for play in top_plays:
                            with st.container():
                                st.markdown(f"**{play['game']}** ({play['sport']} - {play['time']})")
                                c1, c2, c3 = st.columns(3)
                                c1.text(f"Bet ${p['wager']} on {play['s_team']} @ {play['s_price']:+}")
                                c2.text(f"Hedge ${play['hamt']:.2f} on {play['h_book']} @ {play['h_price']:+}")
                                c3.metric("Profit", f"${play['profit']:.2f}", delta_color="off")
                                st.markdown("---")
                    else:
                        st.text("No matches found.")

# --- QUICK CALCULATOR ---
st.write("---")
st.subheader("Manual calculator")
with st.expander("Calculate any two lines"):
    m_col1, m_col2 = st.columns(2)
    m_odds = m_col1.number_input("Promo odds", value=150)
    m_hedge = m_col2.number_input("Hedge odds", value=-140)
    m_w = st.number_input("Promo wager ($)", value=50.0)
    if st.button("Calculate"):
        sm, hm = get_multiplier(m_odds), get_multiplier(m_hedge)
        h_amt = (m_w * (1 + sm)) / (1 + hm)
        st.text(f"Hedge bet needed: ${h_amt:.2f}")
        st.text(f"Profit: ${(m_w * sm) - h_amt:.2f}")
