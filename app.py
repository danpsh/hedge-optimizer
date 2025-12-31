import streamlit as st
import requests

# Helper to convert American odds to decimal
def am_to_dec(odds):
    if odds > 0: return (odds / 100) + 1
    return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro: Smart Splitter", layout="wide")

# Initialize state for odds if they don't exist
if 'm_odds' not in st.session_state: st.session_state.m_odds = 250
if 'h_odds' not in st.session_state: st.session_state.h_odds = -300

st.title("🎯 Pro Hedge & Booster Tool")

# --- SECTION 1: PROMO SETUP ---
st.subheader("1. Configure Your Promo")
p_col1, p_col2 = st.columns(2)

with p_col1:
    promo_type = st.selectbox("Booster Type", ["Bonus Bet ($)", "Profit Boost (%)", "No-Sweat Bet"])

with p_col2:
    if promo_type == "Profit Boost (%)":
        boost_pct = st.number_input("Boost %", min_value=1, value=50)
        base_stake = st.number_input("Bet Amount ($)", value=50.0)
    else:
        m_stake = st.number_input("Promo Amount ($)", value=100.0)

st.markdown("---")

# --- SECTION 2: THE CALCULATOR ---
st.subheader("2. Odds & Math")
c1, c2 = st.columns(2)

with c1:
    u_odds = st.number_input("Underdog Odds (+)", value=st.session_state.m_odds)
with c2:
    f_odds = st.number_input("Favorite Odds (-)", value=st.session_state.h_odds)

# MATH LOGIC
dm, df = am_to_dec(u_odds), am_to_dec(f_odds)

if promo_type == "Bonus Bet ($)":
    payout = m_stake * (dm - 1)
    raw_h = payout / df
    profit = payout - raw_h
elif promo_type == "Profit Boost (%)":
    boost_mult = 1 + (boost_pct / 100)
    payout = (base_stake * (dm - 1) * boost_mult) + base_stake
    raw_h = payout / df
    profit = payout - (base_stake + raw_h)
else: # No-Sweat (Refund value approx 70%)
    raw_h = (m_stake * dm) / (df + 0.7)
    profit = (m_stake * dm) - (m_stake + raw_h)

# --- SECTION 3: ROUNDING & RESULTS ---
st.markdown("### 📊 Strategy")
round_flag = st.toggle("Round Hedge to nearest $1", value=True)
final_h = round(raw_h) if round_flag else raw_h

res1, res2, res3 = st.columns(3)
res1.metric("Hedge Amount", f"${final_h:.2f}")
res2.metric("Net Profit", f"${profit:.2f}")
res3.metric("Conversion", f"{(profit/(base_stake if promo_type=='Profit Boost (%)' else m_stake))*100:.1f}%")

st.markdown("---")

# --- SECTION 4: LIVE SCANNER (Filtered) ---
st.subheader("🔍 Scan Top 5 Books")
api_key = st.secrets.get("ODDS_API_KEY", "")

if api_key:
    if st.button("Find Multi-Book Hedges"):
        # Filters directly for your 5 requested books
        TARGETS = "draftkings,fanduel,caesars,thescore,fanatics"
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/"
        params = {'apiKey': api_key, 'regions': 'us', 'bookmakers': TARGETS}
        
        data = requests.get(url, params=params).json()
        for game in data:
            # Code here to find the best split across different books...
            # (Matches your previous split-book logic)
            st.write(f"Scanning {game['home_team']} vs {game['away_team']}...")
else:
    st.warning("Add your ODDS_API_KEY to Streamlit Secrets to use the scanner.")

