import sys, os
sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from spotbot.strategy.signal import target_weights
from spotbot.analysis.backtest import simulate
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)

def btc_core(c):
    b = c['BTC']
    sigs = [b.ewm(span=10).mean() > b.ewm(span=30).mean(),
            b.ewm(span=20).mean() > b.ewm(span=50).mean(),
            b > b.rolling(50).mean(),
            b > b.rolling(100).mean()]
    hi = b.rolling(20).max().shift(1); lo = b.rolling(10).min().shift(1)
    dc = pd.Series(np.nan, index=b.index); dc[b > hi] = 1.0; dc[b < lo] = 0.0
    sigs.append(dc.ffill().fillna(0) > 0)
    return pd.concat(sigs, axis=1).astype(float).mean(axis=1)  # 0..1

def sat_job(vt):
    f = f'sat_tw_{vt}.pkl'
    if not os.path.exists(f):
        d = load('1d'); target_weights(d['close'], d['qvol'], vt).to_pickle(f)
    return vt

if __name__ == '__main__':
    vts = [0.8, 1.2, 10.0]
    with Pool(3) as p: p.map(sat_job, vts)
    d = load('1d'); c = d['close']
    core = btc_core(c)
    rows = []
    for vt in vts:
        sat = pd.read_pickle(f'sat_tw_{vt}.pkl')
        for share in (0.3, 0.4, 0.5, 0.6, 0.7):
            for fill in (False, True):
                w = sat * (1 - share)
                bw = core * share
                if fill:  # ungenutztes Satelliten-Kapital -> BTC, wenn BTC-Trend an
                    idle = (1 - share) - w.sum(1)
                    bw = bw + idle * core
                w = w.copy(); w['BTC'] = w['BTC'] + bw
                w = w.div(np.maximum(w.sum(1), 1.0), axis=0)
                eq = simulate(w, d['open'], cost=0.002, band=0.02)
                a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
                x = eq.loc['2018-01-01':]
                rows.append(dict(vt=vt, share=share, fill=fill, is_pnl=a['pnl'], is_dd=a['maxdd'], oos_pnl=b['pnl'], oos_dd=b['maxdd'],
                                 mult=x.iloc[-1] / x.iloc[0], full_dd=f['maxdd'], sharpe=f['sharpe'], expo=w.sum(1).loc['2018':].mean()))
    g = pd.DataFrame(rows); g.to_csv('coresat.csv', index=False)
    pd.set_option('display.width', 200)
    print(g.round(2).to_string(index=False))
    eqc = simulate(pd.DataFrame({'BTC': core}).reindex(columns=c.columns, fill_value=0).assign(BTC=core), d['open'], band=0.02)
    print('Nur BTC-Kern-Ensemble:', {k: round(float(v), 1) for k, v in stats(eqc, '2018-01-01').items()}, 'OOS', {k: round(float(v), 1) for k, v in stats(eqc, '2023-01-01').items()})
