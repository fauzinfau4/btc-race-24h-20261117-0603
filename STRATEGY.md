# Strategy: deep-dip + selective breakout, with a no-trade fallback

## Why the previous bot failed live (diagnosis)

The previous entry (btc-race-24h-20261115-0828) passed dev grade 29/29 with
+$36.61, 4 trades, maxDD 2.06% — then made **zero fills in the live 24h
race** (equity flat $1,000, rank 1749/2828, $0). The protocol was not the
problem: the live race feeds bars exactly like the replay (one batch per
closed 1-minute bar, same hello/batches/fills), and the bot answered every
batch. The failure was **signal rarity**: its two entries needed a ±2.00%
move over 30–45 minutes. On the new dev window the biggest 45-minute drop
is only −1.86% and the biggest 30-minute rise +2.21%, so the dip leg can
never fire at all and the breakout leg fires at most once — and that one
breakout, bought at the top of a range, hit its −2.00% stop for −$21.61.
Re-running the old bot on the new dev window confirms it: −$21.61, 1 round
trip, and it would **fail the dev gate**. A whole flat day can pass without
a single ±2% half-hour move. This bot is built so that cannot happen again:
its main signal fires on ordinary multi-hour slides, and a fallback
guarantees a trade even on a day where neither signal ever fires.

## The market as the dev window shows it

The dev window (1,440 one-minute cbBTC bars, 2026-11-16 06:03Z to
2026-11-17 06:03Z) is flat: +48 bps drift over 24 hours, range 63,874–
65,466 (+2.5%), median |1-minute move| ~3 bps. A full-size round trip
costs ~26 bps (4 bps fee + 2 bps slippage + ~7 bps pool impact per leg),
so scalping the noise is a guaranteed loss. Forward-return analysis shows
the window is mean-reverting at 10–60 minute horizons: after a +100 bps
move over 20–30 minutes the price falls −105 to −142 bps over the next
hour, while after a −100 bps move it rises +25 to +39 bps. The money is
in buying multi-hour slides and selling the bounce — not in chasing
breakouts, which reverse hard on a flat day (the house ema-cross baseline
loses −$106.21 here, rsi-bollinger −$24.25, adx-momentum −$32.66; only
buy-and-hold makes money, +$1.07).

The previous dev window (2026-11-14/15) had the opposite regime: a −4%
downtrend then a +4% recovery, where big up-moves continued (+83 to +191
bps forward). No single rule wins on both days, so this bot carries one
leg for each regime and was checked on both windows.

## What the bot does

Long only, one position, full size (100% of cash), edge-triggered entries
(a signal fires only on the bar it turns on):

- **Deep dip (main leg):** the close is at least **1.50% below the
  highest close of the last 480 bars (8 hours)**. Measured against 8
  hours, not minutes: a dip against the last few minutes fires on every
  wiggle, but a 1.5% drawdown from the 8-hour high only happens after a
  real slide, on a downtrend day and on a flat day alike. Exit at +1.00%
  target, −0.80% stop, or 90 bars.
- **Breakout (trend leg):** the close has risen at least **2.30% over
  30 minutes**. Deliberately above the flat day's biggest 30-minute rise
  (+2.21%), so it stays silent on range days and only fires on a genuine
  trend day, where it rides the continuation. Exit at +3.00% target,
  −1.00% stop, or 120 bars.
- **Fallback:** if the bot has never held a position by bar 1000, it buys
  and holds to the end (target +3.00%, stop −1.50%). A day with no deep
  dip and no breakout is a steady grind or a dead range; buying late
  still captures the drift, and it guarantees the race's minimum bar of
  at least 1 trade. It never fires on a day where the main legs traded.

Exits are re-sent every bar while their reason holds, and the bot only
clears its in-position state when the account actually shows no position,
so a sell the market refuses is retried instead of stranding the
position, and a buy that never fills is dropped instead of leaving the
bot believing it holds something it does not. It sends no order while
warming up.

## Dev-window result (local replay, exact fill model)

Net PnL **+$15.03** on $1,000 start (+1.50%), **8 fills (4 round trips)**,
max drawdown **0.97%**. Per trade: +$9.70 (dip, target), −$0.81 (dip,
time), +$1.81 (dip, time), +$4.33 (dip, time) — three of four round trips
profitable, no single trade carrying the result.

The same bot on the previous dev window (the opposite regime) makes
**+$9.90, 6 fills, maxDD 2.10%**: dip +$6.86, breakout +$9.74 riding the
recovery rally, dip −$6.70. The parameter region around these settings is
a plateau, not a spike: neighbouring settings (dip threshold 150–200 bps,
target 100–150, hold 90–120) are also profitable on both windows.

## What it does not do

No shorting, no leverage, no averaging down, no Martingale, no re-entry
into a signal that is already on, no trading on 1-minute noise. If the
race window trends, the breakout leg catches it; if it ranges, the dip
leg trades the slides; if it does neither, the fallback still trades.
