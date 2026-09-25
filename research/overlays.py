import numpy as np, pandas as pd
from engine import load, run_weights, stats
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
d = load('1d'); c = d['close']
def m(eq):
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01'); x = eq.loc['2018-01-01':]
    return f"IS {a['pnl']:6.0f}% dd {a['maxdd']:6.1f} | OOS {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | x{x.iloc[-1]/x.iloc[0]:6.1f} DD {f['maxdd']:6.1f} sh {f['sharpe']:.2f}"
v2 = pd.read_pickle('prod_cs_0.3.pkl')
sat = pd.read_pickle('sat_tw_10.0.pkl')
print('V2 basis                ', m(run_weights(v2, d)))
# a) Funding-Ueberhitzung
f = pd.read_csv('data/BTC_funding.csv', index_col=0).rate; f.index = pd.to_datetime(f.index, utc=True, format='mixed')
fd = f.resample('1D').mean().reindex(c.index)  # Tagesmittel, bekannt am Tagesende
for win in (3, 7):
    fm = fd.rolling(win).mean()
    for thr in (0.0003, 0.0005, 0.0008):
        for scale in (0.0, 0.5):
            k = pd.Series(np.where(fm > thr, scale, 1.0), index=c.index)
            print(f'Funding {win}d>{thr*1e4:.0f}bp -> x{scale}', m(run_weights(v2.mul(k, axis=0), d)), f'| aktiv {(fm>thr).loc["2019-10":].mean()*100:.0f}% d. Tage')
# b) Crash-Schutz
for n, thr in ((3, 0.10), (7, 0.15), (7, 0.20)):
    r = c['BTC'] / c['BTC'].shift(n) - 1
    k = pd.Series(np.where(r < -thr, 0.0, 1.0), index=c.index)
    print(f'Crash BTC {n}d<-{thr:.0%}      ', m(run_weights(v2.mul(k, axis=0), d)))
# c) andere Kerne
btceth = pd.read_pickle('fam_BTCETH.pkl'); brk = pd.read_pickle('fam_BRK.pkl')
from coresat import btc_core
bc = btc_core(c)
for name, core in (('BTC-Trend', None), ('BTCETH-Switch', btceth), ('Breakout', brk)):
    for share in (0.3, 0.5):
        w = sat * (1 - share)
        if core is None: w = w.copy(); w['BTC'] += share * bc
        else: w = w + share * core
        w = w.div(np.maximum(w.sum(1), 1.0), axis=0)
        print(f'Kern {name:13s} {share}', m(run_weights(w, d)))
