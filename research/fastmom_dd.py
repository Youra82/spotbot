import sys; sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from engine import load, stats
from spotbot.strategy.signal import btc_core_signal
from spotbot.analysis.backtest import simulate
from fastmom import rep
d = load('1d'); c = d['close']; b = c['BTC']
def fast_core(b):
    hi = b.rolling(20).max().shift(1); lo = b.rolling(10).min().shift(1)
    dc = pd.Series(np.nan, index=b.index); dc[b > hi] = 1.0; dc[b < lo] = 0.0
    sig = [b.ewm(span=10).mean() > b.ewm(span=30).mean(), b > b.rolling(20).mean(), b > b.rolling(50).mean(), dc.ffill().fillna(0) > 0]
    return pd.concat(sig, axis=1).astype(float).mean(1)
cores = {'normal': btc_core_signal(b), 'schnell': fast_core(b), 'streng': (btc_core_signal(b) == 1).astype(float)}
R = c.pct_change(fill_method=None).fillna(0)
def port_vol_scale(w, target, win=30):
    # realisierte Vola des Portfolios mit heutigen Gewichten ueber die letzten `win` Tage (nur Vergangenheit)
    pr = (w.shift(1) * R).sum(1)  # vergangene Portfolio-Rendite (Naeherung)
    v = pr.rolling(win).std() * np.sqrt(365)
    return np.minimum(1.0, target / v).fillna(1.0)
for vt in (1.5, 10.0):
    w = pd.read_pickle(f'fast_tw_{vt}.pkl'); s = w.sum(1)
    for cn, core in cores.items():
        ww = w.copy(); ww['BTC'] += (1 - s).clip(lower=0) * core
        rep(f'vt{vt} Fueller {cn}', ww, d)
        for pvt in (0.6, 0.8):
            k = port_vol_scale(ww, pvt)
            rep(f'   + Portfolio-Vol {pvt}', ww.mul(k, axis=0), d)
