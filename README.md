[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/fauzinfau4/btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/fauzinfau4/btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

# BTC race bot — deep-dip + selective breakout

Entry for **btc-race-24h-20261117-0603** ("Race a BTC trading bot live for
24 hours", make.fun). Long-only cbBTC bot, Python 3.13, standard library
only plus the vendored `makefun_bars.py` SDK shim (byte-identical copy of
the kit's `sdk/makefun_bars.py`).

## How it trades

- **Deep dip:** buy when the close is ≥1.50% below the highest close of
  the last 480 bars (8h); exit at +1.00% / −0.80% / 90 bars.
- **Breakout:** buy when the close rises ≥2.30% over 30 minutes; exit at
  +3.00% / −1.00% / 120 bars.
- **Fallback:** if it has never held a position by bar 1000, buy and hold
  to the end — so it can never repeat the previous entry's live-race
  failure of zero fills.
- Full size (100% of cash), one position, max slippage 150 bps, integer
  arithmetic only — two runs on the same data produce byte-identical
  orders.

See [STRATEGY.md](STRATEGY.md) for the full reasoning, the diagnosis of
the previous bot's 0-fill live race, and the per-trade results.

## Dev-window result (kit `grade-local`, official harness)

| Window | Net PnL | Trades | Max drawdown |
|---|---|---|---|
| Dev 2026-11-16/17 (this competition) | **+$15.03** | 8 | 0.97% |
| Previous dev window 2026-11-14/15 | +$9.90 | 6 | 2.10% |

Dev gate is net PnL > $0 — this bot clears it with margin on both
regimes, with 4 round trips on the dev window instead of the previous
bot's 2.

## Files

- `main.py` — the bot (entrypoint)
- `vendor/makefun_bars.py` — kit SDK shim, byte-identical copy
- `STRATEGY.md` — strategy write-up and diagnosis
- `LICENSE` — MIT
