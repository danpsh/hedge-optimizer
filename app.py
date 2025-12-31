import streamlit as st
import requests

def american_to_decimal(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Split-Book Scanner", layout="wide")

if 'main_odds' not in st.session_state: st.session_state['main_odds'] = 285
if 'hedge_odds' not in st.session_state: st.session_state['hedge_odds'] = -350

st.title("🎯 Multi-Book Hedge Scanner")
st.write("Ensuring the Underdog and Favorite are on **different sportsbooks** to protect your accounts.")

api_key = st.secrets.get("ODDS_API_KEY", "")

if api_key:
    sport = st.selectbox("Select Sport", ["basketball_nba", "americanfootball_nfl", "icehockey_nhl"])
    
    if st.button("🔍 Scan for Different-Book Hedges"):
        TARGET_BOOKS = "draftkings,fanduel,caesars,thescore,fanatics"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': TARGET_BOOKS}
        
        res = requests.get(url, params=params)
        if res.status_code == 200:
            games = res.json()
            opps = []

            for game in games:
                # 1. Collect all available odds for this specific game
                prices = []
                for book in game['bookmakers']:
                    outcomes = book['markets'][0]['outcomes']
                    for o in outcomes:
                        prices.append({
                            'book': book['title'],
                            'team': o['name'],
                            'price': o['price']
                        })
                
                # 2. Find the best "Dog" and "Fav" on DIFFERENT books
                teams = list(set([p['team'] for p in prices]))
                if len(teams) == 2:
                    team_a_odds = [p for p in prices if p['team'] == teams[0]]
                    team_b_odds = [p for p in prices if p['team'] == teams[1]]
                    
                    for a in team_a_odds:
                        for b in team_b_odds:
                            # Ensure books are different
                            if a['book'] != b['book']:
                                # Identify which is Dog/Fav
                                dog, fav = (a, b) if a['price'] > b['price'] else (b, a)
                                
                                if dog['price'] >= 200 and fav['price'] < 0:
                                    dm, dh = american_to_decimal(dog['price']), american_to_decimal(fav['price'])
                                    conv = (((dm-1)*100) - ((dm-1)*100/dh)) # Bonus Bet math
                                    
                                    opps.append({
                                        "game": f"{teams[0]} vs {teams[1]}",
                                        "dog_book": dog['book'], "dog_price": dog['price'],
                                        "fav_book": fav['book'], "fav_price": fav['price'],
                                        "conv": conv,
                                        "u_key": f"{dog['book']}_{fav['book']}_{game['id']}"
                                    })

            sorted_opps = sorted(opps, key=lambda x: x['conv'], reverse=True)
            for op in sorted_opps[:8]:
                with st.expander(f"{op['conv']:.1f}% Conv: {op['game']}"):
                    st.write(f"🚩 **PROMO SIDE:** {op['dog_book']} ({op['dog_price']})")
                    st.write(f"🛡️ **HEDGE SIDE:** {op['fav_book']} ({op['fav_price']})")
                    if st.button("Load Split", key=op['u_key']):
                        st.session_state['main_odds'] = op['dog_price']
                        st.session_state['hedge_odds'] = op['fav_price']
                        st.rerun()

st.markdown("---")
# (Rest of the calculator code from previous message remains the same)
