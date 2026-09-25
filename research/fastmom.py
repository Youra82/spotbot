import sys, os
sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from spotbot.strategy.signal import target_weights, btc_core_signal
from spotbot.analysis.backtest import simulate
FAST = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[7, 10, 14, 21], top_k=[1, 2, 3], rebal=[7], liq_top=[5, 8, 10], breadth_min=[0.0, 0.3])
def job(vt):
    f = f'fast_tw_{vt}.pkl'
    if not os.path.exists(f):
        d = load('1d'); target_weights(d['close'], d['qvol'], vt, grid=FAST).to_pickle(f)
    return vt
def rep(name, w, d):
    eq = simulate(w, d['open'], cost=0.002, band=0.02).loc['2018':]
    f, i, o = stats(eq, '2018-01-01'), stats(eq, '2018-01-01', '2022-12-31'), stats(eq, '2023-01-01')
    eq2 = simulate(w, d['open'], cost=0.004, band=0.02).loc['2018':]; o2 = stats(eq2, '2023-01-01')
    ok = 'ZIEL' if o['pnl'] >= 558 else ''
    print(f"{name:34s} x{eq.iloc[-1]/eq.iloc[0]:7.1f} DD {f['maxdd']:6.1f} sh {f['sharpe']:.2f} | IS {i['pnl']:6.0f}% dd {i['maxdd']:6.1f} | OOS {o['pnl']:5.0f}% dd {o['maxdd']:6.1f} | 2xK OOS {o2['pnl']:5.0f}% {ok}", flush=True)
if __name__ == '__main__':
    vts = [10.0, 1.5, 1.0, 0.8]
    with Pool(4) as p: p.map(job, vts)
    d = load('1d'); core = btc_core_signal(d['close']['BTC'])
    print('BTC Hold OOS +406%, Ziel >= +558%')
    for vt in vts:
        w = pd.read_pickle(f'fast_tw_{vt}.pkl')
        rep(f'FastMom vt{vt}', w, d)
        for share in (0.2, 0.4):
            ww = w * (1 - share); ww = ww.copy(); ww['BTC'] += share * core
            rep(f'  + BTC-Kern {share}', ww.div(np.maximum(ww.sum(1), 1), axis=0), d)
