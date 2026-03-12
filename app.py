import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- TECH THEME CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
    }
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; font-family: 'Courier New', monospace; font-weight: 800;
    }
    .stButton>button {
        background-color: #1e1e1e; color: #00ff88; border: none; border-radius: 8px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_multiplier(american_odds):
    return (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))

# --- SHARED DATA ---
book_map = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "BetMGM": "betmgm",
    "theScore / ESPN": "espnbet",
    "Bet365": "bet365",
    "Caesars": "caesars",
    "All Books": "allbooks"
}

sports_map = {
    "NBA": "basketball_nba", 
    "NCAAB": "basketball_ncaab", 
    "NHL": "icehockey_nhl", 
    "Boxing": "boxing_boxing", 
    "MMA": "mma_mixed_martial_arts" 
}
sport_labels = list(sports_map.keys())

# --- HEADER ---
st.title("Promo Converter")
quota_placeholder = st.empty()

# --- SECTION 1: GLOBAL SCANNER ---
st.subheader("Global scanner")
with st.expander("Scan all markets for a specific promo type", expanded=False):
    with st.form("global_scan_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            g_strat = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with c2:
            g_book = st.selectbox("Source book", list(book_map.keys())[:-1])
        with c3:
            g_hedge = st.selectbox("Hedge book", list(book_map.keys()))
        
        g_sports = st.multiselect("Sports", sport_labels, default=["NBA", "NHL"])
        col_w, col_b = st.columns(2)
        g_wager = col_w.number_input("Wager ($)", value=50.0)
        g_boost = col_b.number_input("Boost (%)", value=50) if g_strat == "Profit Boost (%)" else 0
        
        run_g = st.form_submit_button("Run global scanner", use_container_width=True)

# --- SECTION 2: MULTI-PROMO OPTIMIZER ---
st.write("---")
st.subheader("Multi-promo optimizer")
with st.expander("Run two promos against each other (Cross-arb)", expanded=False):
    with st.form("multi_scan_form"):
        ml, mr = st.columns(2)
        with ml:
            st.markdown("**Side A**")
            ma_strat = st.selectbox("Strategy A", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="ma1")
            ma_book = st.selectbox("Book A", ["draftkings", "fanduel", "betmgm", "espnbet"], key="ma2")
            ma_wager = st.number_input("Max wager A ($)", value=50.0, key="ma3")
            ma_boost = st.number_input("Boost A (%)", value=50, key="ma4") if ma_strat == "Profit Boost (%)" else 0
        with mr:
            st.markdown("**Side B**")
            mb_strat = st.selectbox("Strategy B", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Cash"], key="mb1")
            mb_book = st.selectbox("Book B", ["fanduel", "draftkings", "betmgm", "espnbet"], key="mb2")
            mb_wager = st.number_input("Max wager B ($)", value=50.0, key="mb3")
            mb_boost = st.number_input("Boost B (%)", value=0, key="mb4") if mb_strat == "Profit Boost (%)" else 0
        
        m_sports = st.multiselect("Sports", sport_labels, default=["NBA", "NHL"], key="ms")
        run_m = st.form_submit_button("Run cross-promo optimizer", use_container_width=True)

# --- SECTION 3: SINGLE PROMO TARGETER ---
st.write("---")
st.subheader("Single promo targeter")
with st.expander("Find the best play for one specific boost", expanded=False):
    with st.form("target_form"):
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            t_book = st.selectbox("Sportsbook", ["draftkings", "fanduel", "betmgm", "espnbet"], key="t1")
            t_strat = st.selectbox("Boost type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="t2")
        with t_col2:
            t_wager = st.number_input("Wager ($)", value=50.0, key="t3")
            t_boost = st.number_input("Boost (%)", value=50, key="t4") if t_strat == "Profit Boost (%)" else 0
        
        t_sports = st.multiselect("Sports", sport_labels, default=["NBA"], key="t5")
        run_t = st.form_submit_button("Find best play", use_container_width=True)

# --- SECTION 4: GAMEPLAN ARCHITECT ---
st.write("---")
st.subheader("Gameplan architect")
with st.expander("Build your daily betting strategy", expanded=True):
    if 'promos' not in st.session_state: st.session_state.promos = []

    with st.form("gp_form"):
        ga, gb, gc = st.columns([2,2,1])
        with ga:
            gp_b = st.selectbox("Book", list(book_map.keys())[:-1], key="gpb")
            gp_s = st.selectbox("Type", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], key="gps")
        with gb:
            gp_w = st.number_input("Wager", value=25.0, key="gpw")
            gp_v = st.number_input("Boost %", value=50, key="gpv")
        with gc:
            gp_sp = st.multiselect("Sports", sport_labels, default=["NBA"], key="gpsp")
        
        if st.form_submit_button("Add to gameplan"):
            st.session_state.promos.append({"book": gp_b, "strat": gp_s, "wager": gp_w, "val": gp_v, "sports": gp_sp})

    if st.session_state.promos:
        for i, p in enumerate(st.session_state.promos):
            st.write(f"**{i+1}. {p['book']}** {p['strat']} (${p['wager']})")
        
        if st.button("Clear all"): 
            st.session_state.promos = []
            st.rerun()

        mode = st.radio("Execution mode", ["Independent (Max EV)", "Cross-Arb (Guaranteed Cash)"], horizontal=True)
        
        if st.button("Generate gameplan"):
            st.write("### Recommended gameplan")
            if mode == "Independent (Max EV)":
                for p in st.session_state.promos:
                    if p['strat'] == "Bonus Bet":
                        st.success(f"**{p['book']} Strategy:** Place on an Underdog (+250 to +400). Hedge on a different book to convert ~70%.")
                    elif p['strat'] == "Profit Boost (%)":
                        st.success(f"**{p['book']} Strategy:** Place on a tight Pick-em (-110). Hedge to lock in ~20% of stake.")
                    else:
                        st.success(f"**{p['book']} Strategy:** Place on a slight Underdog (+120). Use the refund as a Bonus Bet if it loses.")
            else:
                st.info("Scanner running cross-reference between your added promos... (Connect API to see live matches)")

# --- MANUAL CALCULATOR ---
st.write("---")
st.subheader("Manual calculator")
with st.expander("Quick hedge tool"):
    m_odds = st.number_input("Source odds", value=200)
    m_hedge = st.number_input("Hedge odds", value=-220)
    m_w = st.number_input("Wager", value=50.0)
    if st.button("Calculate"):
        sm, hm = get_multiplier(m_odds), get_multiplier(m_hedge)
        h_amt = (m_w * (1 + sm)) / (1 + hm)
        st.metric("Hedge bet", f"${h_amt:.2f}")
        st.metric("Net profit", f"${(m_w * sm) - h_amt:.2f}")

# --- API LOGIC PLACEHOLDER ---
# Note: To run live, ensure 'ODDS_API_KEY' is in your Streamlit Secrets.
