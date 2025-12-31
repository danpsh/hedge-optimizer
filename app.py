import streamlit as st
import requests

def am_to_dec(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Auto-Pilot", layout="wide")

# --- 1. PROMO CONFIGURATION (The "Settings") ---
st.sidebar.title(⚙️ Promo Settings")
promo_type = st.sidebar.selectbox("Booster Type", ["Bonus Bet ($)", "Profit Boost (%)", "No-Sweat Bet"])

if promo_type == "Profit Boost (%)":
    boost_pct = st.sidebar.number_input("Boost %", min_value=1, value=50)
    base_stake = st.sidebar.number_input("Bet Amount ($)", value=50.0)
    m_stake = base_stake
else:
    m_stake = st.sidebar.number_input("Promo Amount ($)", value=100.0)
    base_stake = m_stake

round_flag = st.sidebar.toggle("Round Hedge to $1", value=True)

st.title("🎯 Best Promo Hedges")
st.write(f"Scanning **DraftKings, FanDuel, theScore, Caesars, and Fanatics** for the best {promo_type} opportunities.")

# --- 2. THE AUTO-SCANNER ---
api_key = st.secrets.get("ODDS_API_KEY", "")

if not api_key:
    st.error("Please add your ODDS_API_KEY to Streamlit Secrets.")
else:
    sport = st.selectbox("Select Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])
    
    if st.button("🔍 Find Best Live Options"):
        TARGETS = "draftkings,fanduel,caesars,thescore,fanatics"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': api_key, 'regions': 'us', 'bookmakers': TARGETS, 'oddsFormat': 'american'}
        
        res = requests.get(url, params=params)
        if res.status_code == 200:
            games = res.json()
            opps = []

            for game in games:
                prices = []
                for book in game['bookmakers']:
                    outcomes = book['markets'][0]['outcomes']
                    for o in outcomes:
                        prices.append({'book': book['title'], 'team': o['name'], 'price': o['price']})
                
                # Check for two-book splits
                teams = list(set([p['team'] for p in prices]))
                if len(teams) == 2:
                    t1_odds = [p for p in prices if p['team'] == teams[0]]
                    t2_odds = [p for p in prices if p['team'] == teams[1]]
                    
                    for a in t1_odds:
                        for b in t2_odds:
                            if a['book'] != b['book']:
                                dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                if dog['price'] >= 200 and fav['price'] < 0:
                                    # Calculate Profit based on Promo Type selected in Sidebar
                                    dm, df = am_to_dec(dog['price']), am_to_dec(fav['price'])
                                    
                                    if promo_type == "Bonus Bet ($)":
                                        payout = m_stake * (dm - 1)
                                        raw_h = payout / df
                                        net = payout - raw_h
                                    elif promo_type == "Profit Boost (%)":
                                        p_mult = 1 + (boost_pct/100)
                                        payout = (m_stake * (dm - 1) * p_mult) + m_stake
                                        raw_h = payout / df
                                        net = payout - (m_stake + raw_h)
                                    else: # No Sweat
                                        raw_h = (m_stake * dm) / (df + 0.7)
                                        net = (m_stake * dm) - (m_stake + raw_h)
                                    
                                    opps.append({
                                        "game": f"{game['away_team']} @ {game['home_team']}",
                                        "dog_book": dog['book'], "dog_team": dog['team'], "dog_odds": dog['price'],
                                        "fav_book": fav['book'], "fav_team": fav['team'], "fav_odds": fav['price'],
                                        "h_stake": round(raw_h) if round_flag else raw_h,
                                        "profit": net,
                                        "conv": (net/m_stake)*100
                                    })

            # Sort by best profit
            sorted_opps = sorted(opps, key=lambda x: x['profit'], reverse=True)

            if not sorted_opps:
                st.warning("No valid hedges found. Try a different sport.")
            
            for op in sorted_opps[:5]:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"### {op['game']}")
                        st.write(f"🚩 **{promo_type} on:** {op['dog_book']} — {op['dog_team']} ({op['dog_odds']})")
                        st.write(f"🛡️ **Hedge Cash on:** {op['fav_book']} — {op['fav_team']} ({op['fav_odds']})")
                    with col2:
                        st.metric("Hedge Amount", f"${op['h_stake']:.0f}")
                        st.metric("Net Profit", f"${op['profit']:.2f}")
                        st.write(f"**{op['conv']:.1f}% Conversion**")
        else:
            st.error("API Error. Check your key or limits.")
