import streamlit as st
import requests
from datetime import datetime, timezone

def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Smart Input", layout="wide")

st.title("Pre-Match Promo Optimizer")

# --- STEP 1: DYNAMIC PROMO CONFIGURATION ---
st.subheader("Step 1: Configure Your Promo")

with st.form("promo_form"):
    # First dropdown: Pick the Type
    promo_type = st.selectbox("Select Promo Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0, step=5.0)
    
    with col2:
        # Only show the percentage box if Profit Boost is selected
        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost Percentage (%)", min_value=1, max_value=200, value=50, step=5)
        else:
            # Placeholder for math logic
            boost_val = 0
            st.write("Math optimized for maximum conversion.")

    submit_button = st.form_submit_button("Update and Scan All Sports")

# --- STEP 2: AUTO-SCAN RESULTS ---
st.markdown("---")
st.subheader("Step 2: Top 5 Upcoming Hedges")

api_key = st.secrets.get("ODDS_API_KEY", "")
current_time = datetime.now(timezone.utc)

if not api_key:
    st.error("API Key Missing! Go to Settings > Secrets and add: ODDS_API_KEY = 'your_key'")
else:
    SPORTS_TO_SCAN = ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"]
    TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
    all_opps = []

    with st.spinner("Scanning for upcoming games..."):
        for sport in SPORTS_TO_SCAN:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
            
            try:
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    games = res.json()
                    for game in games:
                        # Check if game is in the future
                        start_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if start_time <= current_time:
                            continue 
                        
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
                                    if a['book'] != b['book']:
                                        dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                        dm, df = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                        
                                        if promo_type == "Profit Boost (%)":
                                            total_return = (max_wager * (dm - 1) * (1 + (boost_val / 100))) + max_wager
                                            hedge_needed = total_return / df
                                            profit = total_return - (max_wager + hedge_needed)
                                        
                                        elif promo_type == "Bonus Bet":
                                            total_return = max_wager * (dm - 1)
                                            hedge_needed = total_return / df
                                            profit = total_return - hedge_needed
                                            
                                        else: # No-Sweat Bet
                                            refund_value = max_wager * 0.70
                                            total_return = max_wager * dm
                                            hedge_needed = (total_return - refund_value) / df
                                            profit = total_return - (max_wager + hedge_needed)

                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "sport": sport.split('_')[1].upper(),
                                            "start": start_time.strftime("%m/%d %I:%M %p"),
                                            "dog_book": dog['book'], "dog_team": dog['team'], "dog_price": dog['price'],
                                            "fav_book": fav['book'], "fav_team": fav['team'], "fav_price": fav['price'],
                                            "profit": profit, "hedge": hedge_needed
                                        })
            except:
                continue

    # Rank by Profit
    sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)

    if not sorted_opps:
        st.warning("No upcoming matches found with these books. Try again later!")
    else:
        for i, op in enumerate(sorted_opps[:5]):
            with st.expander(f"Rank {i+1}: ${op['profit']:.2f} Profit | {op['game']} ({op['sport']})"):
                st.write(f"**Game Start:** {op['start']} UTC")
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"**PROMO SIDE: {op['dog_book']}**")
                    st.write(f"Team: {op['dog_team']}")
                    st.write(f"Odds: {op['dog_price']}")
                    st.code(f"Bet: ${max_wager:.2f}")
                with c2:
                    st.info(f"**HEDGE SIDE: {op['fav_book']}**")
                    st.write(f"Team: {op['fav_team']}")
                    st.write(f"Odds: {op['fav_price']}")
                    st.code(f"Bet: ${op['hedge']:.2f}")
                st.success(f"Guaranteed Profit: ${op['profit']:.2f}")
