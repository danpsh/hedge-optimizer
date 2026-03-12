🎯 Arb Terminal: Promo Converter
A professional-grade, real-time betting terminal built with Streamlit. This tool automates the process of "matched betting" by scanning live markets via The Odds API to convert sportsbook promotions—Bonus Bets, Profit Boosts, and No-Sweat Bets—into guaranteed cash.

🚀 Key Features
Live Market Scanner: Integrated with The Odds API to fetch real-time American odds across major US books (DraftKings, FanDuel, BetMGM, ESPN Bet, etc.).

Multi-Strategy Logic:

Profit Booster: Optimized for boosted net winnings.

Bonus Bet (SNR): High-precision conversion for "Stake Not Returned" credits.

No-Sweat Optimizer: Advanced math factoring in a 70% retention value on potential bonus bet refunds.

Smart Filtering: Filter by sport (NBA, NHL, MMA, etc.) and specific "Hedge Books" to find the tightest lines.

Visual Ranker: Opportunities are ranked by ROI and color-coded (🟢/🔴) based on hedge efficiency.

Manual Calculator: A built-in sandbox to calculate hedges for markets not covered by the API.

🛠️ Technical Stack
Frontend: Streamlit (Custom CSS for "Light Tech" terminal aesthetics).

Backend: Python 3.x / Requests.

API: The Odds API (v4).

Math: Native American-to-Decimal conversion and weighted hedging algorithms.

---
*Disclaimer: This tool is for educational and informational purposes only. Please gamble responsibly.*
