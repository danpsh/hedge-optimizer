import streamlit as st
import requests

def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Universal Booster", layout="wide")

# --- STEP 1: PICK YOUR BOOST ---
st.title("Universal Booster & Global Scanner")
st.subheader("Step 1: Define Your Custom Booster")

col1, col2, col3 = st.columns(3)
with col1:
    boost_type = st.selectbox("Boost Type", ["Profit Boost (%)", "Odds Boost (Fixed Odds)"])
with col2:
    if boost_type == "Profit Boost (%)":
        boost_val = st.number_input("Boost Percentage (%)", min_value=1, value=50)
    else:
        boost_val = st.number_input("New Boosted Odds (e.g., +400)", value=400)
with col3:
    max_wager = st.number_input("Max Wager Amount ($)", min_value=1, value=50)

# --- STEP 2: GLOBAL SCANNER ---
st.markdown("---")
st.subheader("Step 2: Top 5 Global Opportunities")
sport_choice = st.selectbox("Choose Sport to Scan", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"])

api_key = st.secrets.get("ODDS_API_KEY", "")

if not api_key:
    st.error("API Key Missing! Please add ODDS_API_KEY to your Streamlit Secrets.")
else:
    if st.button("Find Top 5 Hedges"):
        TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
        url = f"https://api.the-odds-api.com/v4/sports/{sport_choice}/odds/"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
        
        res = requests.get(url, params=params)
        if res.status_code == 200:
            games = res.json()
            opps = []

            for game in games:
                prices = []
                for book in game['bookmakers']:
                    for market in book['markets']:
                        for o in market['outcomes']:
                            prices.append({'book': book['title'], 'team': o['name'], 'price': o['price']})
                
                teams = list(set([p['team'] for p in prices]))
                if len(teams) == 2:
                    team_a_odds = [p for p in prices if p['team'] == teams[0]]
                    team_b_odds = [p for p in prices if p['team'] == teams[1]]
                    
                    for a in team_a_odds:
                        for b in team_b_odds:
                            # Must be different books to avoid bans
                            if a['book'] != b['book']:
                                dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                
                                # Apply the user's custom boost to the Underdog
                                if boost_type == "Profit Boost (%)":
                                    orig_payout = (american_to_decimal(dog['price']) - 1) * max_wager
                                    total_return = (orig_payout * (1 + (boost_val / 100))) + max_wager
                                else:
                                    total_return = (american_to_decimal(boost_val) - 1) * max_wager + max_wager
                                
                                # Calculate optimal hedge on the Favorite
                                fav_decimal = american_to_decimal(fav['price'])
                                hedge_needed = total_return / fav_decimal
                                guaranteed_profit = total_return - (max_wager + hedge_needed)
                                
                                opps.append({
                                    "game": f"{game['away_team']} vs {game['home_team']}",
                                    "dog_book": dog['book'], "dog_team": dog['team'], "dog_price": dog['price'],
                                    "fav_book": fav['book'], "fav_team": fav['team'], "fav_price": fav['price'],
                                    "profit": guaranteed_profit,
                                    "hedge": hedge_needed,
                                    "return": total_return
                                })

            # Rank by highest profit regardless of team or league spot
            sorted_opps = sorted(opps, key=lambda x: x['profit'], reverse=True)

            if not sorted_opps:
                st.warning("No hedge opportunities found for these parameters.")
            else:
                for i, op in enumerate(sorted_opps[:5]):
                    with st.expander(f"Option {i+1}: ${op['profit']:.2f} Profit - {op['game']}"):
                        col_left, col_right = st.columns(2)
                        with col_left:
                            st.write(f"**BOOSTED BET**")
                            st.write(f"Book: {op['dog_book']}")
                            st.write(f"Team: {op['dog_team']}")
                            st.write(f"Odds: {op['dog_price']}")
                            st.info(f"Wager: ${max_wager:.2f}")
                        with col_right:
                            st.write(f"**CASH HEDGE**")
                            st.write(f"Book: {op['fav_book']}")
                            st.write(f"Team: {op['fav_team']}")
                            st.write(f"Odds: {op['fav_price']}")
                            st.info(f"Wager: ${op['hedge']:.2f}")
                        st.success(f"Locked Profit: ${op['profit']:.2f}")
        else:
            st.error("API Error. Please check your Odds API key and usage limits.")
