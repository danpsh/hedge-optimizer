This is a comprehensive README.md tailored to your Streamlit application. It highlights the professional UI, the specific betting strategies implemented in your code, and the technical setup required.

---

# 🎯 Promo Converter

A professional-grade sports betting arbitrage and promotion conversion tool built with **Streamlit**. This application helps bettors maximize the value of sportsbook promotions (Profit Boosts, Bonus Bets, and No-Sweat Bets) by identifying optimal hedge opportunities using real-time market data.

## ✨ Features

* **Real-Time Odds Integration:** Fetches live data via [The Odds API](https://the-odds-api.com/).
* **Three Core Strategies:**
    * **Profit Boost (%):** Calculates the best way to lock in profit using a percentage-based boost on a source book.
    * **Bonus Bet:** Maximizes the conversion rate of "non-stake returned" bonus credits.
    * **No-Sweat Bet:** Optimizes "risk-free" bets, accounting for the typical **65% conversion rate** of returned bonus bets.
* **Multi-Book Scanning:** Support for DraftKings, FanDuel, BetMGM, and ESPN Bet.
* **Smart Filtering:** Automatically filters for upcoming events (8-day lookahead) and excludes games that have already started.
* **Dynamic Queue System:** Add multiple promos to a queue to run batch scans across different sports and books simultaneously.
* **Professional UI:** Custom CSS styling with "Inter" typography, dark-mode elements, and responsive layouts.

---

## 🚀 Getting Started

### 1. Prerequisites
* Python 3.8+
* An API Key from [The Odds API](https://the-odds-api.com/) (Free tier available).

### 2. Installation
Clone the repository and install the required dependencies:
```bash
pip install streamlit requests
```

### 3. Configuration
The app uses `st.secrets` to manage the API key securely. Create a directory and file at `.streamlit/secrets.toml` in your project root:

```toml
# .streamlit/secrets.toml
ODDS_API_KEY = "your_api_key_here"
```

### 4. Running the App
```bash
streamlit run app.py
```

---

## 🛠 How It Works

### The Math
The converter uses American odds conversion to calculate multipliers ($m$):
* **For Positive Odds (+):** $m = \text{odds} / 100$
* **For Negative Odds (-):** $m = 100 / |\text{odds}|$

It then calculates the optimal hedge wager ($h$) to ensure equal profit (or minimal loss) regardless of the game outcome, depending on the selected strategy.

### Supported Sports
* 🏀 NBA & NCAA (Men's/Women's)
* 🏒 NHL
* ⚾ MLB
* 🥊 UFC/MMA

---

## 🖥 User Interface Guide

1.  **Promo Configuration:** Input your source book, the type of promo, and your wager amount.
2.  **Hedge Books:** Select which books you have funds in to use as the "counter" bet. Leave blank to scan all available books.
3.  **Scan Queue:** Use "Add to Queue" to build a list of multiple promos you need to hedge, then "Run All" to see a consolidated report.
4.  **Results:**
    * **Ranked Matches:** The app sorts matches by highest guaranteed profit.
    * **Precision Options:** Provides both a **.25 centered** hedge (for betting shops that limit to quarters) and a **Flat** hedge (whole dollars).

---

## ⚠️ Disclaimer
*This tool is for informational purposes only. Sports betting involves risk. Always double-check live odds on the respective sportsbooks before placing wagers, as API data can have a slight delay.*
