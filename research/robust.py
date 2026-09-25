import os
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, ensemble
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
WIN = ('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC', 'SUI')
def fmt(name, eq):
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    return f"{name:34s} IS pnl {a['pnl']:6.0f}% dd {a['maxdd']:6.1f} | OOS pnl {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f}"
def job(a):
    vt, kind, arg = a
    d = load('1d', exclude=WIN if kind == 'nowin' else ())
    P = Prep(d)
    w = ensemble(P, vt, cash_slots=False, phase=arg if kind == 'phase' else 0)
    if kind == 'delay': w = w.shift(1).fillna(0)
    eq = run_weights(w, d, cost=0.004 if kind == 'cost2x' else 0.002)
    return fmt(f'vt{vt} {kind} {arg}', eq)
if __name__ == '__main__':
    jobs = []
    for vt in (0.8, 1.0):
        jobs += [(vt, 'cost2x', ''), (vt, 'nowin', ''), (vt, 'delay', '')] + [(vt, 'phase', p) for p in range(7)]
    with Pool(os.cpu_count() - 1) as p:
        for line in p.map(job, jobs): print(line, flush=True)
