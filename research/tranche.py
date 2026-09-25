import os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, ensemble
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def job(a):
    vt, ph = a
    d = load('1d'); P = Prep(d)
    return a, ensemble(P, vt, cash_slots=False, phase=ph).values
if __name__ == '__main__':
    vts = [float(x) for x in sys.argv[1:]] or [0.8, 1.0]
    d = load('1d'); c = d['close']
    jobs = [(vt, ph) for vt in vts for ph in range(14)]
    acc = {vt: 0 for vt in vts}
    with Pool(os.cpu_count() - 1) as p:
        for (vt, ph), w in p.imap_unordered(job, jobs):
            acc[vt] = acc[vt] + w / 14
    for vt in vts:
        w = pd.DataFrame(acc[vt], index=c.index, columns=c.columns)
        w.to_pickle(f'tr_w_{vt}.pkl')
        for cost in (0.002, 0.004):
            eq = run_weights(w, d, cost=cost)
            if cost == 0.002: eq.to_pickle(f'tr_eq_{vt}.pkl')
            a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
            print(f"TRANCHEN vt {vt} cost {cost}: IS pnl {a['pnl']:6.0f}% dd {a['maxdd']:6.1f} | OOS pnl {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f}", flush=True)
