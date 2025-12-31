import streamlit as st
import requests

def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Triple-Threat", layout="wide")

# --- STEP 1: DEFINE BOOSTER ---
st.title("Booster & Promo Optimizer")
st.subheader("Step 1: Input Your Promo Details")

with st.form("promo_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        boost_type = st.selectbox("Boost Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
    with col2:
        if boost_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost Percentage (%)", min_value=1, value=50)
        else:
            # For Bonus/No-Sweat, we assume a standard 70% conversion for the refund/credit
            boost_val = st.hidden = 0 
            st.info("Scanner will optimize for maximum guaranteed cash.")
    with col3:
        max_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
    
    submit_button = st.form_submit_button("Update and Scan All Sports")

# --- STEP 2: AUTO-SCAN RESULTS ---
st.markdown("---")
st.subheader("Step 2: Top 5 Global Hedges")

api_key = st.secrets.get("ODDS_API_KEY", "")

if not api_key:
    st.error("API Key Missing! Add ODDS_API_KEY to Streamlit Secrets.")
else:
    SPORTS_TO_SCAN = ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab"]
    TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
    all_opps = []

    with st.spinner("Finding the best math for your specific promo type..."):
        for sport in SPORTS_TO_SCAN:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
            res = requests.get(url, params=params)
            
            if res.status_code == 200:
                games = res.json()
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
                                if a['book'] != b['book']:
                                    dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                    dm, df = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                    
                                    if boost_type == "Profit Boost (%)":
                                        # Profit Boost: (Stake * (Odds-1) * (1+Boost)) + Stake
                                        total_return = (max_wager * (dm - 1) * (1 + (boost_val / 100))) + max_wager
                                        hedge_needed = total_return / df
                                        profit = total_return - (max_wager + hedge_needed)
                                    
                                    elif boost_type == "Bonus Bet":
                                        # Bonus Bet: Stake is NOT returned. Return = Stake * (Odds - 1)
                                        total_return = max_wager * (dm - 1)
                                        hedge_needed = total_return / df
                                        profit = total_return - hedge_needed # No initial cash cost for the bonus bet
                                        
                                    else: # No-Sweat Bet
                                        # No Sweat: If lose, get ~70% of stake back as bonus bet value
                                        refund_value = max_wager * 0.70
                                        total_return = max_wager * dm
                                        # Hedge to equalize (Win) and (Loss + Refund)
                                        hedge_needed = (total_return - refund_value) / df
                                        profit = total_return - (max_wager + hedge_needed)

                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']} ({sport.split('_')[1].upper()})",
                                        "dog_book": dog['book'], "dog_team": dog['team'], "dog_price": dog['price'],
                                        "fav_book": fav['book'], "fav_team": fav['team'], "fav_price": fav['price'],
                                        "profit": profit, "hedge": hedge_needed
                                    })

    sorted_opps = sorted(all_opps, key=lambda x: x['profit'], reverse=True)

    if not sorted_opps:
        st.warning("No profitable hedges found.")
    else:
        for i, op in enumerate(sorted_opps[:5]):
            with st.expander(f"RANK {i+1}: ${op['profit']:.2f} PROFIT - {op['game']}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**PROMO SIDE** ({op['dog_book']})")
                    st.code(f"Bet ${max_wager:.2f} on {op['dog_team']} @ {op['dog_price']}")
                with c2:
                    st.write(f"**CASH HEDGE** ({op['fav_book']})")
                    st.code(f"Bet ${op['hedge']:.2f} on {op['fav_team']} @ {op['fav_price']}")
                st.success(f"Guaranteed Profit: ${op['profit']:.2f}")
