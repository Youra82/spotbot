import os
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, ensemble
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def job(a):
    vt, cs = a
    d = load('1d'); P = Prep(d)
    w = ensemble(P, vt, cash_slots=cs); eq = run_weights(w, d)
    eq.to_pickle(f'ens_eq_{vt}_cs{int(cs)}.pkl')
    a_, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    return f"vt {vt:.2f} cash_slots={cs}: IS pnl {a_['pnl']:6.0f}% dd {a_['maxdd']:6.1f} | OOS pnl {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f} | Expo {w.sum(1).loc['2018':].mean():.2f}"
if __name__ == '__main__':
    jobs = [(v, False) for v in (0.5, 0.6, 0.7, 0.8, 1.0)]
    with Pool(5) as p:
        for line in p.map(job, jobs): print(line, flush=True)
