import streamlit as st
import requests

def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Big Three", layout="wide", page_icon="💰")

# Initialize Session State
if 'main_odds' not in st.session_state: st.session_state['main_odds'] = 350
if 'hedge_odds' not in st.session_state: st.session_state['hedge_odds'] = -400

st.title("💰 Hedge Pro: Promo Optimizer")

# --- STEP 1: PROMO CONFIG ---
st.subheader(⚙️ Step 1: Promo Configuration")
c1, c2, c3 = st.columns([2, 2, 3])

with c1:
    promo_type = st.selectbox(
        "Promo Type", 
        ["Bonus Bet (Free Bet)", "Profit Boost", "No-Sweat Bet"],
        help="Bonus Bet: Stake not returned. Profit Boost: Extra % on winnings. No-Sweat: Refund if you lose."
    )
with c2:
    m_stake = st.number_input("Promo Amount ($)", value=100, step=10)
with c3:
    if promo_type == "Profit Boost":
        boost_pct = st.slider("Boost Percentage (%)", 0, 100, 50)
    elif promo_type == "No-Sweat Bet":
        st.info("Calculated using 70% refund conversion.")
    else:
        st.write("Target: High Underdogs (+300 or better)")

st.markdown("---")

# --- STEP 2: SCANNER ---
st.subheader("🔍 Step 2: Live Multi-Book Scanner")
api_key = st.secrets.get("ODDS_API_KEY", "")

if api_key:
    col_a, col_b = st.columns([1, 4])
    with col_a:
        sport = st.selectbox("Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])
        scan_btn = st.button("🔍 Scan Best Splits")

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
                for b in game['bookmakers']:
                    for o in b['markets'][0]['outcomes']:
                        prices.append({'book': b['title'], 'team': o['name'], 'price': o['price']})
                
                teams = list(set([p['team'] for p in prices]))
                if len(teams) == 2:
                    team_a = [p for p in prices if p['team'] == teams[0]]
                    team_b = [p for p in prices if p['team'] == teams[1]]
                    for a in team_a:
                        for b in team_b:
                            if a['book'] != b['book']:
                                dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                if dog['price'] >= 200:
                                    dm, dh = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                    conv = ((dm-1)*100) - ((dm-1)*100/dh)
                                    opps.append({
                                        "game": f"{teams[0]} vs {teams[1]}",
                                        "dog_book": dog['book'], "dog_price": dog['price'],
                                        "fav_book": fav['book'], "fav_price": fav['price'],
                                        "conv": conv,
                                        "u_key": f"btn_{dog['book']}_{fav['book']}_{game['id']}_{dog['price']}"
                                    })
            
            for op in sorted(opps, key=lambda x: x['conv'], reverse=True)[:5]:
                with st.expander(f"📈 {op['conv']:.1f}% Conv — {op['game']}"):
                    st.write(f"🚩 **{op['dog_book']}:** {op['dog_price']} | 🛡️ **{op['fav_book']}:** {op['fav_price']}")
                    if st.button("Load Hedge", key=op['u_key']):
                        st.session_state['main_odds'] = op['dog_price']
                        st.session_state['hedge_odds'] = op['fav_price']
                        st.rerun()

st.markdown("---")

# --- STEP 3: CALCULATOR ---
st.subheader("🧮 Step 3: Final Math")
m1, m2 = st.columns(2)
with m1:
    main_odds = st.number_input("Underdog Odds", value=st.session_state['main_odds'])
    hedge_odds = st.number_input("Favorite Odds", value=st.session_state['hedge_odds'])

dm, dh = american_to_decimal(main_odds), american_to_decimal(hedge_odds)

if promo_type == "Bonus Bet (Free Bet)":
    payout = m_stake * (dm - 1)
    hedge = payout / dh
    profit = payout - hedge
elif promo_type == "Profit Boost":
    boost_mult = (dm - 1) * (1 + (boost_pct / 100))
    payout = m_stake * (boost_mult + 1)
    hedge = payout / dh
    profit = payout - (m_stake + hedge)
else: # No-Sweat
    refund = m_stake * 0.70
    payout = m_stake * dm
    hedge = (payout - refund) / dh
    profit = payout - (m_stake + hedge)

with m2:
    st.success(f"**Hedge Amount:** ${hedge:.2f}")
    st.metric("Guaranteed Profit", f"${profit:.2f}")
    st.info(f"Conversion: {(profit/m_stake)*100:.1f}%")
