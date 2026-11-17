"""Deep-dip / breakout bot for the make.fun BTC race (btc-race-24h-20261117-0603).

Long-only, one position, full size. It buys on one of two edge-triggered
signals, both measured on closes:

  * DEEP DIP: the close is at least 1.50% below the highest close of the
    last 480 bars (8 hours). A multi-hour slide that deep is where the
    bounces live: on the dev window the price recovers within ~90 minutes
    often enough to pay the ~26 bps round-trip cost several times over.
    The 8-hour lookback is the point: a dip measured against the last few
    minutes fires on every wiggle, but a dip against the last 8 hours
    only fires after a real slide, in a downtrend day and in a flat day
    alike.
  * BREAKOUT: the close has risen at least 2.30% over the last 30 minutes.
    Only a move this large is chased: on a flat day the biggest 30-minute
    rise is ~2.2%, so this leg stays silent there and cannot buy the top
    of a range the way a looser breakout does; on a trend day it catches
    the rally.

A signal fires only on the bar it turns on (edge-triggered). While a
signal stays on, the bot does not re-enter after an exit.

Exits (whichever comes first):
  * dip leg: +1.00% above the entry close, -0.80% below it, or 90 bars.
  * breakout leg: +3.00% above the entry close, -1.00% below it, or
    120 bars.

Fallback (the anti-zero-trades rule): if the bot has never held a
position by bar 1000, it buys and holds to the end of the window
(target +3.00%, stop -1.50%). A day with no deep dip and no breakout is
a steady grind or a dead range; buying late and holding still captures
the drift, and it guarantees the entry meets the race's minimum bar of
at least 1 trade. The fallback never fires on a day where the two main
legs already traded.

Safety against a rejected order: the bot only clears its in-position
state when the account actually shows no position, so a sell the market
refuses (e.g. max_slippage on a gap) is simply sent again on the next
bar while its exit reason still holds, and a buy that never fills is
dropped instead of leaving the bot believing it holds something it does
not. It never sends an order while warming up.

Everything is integer arithmetic on the closes the harness sent, no
floats, no randomness, no wall clock, no network, no files: two runs on
the same data produce byte-identical replies. Sizing is 100% of cash on
entry; the exit sells the whole position. max_slippage_bps is 150 on
every order, wide enough for the modelled slippage plus pool impact at
full size plus a normal open-vs-close gap, and tight enough to refuse a
fill that gapped far away from the close the decision was made on.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# --- dip leg: close this far below the 480-bar rolling high ---
DIP_WINDOW = 480        # bars of lookback for the rolling high
DIP_BPS = 150           # entry when the close is this far under that high
DIP_TARGET_BPS = 100    # sell when the close is this far above the entry close
DIP_STOP_BPS = 80       # sell when the close is this far below the entry close
DIP_MAX_HOLD = 90       # sell this many bars after entry at the latest

# --- breakout leg: close up this much over 30 minutes ---
MOM_WINDOW = 30         # bars of lookback for the breakout signal
MOM_BPS = 230           # entry when the close rose this much over MOM_WINDOW
MOM_TARGET_BPS = 300    # sell when the close is this far above the entry close
MOM_STOP_BPS = 100      # sell when the close is this far below the entry close
MOM_MAX_HOLD = 120      # sell this many bars after entry at the latest

# --- fallback: buy-and-hold if nothing has traded by this bar ---
FALLBACK_BAR = 1000
FALLBACK_TARGET_BPS = 300
FALLBACK_STOP_BPS = 150

MAX_SLIPPAGE_BPS = 150


class Bot:
    def __init__(self):
        self.closes = []          # closes seen so far, ints at price_scale 5
        self.in_position = False
        self.entry_close = 0      # close at the bar the position was decided on
        self.entry_bar = 0        # seq of the bar the position was decided on
        self.target_bps = 0       # exit target for the open position
        self.stop_bps = 0         # exit stop for the open position
        self.max_hold = 0         # exit hold for the open position
        self.prev_dip_on = False  # dip signal's state on the previous bar
        self.prev_mom_on = False  # breakout signal's state on the previous bar
        self.ever_held = False    # a position has been held at least once

    def _bps_change(self, now, then):
        """(now - then) / then in basis points (integer division)."""
        return (now - then) * 10000 // then

    def on_batch(self, state, batch):
        bar = state.latest.get(SYMBOL)
        if bar is not None:
            self.closes.append(int(bar["c"]))
        closes = self.closes
        seq = state.seq

        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            self.ever_held = True

        # Update the two signals' state on every bar, in or out of a
        # position, so an entry after an exit needs a fresh turn-on, never a
        # signal that was already on while the last trade was held.
        dip_on = mom_on = False
        fired_dip = fired_mom = False
        if len(closes) > DIP_WINDOW:
            high = closes[-DIP_WINDOW]
            for c in closes[-DIP_WINDOW + 1:]:
                if c > high:
                    high = c
            dip_on = self._bps_change(closes[-1], high) < -DIP_BPS
            fired_dip = dip_on and not self.prev_dip_on
            self.prev_dip_on = dip_on
        if len(closes) > MOM_WINDOW:
            mom_on = (
                self._bps_change(closes[-1], closes[-1 - MOM_WINDOW]) > MOM_BPS
            )
            fired_mom = mom_on and not self.prev_mom_on
            self.prev_mom_on = mom_on

        if self.in_position:
            # The buy decided on entry_bar fills at the next bar's open. If
            # the position still is not there a bar later, the buy was
            # rejected (e.g. max_slippage on a gap): drop the stale state
            # instead of sitting on a position that does not exist.
            if seq > self.entry_bar and (holding is None or holding.qty <= 0):
                self.in_position = False
            else:
                close = closes[-1] if closes else None
                if close is not None and holding is not None and holding.qty > 0:
                    gain_bps = self._bps_change(close, self.entry_close)
                    if (
                        gain_bps >= self.target_bps
                        or gain_bps <= -self.stop_bps
                        or seq - self.entry_bar >= self.max_hold
                    ):
                        # Do not clear in_position here: if this sell is
                        # refused, the next batch still shows the position
                        # and the sell is sent again while its reason holds.
                        # in_position clears when the position is gone.
                        return [
                            {
                                "side": "sell",
                                "symbol": SYMBOL,
                                "qty": holding.qty,
                                "max_slippage_bps": MAX_SLIPPAGE_BPS,
                            }
                        ]
                return []

        # The position is gone (or was never there): a sell that filled, or
        # a buy that never filled, ends the open trade.
        self.in_position = False

        if state.warming_up:
            return []

        fallback = not self.ever_held and seq >= FALLBACK_BAR
        if (fired_dip or fired_mom or fallback) and closes:
            amount = state.cash
            if amount >= 1_000_000:
                self.in_position = True
                self.entry_close = closes[-1]
                self.entry_bar = seq
                if fallback:
                    self.target_bps = FALLBACK_TARGET_BPS
                    self.stop_bps = FALLBACK_STOP_BPS
                    self.max_hold = 10 ** 9
                elif fired_dip:
                    self.target_bps = DIP_TARGET_BPS
                    self.stop_bps = DIP_STOP_BPS
                    self.max_hold = DIP_MAX_HOLD
                else:
                    self.target_bps = MOM_TARGET_BPS
                    self.stop_bps = MOM_STOP_BPS
                    self.max_hold = MOM_MAX_HOLD
                return [
                    {
                        "side": "buy",
                        "symbol": SYMBOL,
                        "notional_quote_units": amount,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                ]
        return []


def main():
    bot = Bot()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
