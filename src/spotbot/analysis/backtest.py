# src/spotbot/analysis/backtest.py
"""Backtest mit identischer Signal- (signal.target_weights) und Umschichtlogik
(portfolio.plan_trades) wie live. Ziel aus Close[t] -> Ausfuehrung zum Open[t+1],
Gebuehr+Slippage `cost` je Seite. Equity[t] = Bewertung zum Open[t+2]."""
import numpy as np
import pandas as pd

from spotbot.strategy.portfolio import plan_trades


def simulate(target: pd.DataFrame, open_: pd.DataFrame, cost: float = 0.002, band: float = 0.0,
             min_trade_usdt: float = 0.0, start_equity: float = 1000.0) -> pd.Series:
    o = open_.reindex(index=target.index, columns=target.columns)
    W = target.fillna(0.0).values
    O1 = o.shift(-1).values  # Ausfuehrungskurs
    O2 = o.shift(-2).values  # Bewertungskurs
    n, m = W.shape
    qty = np.zeros(m)
    last_px = np.zeros(m)
    cash = float(start_equity)
    eq = np.full(n, np.nan)
    for t in range(n - 1):
        px = O1[t]
        valid = ~np.isnan(px)
        # Coin nicht mehr handelbar (Delisting/Datenende) -> zum letzten Kurs verkaufen
        gone = ~valid & (qty > 0)
        if gone.any():
            cash += float((qty[gone] * last_px[gone]).sum()) * (1 - cost)
            qty[gone] = 0.0
        pxs = np.where(valid, px, 1.0)
        last_px = np.where(valid, px, last_px)
        hold = np.where(valid, qty * pxs, 0.0)
        equity = cash + hold.sum()
        delta = plan_trades(np.where(valid, W[t], 0.0), hold, equity, band, min_trade_usdt)
        delta = np.where(valid, delta, 0.0)
        sells = np.minimum(delta, 0.0)
        # Verkauf: nie mehr als Bestand
        sell_qty = np.minimum(-sells / pxs, qty)
        qty -= sell_qty
        cash += float((sell_qty * pxs).sum()) * (1 - cost)
        buys = np.maximum(delta, 0.0)
        spend = buys.sum() * (1 + cost)
        if spend > cash > 0:
            buys *= cash / spend
            spend = cash
        elif cash <= 0:
            buys[:] = 0.0; spend = 0.0
        cash -= spend
        qty += buys / pxs
        nxt = np.where(np.isnan(O2[t]), last_px, O2[t])
        eq[t] = cash + float((qty * nxt).sum())
    return pd.Series(eq, index=target.index).ffill()
