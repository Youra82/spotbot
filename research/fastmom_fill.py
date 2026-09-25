import sys; sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from engine import load, stats
from spotbot.strategy.signal import btc_core_signal
from spotbot.analysis.backtest import simulate
from fastmom import rep
d = load('1d'); core = btc_core_signal(d['close']['BTC'])
for vt in (10.0, 1.5, 1.0, 0.8):
    w = pd.read_pickle(f'fast_tw_{vt}.pkl')
    s = w.sum(1)
    print(f'vt{vt}: Exposure Ø gesamt {s.loc["2018":].mean():.2f}, OOS {s.loc["2023":].mean():.2f}, BTC-Signal an im OOS {core.loc["2023":].mean():.2f}')
    ww = w.copy(); ww['BTC'] += (1 - s).clip(lower=0) * core
    rep(f'FastMom vt{vt} + Leerlauf->BTC', ww, d)
