# Promo Converter

A Streamlit app for converting sportsbook promotions into guaranteed profit through hedged arbitrage. Pulls live odds via the Odds API and calculates optimal stake splits across three engines.

---

## Engines

### Main Boost Engine
General-purpose converter for single-book promotions. Supports Profit Boost, Bonus Bet, and No-Sweat Bet promo types across 2-way and 3-way markets.

- Select a source book and promo type
- Enter your wager and boost percentage (if applicable)
- Optionally filter hedge books and sports
- Results ranked by profit, top 15 shown

### 3-Way Soccer Engine
Advanced converter for FIFA World Cup 3-way markets (Home / Away / Draw), with per-leg promo configuration across up to three different books.

- Each leg has its own book selection, promo type, boost %, stake, and promo cap
- Legs 2 and 3 support multi-book selection — the engine scans all permutations
- Arb-splitting logic automatically handles promo cap overflows with cash top-ups
- Look-ahead window: 3 days from today

### Bet and Get Engine
Finds the cheapest hedging path to qualify for a Bet & Get promotion with minimum loss.

- Enter the required qualifying stake and the returned bonus value
- Engine calculates the hedge stake needed to lock in the bonus at minimum cost
- Results sorted by lowest qualifying loss (best path first)
- Net value estimate based on 70% bonus conversion rate

---

## Supported Books

| Display Name     | API Key      |
|------------------|--------------|
| DraftKings       | draftkings   |
| FanDuel          | fanduel      |
| theScore / ESPN  | espnbet      |
| BetMGM           | betmgm       |

---

## Supported Sports

| Display Name    | API Key                  |
|-----------------|--------------------------|
| WNBA            | basketball_wnba          |
| MLB             | baseball_mlb             |
| FIFA World Cup  | soccer_fifa_world_cup    |

---

## Promo Types

| Type           | How it works                                                                 |
|----------------|------------------------------------------------------------------------------|
| Straight Cash  | Standard bet — no promo applied                                              |
| Profit Boost   | Odds multiplier increased by boost % — only the profit portion is boosted    |
| Bonus Bet      | Stake is not returned on win — only net profit paid out                      |
| No-Sweat Bet   | ~65% of stake refunded as a bonus if the bet loses                           |

---

## Setup

### Requirements

```
streamlit
requests
```

Install with:

```bash
pip install streamlit requests
```

### Odds API Key

This app requires an API key from [the-odds-api.com](https://the-odds-api.com). Add it to your Streamlit secrets:

```toml
# .streamlit/secrets.toml
ODDS_API_KEY = "your_key_here"
```

Odds are cached for 5 minutes (`ttl=300`) to preserve API quota. Remaining quota is displayed in the top-right corner of the app.

### Running Locally

```bash
streamlit run app.py
```

### Deploying to Streamlit Cloud

1. Push `app.py` to a GitHub repository
2. Connect the repo in [Streamlit Cloud](https://streamlit.io/cloud)
3. Add `ODDS_API_KEY` under App Settings → Secrets

---

## Notes

- All times displayed in CT (UTC−6)
- Odds API results are filtered to today and the next 2 days
- Results with profit greater than −$10 are surfaced (near-arb opportunities included)
- The 70% bonus conversion rate in the Bet & Get engine is an estimate — adjust expectations based on the specific book and promo terms
