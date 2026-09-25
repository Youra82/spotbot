import itertools, time, sys, os
import pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, rotation
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
grid = dict(btc_sma=[0, 50, 100], coin_sma=[20, 50, 100], mom=[14, 30, 60, 90], top_k=[2, 3, 5],
            rebal=[1, 3, 7], vol_target=[None, 0.3, 0.5], liq_top=[10, 20, 30], breadth_min=[0, 0.4],
            trail=[None, 0.2])
keys = list(grid)
_d = _P = None
def init():
    global _d, _P
    _d = load('1d'); _P = Prep(_d)
def job(vals):
    p = dict(zip(keys, vals))
    eq = run_weights(rotation(_P, **p), _d)
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    return {**p, **{f'is_{x}': a[x] for x in a}, **{f'oos_{x}': b[x] for x in b}, **{f'full_{x}': f[x] for x in f}}
if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'grid1.csv'
    combos = list(itertools.product(*grid.values()))
    print(len(combos), 'Kombis', flush=True); t0 = time.time(); rows = []
    with Pool(max(1, os.cpu_count() - 1), initializer=init) as pool:
        for k, r in enumerate(pool.imap_unordered(job, combos, chunksize=20)):
            rows.append(r)
            if k % 1000 == 0: print(k, f'{time.time() - t0:.0f}s', flush=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print('fertig', flush=True)
