import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arbitrage Edge", layout="wide")

# --- LIGHT TECH THEME (White Background) ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    
    /* Clean White Cards */
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"]:hover {
        border: 1px solid #00ff88;
        box-shadow: 0 4px 12px rgba(0, 255, 136, 0.15);
    }

    /* Metric Styling */
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; 
        font-family: 'Courier New', monospace; 
        font-weight: 800;
    }
    
    /* Input Containers */
    div.row-widget.stRadio > div {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
    }

    /* Stealth EXECUTE Button */
    .stButton>button {
        background-color: #1e1e1e;
        color: #00ff88;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #00ff88;
        color: #1e1e1e;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("📟 ARB TERMINAL")
    st.info("Strategy: FD & DK Source Only")
    quota_placeholder = st.empty()

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2 = st.columns(2)
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"], horizontal=True)
        with col2:
            source_book_display = st.radio("Source Book", ["DraftKings", "FanDuel"], horizontal=True)
            source_book = source_book_display.lower()

        st.divider()
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB", "NCAAF"], horizontal=True)
        with col4:
            max_wager = st.number_input("Wager ($)", min_value=1.0, value=50.0)

        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost (%)", min_value=1, value=50)
        else:
            boost_val = 0

        run_scan = st.form_submit_button("EXECUTE LIVE SCAN")

# --- STANDALONE MANUAL CALCULATOR ---
st.write("---")
st.subheader("🧮 Manual Multi-Strategy Calculator")

with st.expander("Open Manual Calculator", expanded=True):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet (SNR)", "No-Sweat Bet"], horizontal=True)
        
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_s_price = st.number_input("Source Odds (Underdog) e.g. 250", value=250)
            m_wager = st.number_input("Wager Amount ($)", min_value=1.0, value=50.0)
            if m_promo == "Profit Boost (%)":
                m_boost = st.number_input("Boost %", min_value=0, value=50)
        
        with m_col2:
            # Type 300, code makes it -300
            h_input = st.number_input("Hedge Odds (Favorite) e.g. 300", value=300)
            m_h_price = -abs(h_input)
            st.caption(f"Treating Favorite as: **{m_h_price}**")
            
            if m_promo == "No-Sweat Bet":
                m_conv = st.number_input("Refund Conversion %", value=70) / 100

        submit_calc = st.form_submit_button("📊 CALCULATE HEDGE", type="primary", use_container_width=True)

    if submit_calc:
        # American to Multiplier Logic
        ms_m = (m_s_price / 100) if m_s_price > 0 else (100 / abs(m_s_price))
        mh_m = (m_h_price / 100) if m_h_price > 0 else (100 / abs(m_h_price))

        if m_promo == "Profit Boost (%)":
            boost_f = 1 + (m_boost / 100)
            boosted_ms_m = ms_m * boost_f
            m_hedge = (m_wager * (1 + boosted_ms_m)) / (1 + mh_m)
            m_profit = (m_wager * boosted_ms_m) - m_hedge
        elif m_promo == "Bonus Bet (SNR)":
            m_hedge = (m_wager * ms_m) / (1 + mh_m)
            m_profit = (m_wager * ms_m) - m_hedge
        else: # No-Sweat
            m_hedge = (m_wager * (ms_m + 1 - m_conv)) / (mh_m + 1 + m_conv)
            m_profit = (m_wager * ms_m) - (m_hedge + (m_wager * (1 - m_conv)))

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Hedge Amount", f"${m_hedge:.2f}")
        c2.metric("Net Profit", f"${m_profit:.2f}")
        c3.metric("ROI", f"{((m_profit/m_wager)*100):.1f}%")
    # --- MATH LOGIC ---
    ms_m = (m_s_price / 100) if m_s_price > 0 else (100 / abs(m_s_price))
    mh_m = (m_h_price / 100) if m_h_price > 0 else (100 / abs(m_h_price))

    if m_promo == "Profit Boost (%)":
        boost_f = 1 + (m_boost / 100)
        boosted_ms_m = ms_m * boost_f
        m_hedge = (m_wager * (1 + boosted_ms_m)) / (1 + mh_m)
        m_profit = (m_wager * boosted_ms_m) - m_hedge

    elif m_promo == "Bonus Bet (SNR)":
        m_hedge = (m_wager * ms_m) / (1 + mh_m)
        m_profit = (m_wager * ms_m) - m_hedge

    else: # No-Sweat Bet
        m_hedge = (m_wager * (ms_m + 1 - m_conv)) / (mh_m + 1 + m_conv)
        m_profit = (m_wager * ms_m) - (m_hedge + (m_wager * (1 - m_conv)))

    # --- DISPLAY RESULTS ---
    st.divider()
    res_c1, res_c2, res_c3 = st.columns(3)
    res_c1.metric("Hedge Amount", f"${m_hedge:.2f}")
    res_c2.metric("Net Profit", f"${m_profit:.2f}")
    
    m_rating = (m_profit / m_wager) * 100
    res_c3.metric("ROI / Conversion", f"{m_rating:.1f}%")

    if m_profit > 0:
        st.success(f"✅ Place **${m_hedge:.2f}** on the hedge side.")
    else:
        st.error("⚠️ Negative Profit: This line will lose money.")

# --- DATA & LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key! Please add ODDS_API_KEY to your Streamlit Secrets.")
    else:
        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab", "americanfootball_ncaaf"],
            "NBA": ["basketball_nba"], 
            "NFL": ["americanfootball_nfl"], 
            "NHL": ["icehockey_nhl"], 
            "NCAAB": ["basketball_ncaab"],
            "NCAAF": ["americanfootball_ncaaf"]
        }
        
        # Updated BOOK_LIST per your request (ESPN Bet included, others removed)
        BOOK_LIST = "draftkings,fanduel,caesars,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner(f"Intercepting {sport_cat} data..."):
            sports_to_scan = sport_map.get(sport_cat, [])
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{res.headers.get('x-requests-remaining', 'N/A')}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            # Parse UTC time
                            commence_time_utc = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if commence_time_utc <= now_utc: continue 
                            
                            # Convert to CST
                            cst_time = commence_time_utc - timedelta(hours=6)

                            source_odds, hedge_odds = [], []
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        if book['key'] == source_book: source_odds.append(entry)
                                        else: hedge_odds.append(entry)

                            for s in source_odds:
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                                best_h = max([h for h in hedge_odds if h['team'] == opp_team], key=lambda x: x['price'], default=None)
                                
                                if best_h:
                                    s_price, h_price = s['price'], best_h['price']

                                    # Multipliers (Profit per $1)
                                    s_mult = (s_price / 100) if s_price > 0 else (100 / abs(s_price))
                                    h_mult = (h_price / 100) if h_price > 0 else (100 / abs(h_price))

                                    if promo_type == "Profit Boost (%)":
                                        boost_factor = 1 + (boost_val / 100)
                                        boosted_s_mult = s_mult * boost_factor
                                        raw_hedge = (max_wager * (1 + boosted_s_mult)) / (1 + h_mult)
                                        hedge_needed = float(round(raw_hedge))
                                        
                                        p_source_wins = (max_wager * boosted_s_mult) - hedge_needed
                                        p_hedge_wins = (hedge_needed * h_mult) - max_wager
                                        profit = min(p_source_wins, p_hedge_wins)
                                        rating = profit

                                    elif promo_type == "Bonus Bet (SNR)":
                                        raw_hedge = (max_wager * s_mult) / (1 + h_mult)
                                        hedge_needed = float(round(raw_hedge))
                                        
                                        p_source_wins = (max_wager * s_mult) - hedge_needed
                                        p_hedge_wins = (hedge_needed * h_mult)
                                        profit = min(p_source_wins, p_hedge_wins)
                                        rating = (profit / max_wager) * 100

                                    else: # No-Sweat
                                        ref_conv = 0.70
                                        raw_hedge = (max_wager * (s_mult + 1 - ref_conv)) / (h_mult + 1 + ref_conv)
                                        hedge_needed = float(round(raw_hedge))
                                        
                                        p_source_wins = (max_wager * s_mult) - hedge_needed
                                        p_hedge_wins = (hedge_needed * h_mult) + (max_wager * ref_conv) - max_wager
                                        profit = min(p_source_wins, p_hedge_wins)
                                        rating = (profit / max_wager) * 100

                                    if profit > 0:
                                        all_opps.append({
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "start_cst": cst_time.strftime("%m/%d %I:%M %p"),
                                            "profit": profit, "hedge": hedge_needed, "rating": rating,
                                            "s_team": s['team'], "s_book": s['book'], "s_price": s_price,
                                            "h_team": best_h['team'], "h_book": best_h['book'], "h_price": h_price
                                        })
                except Exception as e:
                    continue

        st.markdown("### 🏆 Top Scanned Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)

        if not sorted_opps:
            st.warning("No high-value matches found currently.")
        else:
            for i, op in enumerate(sorted_opps[:10]):
                with st.expander(f"RANK {i+1} | {op['start_cst']} | +${op['profit']:.2f}"):
                    st.write(f"**{op['game']}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.caption("SOURCE BOOK")
                        st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                        st.caption(f"Book: {op['s_book']}")
                    with c2:
                        st.caption("STEALTH HEDGE (Rounded)")
                        st.success(f"Bet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                        st.caption(f"Book: {op['h_book']}")
                    with c3:
                        st.metric("Guaranteed Profit", f"${op['profit']:.2f}")
                        st.caption(f"Rating: {op['rating']:.1f}%")




