import sys, os
sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from spotbot.analysis.backtest import simulate
from spotbot.strategy.signal import core_satellite_weights, ENSEMBLE_GRID
WIN = ('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC', 'SUI')
G7 = dict(ENSEMBLE_GRID, rebal=[7])
def job(a):
    grid_name, share, nowin = a
    d = load('1d', exclude=WIN if nowin else ())
    w = core_satellite_weights(d['close'], d['qvol'], share, 10.0, grid=G7 if grid_name == 'rebal7' else ENSEMBLE_GRID)
    if not nowin: w.to_pickle(f'A_{grid_name}_{share}.pkl')
    out = []
    for cost in (0.002, 0.004):
        eq = simulate(w, d['open'], cost=cost, band=0.02).loc['2018':]
        f, i, o = stats(eq, '2018-01-01'), stats(eq, '2018-01-01', '2022-12-31'), stats(eq, '2023-01-01')
        out.append((eq.iloc[-1] / eq.iloc[0], f['maxdd'], f['sharpe'], i['maxdd'], o['pnl'], o['maxdd']))
    return a, out
if __name__ == '__main__':
    jobs = [(g, s, nw) for g in ('v2grid', 'rebal7') for s in (0.2, 0.3) for nw in (False, True)]
    with Pool(os.cpu_count() - 1) as p: res = p.map(job, jobs)
    for (g, s, nw), out in res:
        (m1, d1, s1, i1, o1, od1), (m2, d2, *_rest) = out
        tag = 'OHNE Gewinner' if nw else 'voll         '
        print(f"{g:7s} Kern {s} {tag} | x{m1:6.1f} DD {d1:6.1f} (IS {i1:6.1f}) sh {s1:.2f} OOS {o1:4.0f}%/{od1:6.1f} || 2x Kosten x{m2:5.1f} DD {d2:6.1f}")
