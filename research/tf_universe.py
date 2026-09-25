import os, itertools
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, rotation
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
_d = {}; _P = {}
def get(tf):
    if tf not in _d:
        _d[tf] = load(tf); _P[tf] = Prep(_d[tf], vol_win=30 * (6 if tf == '4h' else 1))
    return _d[tf], _P[tf]
def job(a):
    tf, p = a
    d, P = get(tf); k = 6 if tf == '4h' else 1
    q = dict(p); q['btc_sma'] *= k; q['coin_sma'] *= k; q['mom'] = int(q['mom'] * k)
    q['rebal'] = max(1, int(q['rebal'] * k))
    ws = [rotation(P, vol_target=None, cash_slots=False, phase=ph, **q) for ph in range(0, q['rebal'], max(1, q['rebal'] // 3))]
    w = sum(ws) / len(ws)
    eq = run_weights(w, d)
    a_, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01'); x = eq.loc['2018-01-01':]
    return dict(tf=tf, **p, is_pnl=a_['pnl'], is_dd=a_['maxdd'], oos_pnl=b['pnl'], oos_dd=b['maxdd'], mult=x.iloc[-1] / x.iloc[0], dd=f['maxdd'], sh=f['sharpe'])
if __name__ == '__main__':
    grid = dict(btc_sma=[50], coin_sma=[20, 50], mom=[7, 14, 30], top_k=[3, 5], rebal=[1, 7], liq_top=[10, 20, 40], breadth_min=[0.3])
    combos = [dict(zip(grid, v)) for v in itertools.product(*grid.values())]
    jobs = [(tf, p) for tf in ('1d', '4h') for p in combos]
    rows = []
    with Pool(os.cpu_count() - 1) as pool:
        for r in pool.imap_unordered(job, jobs): rows.append(r)
    g = pd.DataFrame(rows); g.to_csv('tf_universe.csv', index=False)
    pd.set_option('display.width', 220)
    print('Median je Zeitebene:'); print(g.groupby('tf')[['mult', 'dd', 'oos_pnl', 'oos_dd', 'sh']].median().round(2))
    print('\nMedian je Universum-Breite:'); print(g.groupby(['tf', 'liq_top'])[['mult', 'dd', 'oos_pnl', 'oos_dd', 'sh']].median().round(2))
    print('\nMedian je Umschichtung:'); print(g.groupby(['tf', 'rebal'])[['mult', 'dd', 'oos_pnl', 'sh']].median().round(2))
    print('\nPaarvergleich gleiche Parameter 4h vs 1d: Anteil 4h besser (Sharpe):')
    pv = g.pivot_table(index=['coin_sma', 'mom', 'top_k', 'rebal', 'liq_top'], columns='tf', values='sh')
    print(round((pv['4h'] > pv['1d']).mean(), 2))
