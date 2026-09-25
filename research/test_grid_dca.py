import sys, itertools, os
import numpy as np, pandas as pd
from multiprocessing import Pool
from grid_dca import load_1h, dca_martingale, grid, daily_stats
syms = sys.argv[1].split(',') if len(sys.argv) > 1 else ['BTC', 'ETH']
def regime_series(n):
    b = load_1h('BTC').close.resample('1D').last()
    r = (b > b.rolling(n).mean()).shift(1)  # erst am naechsten Tag bekannt
    return r.reindex(pd.date_range(r.index[0], r.index[-1] + pd.Timedelta(hours=23), freq='1h', tz='UTC'), method='ffill').astype(bool)
REG = None
def job(a):
    kind, sym, p = a
    df = load_1h(sym)
    p = dict(p); n = p.pop('reg')
    reg = regime_series(n) if n else None
    eq = dca_martingale(df, regime=reg, **p) if kind == 'DCA' else grid(df, regime=reg, **p)
    s = [daily_stats(eq, '2018-01-01', '2022-12-31') if eq.index[0] < pd.Timestamp('2021-01-01', tz='UTC') else None, daily_stats(eq, '2023-01-01'), daily_stats(eq)]
    return kind, sym, a[2], s
if __name__ == '__main__':
    jobs = []
    for sym in syms:
        for reg in (0, 50):
            for so_step, vs, n_so, tp, sl in [(0.02, 1.5, 6, 0.015, None), (0.03, 1.5, 5, 0.02, None), (0.015, 2.0, 5, 0.01, None),
                                             (0.05, 1.3, 4, 0.03, None), (0.03, 1.5, 5, 0.02, 0.25), (0.02, 1.2, 8, 0.02, None)]:
                jobs.append(('DCA', sym, dict(reg=reg, so_step=so_step, vol_scale=vs, max_so=n_so, tp=tp, sl=sl)))
            for width, nl, rd in [(0.2, 20, 14), (0.3, 20, 30), (0.5, 40, 60), (0.3, 10, 30), (1.0, 50, 180)]:
                jobs.append(('GRID', sym, dict(reg=reg, width=width, n_levels=nl, reset_days=rd)))
    rows = []
    with Pool(os.cpu_count() - 1) as pool:
        for kind, sym, p, s in pool.imap_unordered(job, jobs):
            p = {k: v for k, v in p.items()}
            rows.append(dict(kind=kind, sym=sym, params=str(p), is_mult=s[0]['mult'] if s[0] else np.nan, is_dd=s[0]['dd'] if s[0] else np.nan,
                             oos_mult=s[1]['mult'], oos_dd=s[1]['dd'], full_mult=s[2]['mult'], full_dd=s[2]['dd']))
    g = pd.DataFrame(rows).sort_values(['kind', 'sym', 'full_mult'], ascending=[True, True, False])
    g.to_csv(f'grid_dca_{"_".join(syms)}.csv', index=False)
    pd.set_option('display.width', 230); pd.set_option('display.max_colwidth', 100)
    print(g.round(2).to_string(index=False))
