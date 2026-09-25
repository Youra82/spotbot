# src/spotbot/strategy/signal.py
"""Tranchen-Ensemble-Momentum-Rotation (long-only Spot).

EINE Funktion fuer Live UND Backtest (target_weights). Ablauf je Ensemble-Mitglied:
  - Regime: BTC Close > SMA(btc_sma) UND Breadth (Anteil liquider Coins ueber eigener SMA)
    >= breadth_min, sonst alles in USDT.
  - Kandidaten: Coin unter den `liq_top` liquidesten (30T-Quote-Volumen), Close > SMA(coin_sma),
    Momentum(mom) > 0.
  - An Umschichttagen: Top-K nach Momentum, invers-vola-gewichtet, Portfolio-Vola auf
    vol_target skaliert (max 100%, kein Hebel).
  - Zwischen Umschichttagen: nur Ausstiege (Coin faellt aus Kandidaten, Regime aus).
Ensemble = Mittel ueber alle Parameter-Mitglieder UND alle Umschicht-Phasen (Tranchen).
Die Phase ist am Kalendertag verankert, damit ein kurzes Live-Datenfenster exakt dieselben
Umschichttage trifft wie der lange Backtest.
Signal mit Daten bis Close[t], Ausfuehrung zum naechsten Open (kein Lookahead)."""
import itertools

import numpy as np
import pandas as pd

ENSEMBLE_GRID = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5, 8],
                     rebal=[7, 14], liq_top=[10, 15, 20], breadth_min=[0.3, 0.5])
N_PHASES = 14  # kgV der rebal-Werte
VOL_WIN = 30
LIQ_WIN = 30
# Laengster Indikator (SMA100) + Zustand seit letztem Umschichttag (max 14) + Puffer
MIN_HISTORY_DAYS = 160


class Prep:
    """Vorberechnete Indikatoren (Index = Tagesdatum UTC, Spalten = Coins)."""

    def __init__(self, close: pd.DataFrame, qvol: pd.DataFrame, btc: str = 'BTC'):
        self.cols = list(close.columns)
        self.idx = close.index
        self.C = close.values
        rets = close.pct_change(fill_method=None)
        self.R = rets.values
        self.vol = (rets.rolling(VOL_WIN, min_periods=VOL_WIN).std() * np.sqrt(365)).values
        liq = qvol.rolling(LIQ_WIN, min_periods=LIQ_WIN).mean()
        self.liq_rank = liq.rank(axis=1, ascending=False).values
        ix = close.index
        if ix.tz is not None:
            ix = ix.tz_convert('UTC').tz_localize(None)
        self.day = np.asarray((ix.normalize() - pd.Timestamp('1970-01-01')).days)
        self.btc = self.cols.index(btc)
        self._close = close
        self._sma, self._mom = {}, {}

    def sma(self, n):
        if n not in self._sma:
            self._sma[n] = self._close.rolling(n, min_periods=n).mean().values
        return self._sma[n]

    def mom(self, n):
        if n not in self._mom:
            self._mom[n] = (self._close / self._close.shift(n) - 1).values
        return self._mom[n]


def rotation(P: Prep, btc_sma, coin_sma, mom, top_k, rebal, liq_top, breadth_min, vol_target,
             phase=0) -> np.ndarray:
    C, R = P.C, P.R
    S = P.sma(coin_sma); M = P.mom(mom); B = P.sma(btc_sma)
    with np.errstate(invalid='ignore'):
        above = C > S
        elig = above & (M > 0) & (P.liq_rank <= liq_top) & ~np.isnan(P.vol)
    inliq = (P.liq_rank <= liq_top) & ~np.isnan(S)
    breadth = (above & inliq).sum(1) / np.maximum(inliq.sum(1), 1)
    n, m = C.shape
    W = np.zeros((n, m)); cur = np.zeros(m)
    for i in range(n):
        b = B[i, P.btc]
        reg = (not np.isnan(b)) and C[i, P.btc] > b and breadth[i] >= breadth_min
        if not reg:
            cur = np.zeros(m)
        elif (P.day[i] + phase) % rebal == 0:
            mm = np.where(elig[i], M[i], -np.inf)
            idx = [j for j in np.argsort(-mm)[:top_k] if np.isfinite(mm[j])]
            cur = np.zeros(m)
            if idx:
                ww = 1 / P.vol[i, idx]
                ww = ww / ww.sum()
                sub = np.nan_to_num(R[max(0, i - VOL_WIN + 1):i + 1][:, idx])
                pv = np.sqrt(ww @ (np.atleast_2d(np.cov(sub.T)) * 365) @ ww)
                if pv > 0:
                    ww = ww * min(1.0, vol_target / pv)
                cur[idx] = ww
        else:
            cur = np.where(elig[i], cur, 0.0)
        W[i] = cur
    return W


