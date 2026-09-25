import sys; sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from engine import load, stats
from spotbot.strategy.signal import btc_core_signal
from fastmom import rep
d = load('1d'); b = d['close']['BTC']
strict = (btc_core_signal(b) == 1).astype(float)
for vt in (1.5, 10.0):
    w = pd.read_pickle(f'fast_tw_{vt}.pkl'); s = w.sum(1)
    ww = w.copy(); ww['BTC'] += (1 - s).clip(lower=0) * strict
    rep(f'vt{vt} streng (ohne Langsam-Filter)', ww, d)
    for n in (150, 200, 250):
        gate = (b > b.rolling(n).mean()).astype(float)
        rep(f'   + BTC > SMA{n}', ww.mul(gate, axis=0), d)
        # weich: halbe Exposure unter SMA
        rep(f'   + BTC > SMA{n} (sonst 50%)', ww.mul(gate * 0.5 + 0.5, axis=0), d)
