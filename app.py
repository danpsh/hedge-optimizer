import streamlit as st

def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

st.set_page_config(page_title="Hedge Pro Optimizer", layout="wide")

st.title("💰 Sportsbook Promo & Hedge Optimizer")
st.write("Convert your site credits and boosts into guaranteed cash.")
st.markdown("---")

# Sidebar for Inputs
st.sidebar.header("1. The Promo (The 'Dog' Side)")
promo_type = st.sidebar.selectbox("Promo Type", ["Bonus Bet (Free Bet)", "Profit Boost", "No-Sweat Bet"])
main_odds = st.sidebar.number_input("Underdog Odds (e.g. +350)", value=350)
main_stake = st.sidebar.number_input("Promo Amount ($)", value=100)

st.sidebar.header("2. The Hedge (The 'Fav' Side)")
hedge_odds = st.sidebar.number_input("Favorite Odds (e.g. -400)", value=-400)

# Calculations
d_main = american_to_decimal(main_odds)
d_hedge = american_to_decimal(hedge_odds)

if promo_type == "Bonus Bet (Free Bet)":
    # Winnings = Stake * (Decimal - 1) | Stake is NOT returned
    target_payout = main_stake * (d_main - 1)
    hedge_stake = target_payout / d_hedge
    net_profit = target_payout - hedge_stake  # Main stake was free credit
    
elif promo_type == "Profit Boost":
    boost_pct = st.sidebar.slider("Boost %", 0, 100, 50)
    # Boost applies to net profit
    boosted_payout_mult = ((d_main - 1) * (1 + boost_pct/100)) + 1
    target_payout = main_stake * boosted_payout_mult
    hedge_stake = target_payout / d_hedge
    net_profit = target_payout - (main_stake + hedge_stake)

elif promo_type == "No-Sweat Bet":
    # Calculated based on 70% retention of the refund
    refund_val = main_stake * 0.70
    target_payout = main_stake * d_main
    hedge_stake = (target_payout - refund_val) / d_hedge
    net_profit = target_payout - (main_stake + hedge_stake)

# Results Display
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Hedge Amount (on Favorite)", f"${hedge_stake:.2f}")
with col2:
    st.metric("Guaranteed Profit", f"${net_profit:.2f}")
with col3:
    conversion_rate = (net_profit / main_stake) * 100
    st.metric("Conversion Rate", f"{conversion_rate:.1f}%")

st.markdown("---")
st.subheader("Scenario Breakdown")
st.table([
    {
        "If this side wins...": "Underdog (Promo)", 
        "Payout": f"${target_payout:.2f}", 
        "Minus Hedge Loss": f"-${hedge_stake:.2f}", 
        "Net Profit": f"${net_profit:.2f}"
    },
    {
        "If this side wins...": "Favorite (Hedge)", 
        "Payout": f"${hedge_stake * d_hedge:.2f}", 
        "Minus Total Cost": f"-${hedge_stake if promo_type == 'Bonus Bet (Free Bet)' else (main_stake + hedge_stake):.2f}", 
        "Net Profit": f"${net_profit:.2f}"
    }
])