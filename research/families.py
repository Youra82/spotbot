"""Strategie-Familien jenseits Trend-Rotation (Forschung).
Alle liefern Zielgewichte (Zeile t = Ziel nach Close t, Ausfuehrung Open t+1).
Positionslogik je Coin: Zustandsmaschine Einstieg E / Ausstieg X, Gewicht = 1/slots je Position
(bei mehr Positionen als Slots: gleichmaessig verduennt, keine Auswahl -> keine Rangfolge-Overfits)."""
import numpy as np
import pandas as pd


def liq_mask(d, liq_top):
    liq = d['qvol'].rolling(30, min_periods=30).mean()
    return (liq.rank(axis=1, ascending=False) <= liq_top).values


def state_machine(E, X, max_hold=None):
    n, m = E.shape
    P = np.zeros((n, m), dtype=bool)
    held = np.zeros(m, dtype=bool); age = np.zeros(m, dtype=int)
    for i in range(n):
        age = np.where(held, age + 1, 0)
        ex = held & (X[i] | ((age >= max_hold) if max_hold else False))
        held = held & ~ex
        en = ~held & E[i]
        held = held | en
        age = np.where(en, 0, age)
        P[i] = held
    return P


def to_weights(P, d, slots):
    cnt = P.sum(1, keepdims=True)
    W = P / np.maximum(cnt, slots)
    return pd.DataFrame(W, index=d['close'].index, columns=d['close'].columns)


def rsi(c, n):
    diff = c.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def btc_regime(d, n):
    b = d['close']['BTC']
    return (b > b.rolling(n).mean()).values


# --- A: Mean-Reversion -------------------------------------------------------
def mean_reversion(d, kind='rsi', n=2, thr=10, exit_sma=5, max_hold=10, liq_top=20, slots=5,
                   trend_filter=200, regime=0):
    c = d['close']
    L = liq_mask(d, liq_top)
    if kind == 'rsi':
        sig = (rsi(c, n) < thr).values
    elif kind == 'bb':  # Close unter unterem Bollinger-Band (n Tage, thr/10 Sigma)
        m = c.rolling(n).mean(); s = c.rolling(n).std()
        sig = (c < m - thr / 10 * s).values
    elif kind == 'ret':  # n-Tage-Rendite < -thr%
        sig = (c / c.shift(n) - 1 < -thr / 100).values
    E = sig & L
    if trend_filter:
        E &= (c > c.rolling(trend_filter).mean()).values
    if regime:
        E &= btc_regime(d, regime)[:, None]
    X = (c > c.rolling(exit_sma).mean()).values
    return to_weights(state_machine(E, X, max_hold), d, slots)


# --- C: Donchian-Breakout / Turtle --------------------------------------------
def breakout(d, n_in=20, atr_mult=3.0, liq_top=20, slots=5, regime=0):
    c, h, l = d['close'], d['high'], d['low']
    L = liq_mask(d, liq_top)
    E = (c > h.rolling(n_in).max().shift(1)).values & L
    if regime:
        E &= btc_regime(d, regime)[:, None]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()]).groupby(level=0).max()
    atr = tr.rolling(20).mean().values
    C = c.values
    n, m = C.shape
    P = np.zeros((n, m), dtype=bool); held = np.zeros(m, dtype=bool); peak = np.zeros(m)
    for i in range(n):
        peak = np.where(held, np.fmax(peak, C[i]), 0)
        stop = held & (C[i] < peak - atr_mult * np.nan_to_num(atr[i]))
        held &= ~stop
        en = ~held & E[i]
        held |= en
        peak = np.where(en, C[i], peak)
        P[i] = held
    return to_weights(P, d, slots)


# --- D: Volatilitaets-Breakout (1 Tag halten) --------------------------------
def vol_breakout(d, k=0.5, liq_top=10, slots=5, regime=0):
    """Signal: heutiger Close > heutiger Open + k * gestrige Range -> morgen halten (1 Tag)."""
    c, o, h, l = d['close'], d['open'], d['high'], d['low']
    L = liq_mask(d, liq_top)
    E = (c > o + k * (h - l).shift(1)).values & L
    if regime:
        E &= btc_regime(d, regime)[:, None]
    return to_weights(E, d, slots)


# --- B: Dip-Kauf im Bullenmarkt ----------------------------------------------
def dip_buy(d, drop=15, lookback=5, hold=5, liq_top=20, slots=5, regime=50, trend=100):
    c = d['close']
    L = liq_mask(d, liq_top)
    E = (c / c.rolling(lookback).max() - 1 < -drop / 100).values & L
    E &= (c.shift(lookback) > c.rolling(trend).mean().shift(lookback)).values  # vor dem Dip im Trend
    if regime:
        E &= btc_regime(d, regime)[:, None]
    X = np.zeros_like(E)
    return to_weights(state_machine(E, X, hold), d, slots)


# --- E: Wochentag ------------------------------------------------------------
def weekday(d, days=(0, 4, 5), sym='BTC', regime=0):
    """Halte `sym` an den Tagen `days` (Rendite des Tages t+1 Open->t+2 Open wird dem Signaltag t
    zugeordnet -> wir setzen Gewicht an Tag t, wenn t+1 ein gewuenschter Wochentag ist)."""
    c = d['close']
    nxt = (c.index + pd.Timedelta(days=1)).dayofweek
    on = np.isin(nxt, days)
    if regime:
        on &= btc_regime(d, regime)
    W = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    W[sym] = on.astype(float)
    return W


# --- G: BTC/ETH relative Staerke ---------------------------------------------
def btc_eth_switch(d, n=30, regime=50):
    c = d['close']
    ratio = c['ETH'] / c['BTC']
    eth_strong = (ratio > ratio.rolling(n).mean()).values
    reg = btc_regime(d, regime) if regime else np.ones(len(c), bool)
    W = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    W['ETH'] = (reg & eth_strong).astype(float)
    W['BTC'] = (reg & ~eth_strong).astype(float)
    return W
