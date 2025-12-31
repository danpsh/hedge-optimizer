import streamlit as st
import requests

# 1. Helper Function: Math Conversion
def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

# 2. Page Configuration
st.set_page_config(page_title="Hedge Pro Scanner", layout="wide")

# 3. Initialize Session State
if 'main_odds' not in st.session_state:
    st.session_state['main_odds'] = 300
if 'hedge_odds' not in st.session_state:
    st.session_state['hedge_odds'] = -350

# --- SIDEBAR ---
st.sidebar.title("Promo Settings")
promo_type = st.sidebar.selectbox("Promo Type", ["Bonus Bet (Free Bet)", "Profit Boost", "No-Sweat Bet"])
m_stake = st.sidebar.number_input("Promo Amount ($)", value=100)
round_bet = st.sidebar.checkbox("Round Hedge to nearest $5", value=True)

# --- SECTION 1: SCANNER ---
st.title("Multi-Book Hedge Scanner")
st.write("Finding the best Underdog and Favorite on different books.")

api_key = st.secrets.get("ODDS_API_KEY", "")

if not api_key:
    st.error("API Key Missing! Add ODDS_API_KEY to your Streamlit Secrets.")
else:
    col_a, col_b = st.columns([1, 4])
    with col_a:
        sport = st.selectbox("Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])
        scan_btn = st.button("Find Different-Book Hedges")

    if scan_btn:
        TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
        
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
                
                teams = list(set([p['team'] for p in prices]))
                if len(teams) == 2:
                    team_a_odds = [p for p in prices if p['team'] == teams[0]]
                    team_b_odds = [p for p in prices if p['team'] == teams[1]]
                    
                    for a in team_a_odds:
                        for b in team_b_odds:
                            if a['book'] != b['book']:
                                dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                if dog['price'] >= 250 and fav['price'] < 0:
                                    dm, dh = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                    payout = (dm - 1) * 100
                                    h_stake = payout / dh
                                    conv = (payout - h_stake)
                                    
                                    opps.append({
                                        "game": f"{teams[0]} vs {teams[1]}",
                                        "dog_book": dog['book'], "dog_price": dog['price'],
                                        "fav_book": fav['book'], "fav_price": fav['price'],
                                        "conv": conv,
                                        "u_key": f"btn_{dog['book']}_{fav['book']}_{dog['price']}_{fav['price']}".replace(" ", "_")
                                    })

            sorted_opps = sorted(opps, key=lambda x: x['conv'], reverse=True)
            for op in sorted_opps[:8]:
                with st.expander(f"{op['conv']:.1f}% Conversion - {op['game']}"):
                    st.write(f"PROMO ON: {op['dog_book']} ({op['dog_price']})")
                    st.write(f"HEDGE ON: {op['fav_book']} ({op['fav_price']})")
                    if st.button("Use this Hedge", key=op['u_key']):
                        st.session_state['main_odds'] = op['dog_price']
                        st.session_state['hedge_odds'] = op['fav_price']
                        st.rerun()

st.markdown("---")

# --- SECTION 2: CALCULATOR ---
st.subheader("Final Calculation")
c1, c2 = st.columns(2)

with c1:
    main_odds = st.number_input("Underdog Odds (Promo)", value=st.session_state['main_odds'])
    hedge_odds = st.number_input("Favorite Odds (Cash)", value=st.session_state['hedge_odds'])

dm, dh = american_to_decimal(main_odds), american_to_decimal(hedge_odds)

if promo_type == "Bonus Bet (Free Bet)":
    target_win = m_stake * (dm - 1)
    hedge_needed = target_win / dh
elif promo_type == "Profit Boost":
    target_win = m_stake * dm
    hedge_needed = target_win / dh
else: # No-sweat
    refund_val = m_stake * 0.70
    target_win = m_stake * dm
    hedge_needed = (target_win - refund_val) / dh

if round_bet:
    hedge_needed = 5 * round(hedge_needed / 5)

if promo_type == "Bonus Bet (Free Bet)":
    net_profit = target_win - hedge_needed
else:
    net_profit = target_win - (m_stake + hedge_needed)

with c2:
    st.metric("Hedge to Place", f"${hedge_needed:.0f}" if round_bet else f"${hedge_needed:.2f}")
    st.metric("Guaranteed Profit", f"${net_profit:.2f}")
    st.write(f"Conversion: {((net_profit/m_stake)*100):.1f}%")
