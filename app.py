import streamlit as st
import requests

# 1. Access your secret API key
API_KEY = st.secrets["ODDS_API_KEY"]

def fetch_live_odds(sport="upcoming"):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'h2h',
        'oddsFormat': 'american',
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch odds. Check your API key or limit.")
        return []

st.title("💰 Auto-Hedge Scanner")

if st.button("🔍 Scan for Top 5 Hedges"):
    data = fetch_live_odds("americanfootball_nfl") # Or 'basketball_nba'
    
    opportunities = []
    for game in data:
        home_team = game['home_team']
        away_team = game['away_team']
        
        # Get odds from the first two available bookmakers to compare
        for book in game['bookmakers']:
            odds = book['markets'][0]['outcomes']
            # Simple logic: assume we put the Bonus on the dog (+ odds) 
            # and hedge on the favorite (- odds)
            dog = next((o for o in odds if o['price'] > 200), None)
            fav = next((o for o in odds if o['price'] < 0), None)
            
            if dog and fav:
                opportunities.append({
                    "Game": f"{away_team} @ {home_team}",
                    "Book": book['title'],
                    "Dog": f"{dog['name']} ({dog['price']})",
                    "Fav": f"{fav['name']} ({fav['price']})",
                    "Profit_Potential": dog['price'] # Just a marker for now
                })
    
    # Display the top 5
    for op in opportunities[:5]:
        with st.expander(f"📈 {op['Game']} ({op['Book']})"):
            st.write(f"**Bonus Bet on:** {op['Dog']}")
            st.write(f"**Hedge on:** {op['Fav']}")
            if st.button(f"Load {op['Game']}", key=op['Game']):
                # This would push the odds into your calculator automatically
                st.session_state['main_odds'] = int(op['Dog'].split('(')[1].replace(')', ''))
                st.session_state['hedge_odds'] = int(op['Fav'].split('(')[1].replace(')', ''))
