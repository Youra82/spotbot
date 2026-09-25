"""Feines Grid um die strukturellen DD-Hebel; speichert Tagesrenditen fuer Walk-Forward."""
import itertools, time, sys, os
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, rotation
grid = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5, 8], rebal=[7, 14],
            vol_target=[0.2, 0.25, 0.3, 0.35, 0.4, 0.5], liq_top=[10, 15, 20], breadth_min=[0.3, 0.5],
            vol_long=[0, 90])
keys = list(grid)
_d = _P = None
def init():
    global _d, _P
    _d = load('1d'); _P = Prep(_d)
def job(a):
    k, vals = a
    p = dict(zip(keys, vals))
    eq = run_weights(rotation(_P, **p), _d)
    return k, eq.pct_change().fillna(0).values.astype(np.float32)
if __name__ == '__main__':
    combos = list(itertools.product(*grid.values()))
    d = load('1d'); idx = d['close'].index
    print(len(combos), 'Kombis', flush=True); t0 = time.time()
    M = np.zeros((len(combos), len(idx)), dtype=np.float32)
    with Pool(max(1, os.cpu_count() - 1), initializer=init) as pool:
        for n, (k, r) in enumerate(pool.imap_unordered(job, enumerate(combos), chunksize=20)):
            M[k] = r
            if n % 1000 == 0: print(n, f'{time.time() - t0:.0f}s', flush=True)
    np.save('grid2_rets.npy', M)
    pd.DataFrame(combos, columns=keys).to_csv('grid2_params.csv', index=False)
    pd.Series(idx).to_csv('grid2_index.csv', index=False)
    print('fertig', flush=True)
