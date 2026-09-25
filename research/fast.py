"""Schnelle numpy-Variante der Rotation + Grid-Hilfen."""
import numpy as np
import pandas as pd

class Prep:
    def __init__(self, d, vol_win=30):
        self.d = d
        c = d['close']; self.cols = list(c.columns); self.idx = c.index
        self.C = c.values
        self.R = c.pct_change(fill_method=None).values
        self.vol = (c.pct_change(fill_method=None).rolling(vol_win, min_periods=vol_win).std() * np.sqrt(365)).values
        liq = d['qvol'].rolling(30, min_periods=30).mean()
        self.liq_rank = liq.rank(axis=1, ascending=False).values
        self.vol_win = vol_win
        self._sma, self._mom = {}, {}
        self.btc = self.cols.index('BTC')
    def sma(self, n):
        if n not in self._sma:
            self._sma[n] = self.d['close'].rolling(n, min_periods=n).mean().values
        return self._sma[n]
    def mom(self, n):
        if n not in self._mom:
            c = self.d['close']; self._mom[n] = (c / c.shift(n) - 1).values
        return self._mom[n]


def rotation(P, btc_sma=50, coin_sma=50, mom=30, top_k=3, rebal=7, vol_target=None,
             liq_top=20, breadth_min=0.0, trail=None, min_mom=0.0, cash_slots=True, vol_long=0, phase=0):
    C, R = P.C, P.R
    S = P.sma(coin_sma); M = P.mom(mom)
    above = C > S
    elig = above & (M > min_mom) & (P.liq_rank <= liq_top) & ~np.isnan(P.vol)
    B = P.sma(btc_sma) if btc_sma else None
    # Breadth: Anteil der top-liq Coins ueber ihrer SMA
    inliq = (P.liq_rank <= liq_top) & ~np.isnan(S)
    breadth = np.where(inliq.sum(1) > 0, (above & inliq).sum(1) / np.maximum(inliq.sum(1), 1), 0)
    n, m = C.shape
    W = np.zeros((n, m)); cur = np.zeros(m); peak = np.zeros(m)
    for i in range(n):
        reg = True
        if B is not None:
            reg = C[i, P.btc] > B[i, P.btc] if not np.isnan(B[i, P.btc]) else False
        reg = reg and breadth[i] >= breadth_min
        if not reg:
            cur = np.zeros(m); peak[:] = 0
        else:
            if trail is not None:
                held = cur > 0
                peak = np.where(held, np.fmax(peak, C[i]), 0)
                stop = held & (C[i] < peak * (1 - trail))
                cur = np.where(stop, 0, cur)
            if (i + phase) % rebal == 0:
                mm = np.where(elig[i], M[i], -np.inf)
                order = np.argsort(-mm)[:top_k]
                idx = [j for j in order if np.isfinite(mm[j])]
                new = np.zeros(m)
                if idx:
                    ww = 1 / P.vol[i, idx]; ww = ww / ww.sum()
                    if cash_slots:  # weniger Kandidaten als K -> Rest bleibt Cash
                        ww = ww * len(idx) / top_k
                    if vol_target:
                        sub = np.nan_to_num(R[max(0, i - P.vol_win + 1):i + 1][:, idx])
                        cov = np.atleast_2d(np.cov(sub.T)) * 365
                        pv = np.sqrt(ww @ cov @ ww)
                        if vol_long:  # konservativ: max(kurze, lange) Portfolio-Vola
                            sub2 = np.nan_to_num(R[max(0, i - vol_long + 1):i + 1][:, idx])
                            pv = max(pv, np.sqrt(ww @ (np.atleast_2d(np.cov(sub2.T)) * 365) @ ww))
                        if pv > 0: ww = ww * min(1.0, vol_target / pv) if ww.sum() * 0 == 0 else ww
                    new[idx] = ww
                # neue Positionen: Peak initialisieren
                peak = np.where((new > 0) & (cur == 0), C[i], np.where(new > 0, peak, 0))
                cur = new
            else:
                cur = np.where(elig[i] | (cur == 0), cur, 0)
                cur = np.where(above[i], cur, 0)
        W[i] = cur
    return pd.DataFrame(W, index=P.idx, columns=P.cols)


def tsmom(P, lookbacks=(20, 60, 120), liq_top=15, asset_vol=0.5, max_w=0.3, gross=1.0,
          btc_sma=0, band=0.25, rebal=1, sig_mode='frac'):
    """Time-Series-Momentum: pro Coin Signal = Anteil positiver Lookback-Renditen
    (frac) bzw. alle positiv (all). Gewicht = Signal * asset_vol/vol / liq_top, gedeckelt.
    Band: nur umschichten, wenn relative Aenderung > band oder Signal an/aus."""
    C = P.C; n, m = C.shape
    sig = np.zeros((n, m))
    for lb in lookbacks:
        sig += np.nan_to_num(P.mom(lb) > 0)
    sig /= len(lookbacks)
    if sig_mode == 'all':
        sig = (sig == 1).astype(float)
    ok = (P.liq_rank <= liq_top) & ~np.isnan(P.vol) & ~np.isnan(P.mom(max(lookbacks)))
    raw = np.where(ok, sig * asset_vol / np.where(P.vol > 0, P.vol, np.inf) / liq_top * 1.0, 0)
    raw = np.minimum(raw, max_w)
    B = P.sma(btc_sma) if btc_sma else None
    W = np.zeros((n, m)); cur = np.zeros(m)
    for i in range(n):
        tgt = raw[i].copy()
        if B is not None and not (C[i, P.btc] > B[i, P.btc]):
            tgt[:] = 0
        s = tgt.sum()
        if s > gross: tgt *= gross / s
        if i % rebal == 0 or ((tgt == 0) & (cur > 0)).any():
            chg = (np.abs(tgt - cur) > band * np.maximum(cur, 1e-12)) | ((tgt == 0) != (cur == 0))
            cur = np.where(chg, tgt, cur)
            s = cur.sum()
            if s > 1.0: cur = cur / s
        W[i] = cur
    return pd.DataFrame(W, index=P.idx, columns=P.cols)


ENSEMBLE_GRID = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5, 8],
                     rebal=[7, 14], liq_top=[10, 15, 20], breadth_min=[0.3, 0.5])


def members(grid=ENSEMBLE_GRID):
    import itertools
    keys = list(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*grid.values())]


def ensemble(P, vol_target=0.5, grid=ENSEMBLE_GRID, cash_slots=True, phase=0):
    """Mittelwert der Zielgewichte aller Ensemble-Mitglieder = ein Portfolio."""
    ms = members(grid)
    W = None
    for m in ms:
        w = rotation(P, vol_target=vol_target, cash_slots=cash_slots, phase=phase, **m).values
        W = w if W is None else W + w
    return pd.DataFrame(W / len(ms), index=P.idx, columns=P.cols)