def members(grid=ENSEMBLE_GRID):
    keys = list(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*grid.values())]


def btc_core_signal(btc_close: pd.Series) -> pd.Series:
    """BTC-Trend-Ensemble 0..1 = Anteil positiver Filter (EMA10/30, EMA20/50, SMA50, SMA100,
    Donchian 20/10). EMA/Donchian haben langes Gedaechtnis -> live >= CORE_HISTORY_DAYS laden."""
    b = btc_close
    sigs = [b.ewm(span=10).mean() > b.ewm(span=30).mean(),
            b.ewm(span=20).mean() > b.ewm(span=50).mean(),
            b > b.rolling(50).mean(),
            b > b.rolling(100).mean()]
    hi = b.rolling(20).max().shift(1)
    lo = b.rolling(10).min().shift(1)
    dc = pd.Series(np.nan, index=b.index)
    dc[b > hi] = 1.0
    dc[b < lo] = 0.0
    sigs.append(dc.ffill().fillna(0) > 0)
    return pd.concat(sigs, axis=1).astype(float).mean(axis=1)


CORE_HISTORY_DAYS = 400


def core_satellite_weights(close: pd.DataFrame, qvol: pd.DataFrame, core_share: float,
                           sat_vol_target: float, grid=ENSEMBLE_GRID, btc: str = 'BTC') -> pd.DataFrame:
    """core_share im BTC-Trend-Kern + (1-core_share) in der Tranchen-Ensemble-Rotation."""
    w = target_weights(close, qvol, sat_vol_target, grid=grid, btc=btc) * (1 - core_share)
    w[btc] = w[btc] + core_share * btc_core_signal(close[btc])
    return w.div(np.maximum(w.sum(axis=1), 1.0), axis=0)


# V3 "Fast Momentum": kurze Lookbacks, konzentriert auf die liquidesten Coins, woechentlich
FAST_GRID = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[7, 10, 14, 21], top_k=[1, 2, 3], rebal=[7],
                 liq_top=[5, 8, 10], breadth_min=[0.0, 0.3])


def fast_momentum_weights(close: pd.DataFrame, qvol: pd.DataFrame, vol_target: float = 1.5,
                          slow_sma: int = 150, slow_floor: float = 0.5, grid=FAST_GRID,
                          btc: str = 'BTC') -> pd.DataFrame:
    """V3: Fast-Momentum-Ensemble; ungenutztes Kapital -> BTC, wenn ALLE BTC-Trendfilter positiv;
    BTC unter SMA(slow_sma) -> gesamte Exposure auf slow_floor (gegen Baermarkt-Rallyes)."""
    w = target_weights(close, qvol, vol_target, grid=grid, btc=btc)
    b = close[btc]
    strict = (btc_core_signal(b) == 1).astype(float)
    w[btc] = w[btc] + (1 - w.sum(axis=1)).clip(lower=0) * strict
    gate = np.where(b > b.rolling(slow_sma).mean(), 1.0, slow_floor)
    return w.mul(gate, axis=0)


def target_weights(close: pd.DataFrame, qvol: pd.DataFrame, vol_target: float,
                   grid=ENSEMBLE_GRID, btc: str = 'BTC') -> pd.DataFrame:
    """Zielgewichte je Tag (Zeile t = Ziel nach Close t). Summe <= 1, Rest = USDT."""
    P = Prep(close, qvol, btc)
    ms = members(grid)
    acc = np.zeros(close.shape)
    for mem in ms:
        # Alle N_PHASES Tranchen; bei rebal=7 sind Phase p und p+7 identisch -> einmal rechnen, doppelt zaehlen
        for ph in range(mem['rebal']):
            acc += rotation(P, vol_target=vol_target, phase=ph, **mem) * (N_PHASES // mem['rebal'])
    acc /= len(ms) * N_PHASES
    return pd.DataFrame(acc, index=close.index, columns=close.columns)
