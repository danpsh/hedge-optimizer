import streamlit as st
import requests

# Helper function for math
def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: 5-Book Scanner", layout="wide")

# Initialize session state for the calculator
if 'main_odds' not in st.session_state:
    st.session_state['main_odds'] = 285
if 'hedge_odds' not in st.session_state:
    st.session_state['hedge_odds'] = -350

st.title("🎯 Top 5 Bookmaker Scanner")
st.info("Searching: DraftKings, FanDuel, theScore, Caesars, and Fanatics")

# --- SECTION 1: API SCANNER ---
api_key = st.secrets.get("ODDS_API_KEY", "")

if not api_key:
    st.error("Missing API Key! Please add ODDS_API_KEY to your Streamlit Secrets.")
else:
    col_a, col_b = st.columns([1, 4])
    with col_a:
        sport = st.selectbox("Select Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])
        scan_btn = st.button("🔍 Find Best Hedges")

    if scan_btn:
        # We specify the exact bookmakers in the API call to save 'credits' and focus results
        TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            'apiKey': api_key,
            'regions': 'us',
            'markets': 'h2h',
            'oddsFormat': 'american',
            'bookmakers': TARGET_BOOKS  # Filters the API results directly
        }
        
        res = requests.get(url, params=params)
        
        if res.status_code == 200:
            games = res.json()
            all_opportunities = []

            for game in games:
                for book in game['bookmakers']:
                    outcomes = book['markets'][0]['outcomes']
                    # Look for Dog (Positive odds) and Fav (Negative odds)
                    dog = next((o for o in outcomes if o['price'] >= 200), None)
                    fav = next((o for o in outcomes if o['price'] < 0), None)
                    
                    if dog and fav:
                        # Quick math to find the conversion rate for sorting
                        dm, dh = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                        payout = (dm - 1) * 100 # Assumes $100 bonus bet
                        h_stake = payout / dh
                        conv = ((payout - h_stake) / 100) * 100
                        
                        all_opportunities.append({
                            "game": f"{game['away_team']} @ {game['home_team']}",
                            "book": book['title'],
                            "dog_price": dog['price'],
                            "fav_price": fav['price'],
                            "conv": conv,
                            "u_key": f"load_{game['home_team']}_{book['title']}_{dog['price']}".replace(" ", "_")
                        })

            # Sort by highest conversion first
            sorted_opps = sorted(all_opportunities, key=lambda x: x['conv'], reverse=True)

            if not sorted_opps:
                st.warning("No great hedge opportunities found in these books right now.")
            
            for op in sorted_opps[:10]: # Show top 10
                with st.expander(f"{op['conv']:.1f}% Conv — {op['game']} ({op['book']})"):
                    st.write(f"**Underdog:** {op['dog_price']} | **Favorite:** {op['fav_price']}")
                    if st.button(f"Load into Calculator", key=op['u_key']):
                        st.session_state['main_odds'] = op['dog_price']
                        st.session_state['hedge_odds'] = op['fav_price']
                        st.rerun()
        else:
            st.error(f"API Error: {res.status_code}. Check your key or usage limits.")

st.markdown("---")

# --- SECTION 2: THE CALCULATOR ---
st.subheader("🧮 Calculator")
c1, c2, c3 = st.columns(3)
with c1:
    promo_type = st.selectbox("Promo Type", ["Bonus Bet (Free Bet)", "Profit Boost", "No-Sweat Bet"])
    m_odds = st.number_input("Underdog Odds (+)", value=st.session_state['main_odds'])
with c2:
    m_stake = st.number_input("Promo Amount ($)", value=250)
    h_odds = st.number_input("Favorite Odds (-)", value=st.session_state['hedge_odds'])
with c3:
    # Bonus Math Logic
    dm, dh = american_to_decimal(m_odds), american_to_decimal(h_odds)
    if promo_type == "Bonus Bet (Free Bet)":
        target = m_stake * (dm - 1)
        h_stake = target / dh
        profit = target - h_stake
    else:
        target = m_stake * dm
        h_stake = target / dh
        profit = target - (m_stake + h_stake)

    st.metric("Hedge Amount", f"${h_stake:.2f}")
    st.metric("Guaranteed Profit", f"${profit:.2f}")
    st.write(f"**Conversion:** {(profit/m_stake)*100:.1f}%")
