import sys; sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from engine import load, stats
from coresat import btc_core
from spotbot.analysis.backtest import simulate
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
d = load('1d'); c = d['close']
core_sig = btc_core(c)
bvol = c['BTC'].pct_change().rolling(30).std() * np.sqrt(365)
rows = []
for cvt in (None, 0.4, 0.5, 0.6, 0.8):
    core = core_sig * (np.minimum(1, cvt / bvol).fillna(0) if cvt else 1)
    for vt in (1.2, 10.0):
        sat = pd.read_pickle(f'sat_tw_{vt}.pkl')
        for share in (0.3, 0.5, 0.7, 1.0):
            for fill in (False, True):
                if share == 1.0 and fill: continue
                w = sat * (1 - share); bw = core * share
                if fill: bw = bw + ((1 - share) - w.sum(1)) * core
                w = w.copy(); w['BTC'] += bw
                w = w.div(np.maximum(w.sum(1), 1.0), axis=0)
                eq = simulate(w, d['open'], cost=0.002, band=0.02)
                a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
                x = eq.loc['2018-01-01':]
                rows.append(dict(core_vt=cvt or 0, sat_vt=vt, share=share, fill=fill, is_pnl=a['pnl'], is_dd=a['maxdd'], oos_pnl=b['pnl'], oos_dd=b['maxdd'], mult=x.iloc[-1]/x.iloc[0], full_dd=f['maxdd'], sharpe=f['sharpe']))
g = pd.DataFrame(rows); g.to_csv('coresat2.csv', index=False)
pd.set_option('display.width', 200)
print('Auswahl NUR nach IS: IS-DD > -32% (Puffer fuer OOS), sortiert nach IS-PnL')
print(g[g.is_dd > -32].sort_values('is_pnl', ascending=False).head(15).round(2).to_string(index=False))
print('\nBTC Hold: x5.7, DD -81%, OOS +406% DD -53%')
