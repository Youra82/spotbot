import os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, ensemble
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def job(vt):
    d = load('1d'); P = Prep(d)
    w = ensemble(P, vt); eq = run_weights(w, d)
    w.to_pickle(f'ens_w_{vt}.pkl'); eq.to_pickle(f'ens_eq_{vt}.pkl')
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    expo = w.sum(1).loc['2018':].mean()
    return f"vt {vt:.2f}: IS pnl {a['pnl']:6.0f}% dd {a['maxdd']:6.1f} | OOS pnl {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f} | avg Exposure {expo:.2f}"
if __name__ == '__main__':
    vts = [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5]
    with Pool(min(len(vts), os.cpu_count() - 1)) as p:
        for line in p.map(job, vts): print(line, flush=True)
