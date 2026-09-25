import sys, os, itertools
sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from fast import Prep
from rotation2 import rotation2
from spotbot.analysis.backtest import simulate
from spotbot.strategy.signal import btc_core_signal, core_satellite_weights
WIN = ('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC', 'SUI')
V2GRID = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5, 8], liq_top=[10, 15, 20], breadth_min=[0.3, 0.5])
NEW = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5], liq_top=[10, 20], breadth_min=[0.3])
CASES = {
    'A V2-Grid, abs, voll investiert (=V2-Sat, nur rebal7)': (V2GRID, dict(rank='abs', cash_slots=False)),
    'B V2-Grid, abs, Cash-Slots':                            (V2GRID, dict(rank='abs', cash_slots=True)),
    'C V2-Grid, sharpe, voll investiert':                     (V2GRID, dict(rank='sharpe', cash_slots=False)),
    'D V2-Grid, sharpe, Cash-Slots':                          (V2GRID, dict(rank='sharpe', cash_slots=True)),
    'E Neu-Grid, abs, voll investiert':                       (NEW, dict(rank='abs', cash_slots=False)),
    'F Neu-Grid, abs, Cash-Slots':                            (NEW, dict(rank='abs', cash_slots=True)),
    'G Neu-Grid, sharpe, Cash-Slots':                         (NEW, dict(rank='sharpe', cash_slots=True)),
}
def job(a):
    name, nowin = a
    grid, kw = CASES[name]
    d = load('1d', exclude=WIN if nowin else ()); P = Prep(d)
    keys = list(grid); acc = None; n = 0
    for v in itertools.product(*grid.values()):
        for ph in range(7):
            w = rotation2(P, rebal=7, phase=ph, **dict(zip(keys, v)), **kw)
            acc = w if acc is None else acc + w; n += 1
    s = pd.DataFrame(acc / n, index=P.idx, columns=P.cols)
    w = s * 0.8; w['BTC'] += 0.2 * btc_core_signal(d['close']['BTC'])
    w = w.div(np.maximum(w.sum(1), 1.0), axis=0)
    eq = simulate(w, d['open'], cost=0.002, band=0.02).loc['2018':]
    f, o = stats(eq, '2018-01-01'), stats(eq, '2023-01-01')
    return name, nowin, eq.iloc[-1] / eq.iloc[0], f['maxdd'], f['sharpe'], o['pnl'], o['maxdd']
def v2job(nowin):
    d = load('1d', exclude=WIN if nowin else ())
    w = core_satellite_weights(d['close'], d['qvol'], 0.3, 10.0)
    eq = simulate(w, d['open'], cost=0.002, band=0.02).loc['2018':]
    f, o = stats(eq, '2018-01-01'), stats(eq, '2023-01-01')
    return 'V2 original (Kern 0.3)', nowin, eq.iloc[-1] / eq.iloc[0], f['maxdd'], f['sharpe'], o['pnl'], o['maxdd']
if __name__ == '__main__':
    jobs = [(n, nw) for n in CASES for nw in (False, True)]
    with Pool(os.cpu_count() - 1) as p:
        r1 = p.map_async(v2job, [False, True]); res = p.map(job, jobs); res = r1.get() + res
    print(f"{'Fall (alle mit 20% BTC-Kern ausser V2)':55s} {'Endwert':>8s} {'DD':>7s} {'Sh':>5s} {'OOS':>6s} {'OOS-DD':>7s} | ohne Gewinner-Coins")
    by = {(r[0], r[1]): r for r in res}
    for name in ['V2 original (Kern 0.3)'] + list(CASES):
        a, b = by[(name, False)], by[(name, True)]
        print(f"{name:55s} x{a[2]:6.1f} {a[3]:7.1f} {a[4]:5.2f} {a[5]:5.0f}% {a[6]:7.1f} | x{b[2]:5.1f} DD {b[3]:6.1f} sh {b[4]:.2f} OOS {b[5]:4.0f}%")
