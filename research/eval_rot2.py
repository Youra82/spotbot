import itertools, os
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep
from rotation2 import rotation2
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
BASE = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5], liq_top=[10, 20])
VARIANTS = {
    'abs':            dict(rank='abs'),
    'rs':             dict(rank='rs'),
    'sharpe':         dict(rank='sharpe'),
    'abs_skip3':      dict(rank='abs', skip=3),
    'abs_fillbtc':    dict(rank='abs', fill_btc=True),
    'rs_gate':        dict(rank='abs', rs_gate=True),
    'rs_gate_fill':   dict(rank='abs', rs_gate=True, fill_btc=True),
    'rs_fill':        dict(rank='rs', fill_btc=True),
    'rs_gate_fill_sh':dict(rank='sharpe', rs_gate=True, fill_btc=True),
}
_d = _P = None
def init():
    global _d, _P
    _d = load('1d'); _P = Prep(_d)
def job(name):
    keys = list(BASE); acc = None; n = 0
    for v in itertools.product(*BASE.values()):
        p = dict(zip(keys, v))
        for ph in range(7):
            w = rotation2(_P, rebal=7, phase=ph, **p, **VARIANTS[name])
            acc = w if acc is None else acc + w; n += 1
    W = pd.DataFrame(acc / n, index=_P.idx, columns=_P.cols)
    W.to_pickle(f'rot2_{name}.pkl')
    eq = run_weights(W, _d)
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01'); x = eq.loc['2018':]
    return name, a, b, f, x.iloc[-1] / x.iloc[0], W.sum(1).loc['2018':].mean()
if __name__ == '__main__':
    with Pool(min(len(VARIANTS), os.cpu_count() - 1), initializer=init) as pool:
        res = pool.map(job, list(VARIANTS))
    print(f"{'Variante':16s} {'Endwert':>8s} {'DD':>7s} {'Sharpe':>6s} | {'IS-PnL':>7s} {'IS-DD':>6s} | {'OOS':>6s} {'OOS-DD':>7s} | Expo")
    for name, a, b, f, mult, ex in res:
        print(f"{name:16s} x{mult:7.1f} {f['maxdd']:7.1f} {f['sharpe']:6.2f} | {a['pnl']:6.0f}% {a['maxdd']:6.1f} | {b['pnl']:5.0f}% {b['maxdd']:7.1f} | {ex:.2f}")
    print('Referenz: V2 x27.2 DD -35.4 (run_weights), BTC Hold x5.7, OOS +406%')
