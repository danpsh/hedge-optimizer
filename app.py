import streamlit as st
import requests

# 1. Math Helper
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

# 2. Setup
st.set_page_config(page_title="Hedge Pro", layout="centered", page_icon="💰")

if 'main_odds' not in st.session_state: st.session_state['main_odds'] = 300
if 'hedge_odds' not in st.session_state: st.session_state['hedge_odds'] = -350

st.title("💰 Hedge Pro Scanner")

# --- STEP 1: DROPDOWNS ---
st.subheader("⚙️ Step 1: Set Your Promo")
col1, col2 = st.columns(2)

with col1:
    promo_type = st.selectbox("Promo Type", ["Bonus Bet (Free Bet)", "Profit Boost", "No-Sweat Bet"])
    sport = st.selectbox("Select Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])

with col2:
    m_stake = st.number_input("Promo Amount ($)", value=50, step=10)
    round_bet = st.checkbox("Round Hedge to nearest $1", value=True)

# --- STEP 2: SCANNER ---
st.subheader("🔍 Step 2: Find Live Hedges")
st.write("Comparing **DraftKings** and **FanDuel** (Different Books Only)")

api_key = st.secrets.get("ODDS_API_KEY", "")

if st.button("Find Best Splits"):
    if not api_key:
        st.error("Missing API Key in Secrets!")
    else:
        TARGET_BOOKS = "draftkings,fanduel"
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
                                if dog['price'] >= 200: # Only look for high value
                                    dm, dh = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                    payout = (dm - 1) * m_stake if promo_type == "Bonus Bet (Free Bet)" else dm * m_stake
                                    h_stake = payout / dh
                                    p = payout - (h_stake if promo_type == "Bonus Bet (Free Bet)" else (m_stake + h_stake))
                                    
                                    opps.append({
                                        "game": f"{teams[0]} vs {teams[1]}",
                                        "dog": dog, "fav": fav, "profit": p,
                                        "u_key": f"btn_{dog['book']}_{fav['book']}_{dog['price']}_{fav['price']}"
                                    })

            sorted_opps = sorted(opps, key=lambda x: x['profit'], reverse=True)
            if not sorted_opps:
                st.warning("No split-book opportunities found right now.")
            
            for op in sorted_opps[:5]:
                with st.expander(f"Profit: ${op['profit']:.2f} — {op['game']}"):
                    st.write(f"🟢 **{op['dog']['book']}:** {op['dog']['name']} ({op['dog']['price']})")
                    st.write(f"🔵 **{op['fav']['book']}:** {op['fav']['name']} ({op['fav']['price']})")
                    if st.button("Load into Calculator", key=op['u_key']):
                        st.session_state['main_odds'] = op['dog']['price']
                        st.session_state['hedge_odds'] = op['fav']['price']
                        st.rerun()

st.markdown("---")

# --- STEP 3: CALCULATOR ---
st.subheader("🧮 Step 3: Final Calculation")
c3, c4 = st.columns(2)

with c3:
    m_odds = st.number_input("Underdog Odds (Promo)", value=st.session_state['main_odds'])
    h_odds = st.number_input("Favorite Odds (Hedge)", value=st.session_state['hedge_odds'])

# Math Logic
dm, dh = american_to_decimal(m_odds), american_to_decimal(h_odds)

if promo_type == "Bonus Bet (Free Bet)":
    target = m_stake * (dm - 1)
    hedge = target / dh
elif promo_type == "Profit Boost":
    target = m_stake * dm
    hedge = target / dh
else: # No-sweat
    target = m_stake * dm
    hedge = (target - (m_stake * 0.7)) / dh

if round_bet: hedge = round(hedge)

if promo_type == "Bonus Bet (Free Bet)":
    final_p = target - hedge
else:
    final_p = target - (m_stake + hedge)

with c4:
    st.metric("Hedge to Place", f"${hedge:.0f}" if round_bet else f"${hedge:.2f}")
    st.metric("Guaranteed Profit", f"${final_p:.2f}")
    st.write(f"**Conversion Rate:** {((final_p/m_stake)*100):.1f}%")
