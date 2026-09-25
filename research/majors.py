import itertools, os
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
from fast import Prep, rotation
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def row(name, eq):
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    x = eq.loc['2018-01-01':]
    return dict(name=name, is_pnl=a['pnl'], is_dd=a['maxdd'], oos_pnl=b['pnl'], oos_dd=b['maxdd'], mult=x.iloc[-1]/x.iloc[0], full_dd=f['maxdd'])
def job(p):
    d = load('1d'); P = Prep(d); out = []
    kind = p[0]
    if kind == 'major':
        _, liq, sma, mom, k, reb, bs = p
        w = rotation(P, btc_sma=bs, coin_sma=sma, mom=mom, top_k=k, rebal=reb, vol_target=None, liq_top=liq, cash_slots=False)
        out.append(row(f'major liq{liq} sma{sma} mom{mom} k{k} reb{reb} btc{bs}', run_weights(w, d)))
    else:
        _, core, ema = p
        c = d['close']; b = c['BTC']
        sig = (b.ewm(span=ema[0]).mean() > b.ewm(span=ema[1]).mean()).astype(float)
        wb = pd.DataFrame(0.0, index=c.index, columns=c.columns); wb['BTC'] = sig
        for liq in (10, 20):
            sat = rotation(P, btc_sma=50, coin_sma=20, mom=30, top_k=3, rebal=7, vol_target=None, liq_top=liq, breadth_min=0.3, cash_slots=False)
            w = core * wb + (1 - core) * sat
            out.append(row(f'core{core} ema{ema} + sat liq{liq}', run_weights(w, d)))
    return out
if __name__ == '__main__':
    jobs = [('major', liq, sma, mom, k, reb, bs) for liq in (3, 5, 8) for sma in (20, 50) for mom in (14, 30, 60, 90)
            for k in (1, 2) for reb in (1, 7) for bs in (0, 50)]
    jobs += [('core', c, e) for c in (0.5, 0.7, 0.85) for e in ((10, 30), (20, 50))]
    rows = []
    with Pool(os.cpu_count() - 1) as p:
        for r in p.imap_unordered(job, jobs): rows += r
    g = pd.DataFrame(rows); g.to_csv('majors.csv', index=False)
    pd.set_option('display.width', 200)
    print('Anzahl', len(g))
    print('\nTop nach IS (ehrlich, OOS nur angeschaut): IS-DD > -45%')
    print(g[g.is_dd > -45].sort_values('is_pnl', ascending=False).head(12).round(1).to_string(index=False))
    print('\nBTC-Kern + Satellit:'); print(g[g.name.str.startswith('core')].round(1).to_string(index=False))
    print('\nObergrenze (Rueckschau): OOS-DD > -30%: bestes OOS', round(g[g.oos_dd > -30].oos_pnl.max()), '% | OOS-DD > -40%:', round(g[g.oos_dd > -40].oos_pnl.max()), '%')
