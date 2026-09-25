import sys, os; sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from spotbot.strategy.signal import target_weights, btc_core_signal
from spotbot.analysis.backtest import simulate
from fastmom import FAST, rep
WIN = ('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC', 'SUI')
def build(d, w):
    b = d['close']['BTC']; s = w.sum(1)
    ww = w.copy(); ww['BTC'] += (1 - s).clip(lower=0) * (btc_core_signal(b) == 1).astype(float)
    gate = (b > b.rolling(150).mean()).astype(float) * 0.5 + 0.5
    return ww.mul(gate, axis=0)
def job(nowin):
    d = load('1d', exclude=WIN if nowin else ())
    f = 'fast_tw_1.5_nowin.pkl' if nowin else 'fast_tw_1.5.pkl'
    w = pd.read_pickle(f) if os.path.exists(f) else target_weights(d['close'], d['qvol'], 1.5, grid=FAST)
    w.to_pickle(f)
    return nowin, w
if __name__ == '__main__':
    with Pool(2) as p: R = dict(p.map(job, [False, True]))
    d = load('1d'); dn = load('1d', exclude=WIN)
    v3 = build(d, R[False]); v3.to_pickle('v3_candidate.pkl')
    rep('V3-Kandidat', v3, d)
    rep('V3 ohne 10 Gewinner-Coins', build(dn, R[True]), dn)
    rep('V3 1 Tag verzoegert', v3.shift(1).fillna(0), d)
    # Vergleich: BTC halten ohne Gewinner-Coins bleibt gleich (+406%)
    eq = simulate(v3, d['open'], band=0.02).loc['2018':]
    y = eq.resample('YE').last(); yr = y.pct_change(); yr.iloc[0] = y.iloc[0] / eq.iloc[0] - 1
    bh = d['close']['BTC'].loc['2018':]; by = bh.resample('YE').last(); byr = by.pct_change(); byr.iloc[0] = by.iloc[0] / bh.iloc[0] - 1
    print('Jahr   V3     BTC')
    for (i, v), bv in zip(yr.items(), byr.values): print(f'{i.year}  {v*100:+5.0f}%  {bv*100:+5.0f}%')
    print('Ø Exposure', round(float(v3.sum(1).loc['2018':].mean()), 2), '| Ø Anzahl Coins > 1%:', round(float((v3 > 0.01).sum(1).loc['2018':].mean()), 1))
