import sys, os, itertools
sys.path.insert(0, '../src')
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, stats
from fast import Prep
from rotation2 import rotation2
from spotbot.analysis.backtest import simulate
from spotbot.strategy.signal import btc_core_signal
BASE = dict(btc_sma=[50, 100], coin_sma=[20, 50], mom=[14, 30, 60], top_k=[3, 5], liq_top=[10, 20])
WIN = ('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC', 'SUI')
def sat(d, rank):
    P = Prep(d); keys = list(BASE); acc = None; n = 0
    for v in itertools.product(*BASE.values()):
        for ph in range(7):
            w = rotation2(P, rebal=7, phase=ph, rank=rank, **dict(zip(keys, v)))
            acc = w if acc is None else acc + w; n += 1
    return pd.DataFrame(acc / n, index=P.idx, columns=P.cols)
def job(a):
    rank, nowin = a
    d = load('1d', exclude=WIN if nowin else ())
    return a, sat(d, rank)
def combine(s, c, share):
    w = s * (1 - share); w = w.copy(); w['BTC'] += share * btc_core_signal(c['BTC'])
    return w.div(np.maximum(w.sum(1), 1.0), axis=0)
def rep(name, w, d, cash_apy=0.0):
    out = []
    for cost in (0.002, 0.004):
        eq = simulate(w, d['open'], cost=cost, band=0.02)
        if cash_apy:
            idle = (1 - w.sum(1)).clip(0, 1).shift(1).fillna(1).reindex(eq.index)
            r = eq.pct_change().fillna(0) + idle * ((1 + cash_apy) ** (1 / 365) - 1)
            eq = (1 + r).cumprod() * eq.iloc[0]
        eq = eq.loc['2018':]
        f, i, o = stats(eq, '2018-01-01'), stats(eq, '2018-01-01', '2022-12-31'), stats(eq, '2023-01-01')
        out.append(f"x{eq.iloc[-1]/eq.iloc[0]:6.1f} DD {f['maxdd']:6.1f} sh {f['sharpe']:.2f} OOS {o['pnl']:4.0f}%/{o['maxdd']:5.1f}")
    print(f'{name:40s} | {out[0]} || 2x Kosten: {out[1]}', flush=True)
if __name__ == '__main__':
    with Pool(4) as p:
        R = dict(p.map(job, [('abs', False), ('sharpe', False), ('abs', True), ('sharpe', True)]))
    d = load('1d'); dn = load('1d', exclude=WIN)
    v2 = pd.read_pickle('prod_cs_0.3.pkl')
    R[('sharpe', False)].to_pickle('v3_sat_sharpe.pkl')
    rep('V2 (Referenz)', v2, d)
    for share in (0.0, 0.2, 0.3):
        rep(f'ABS-Satellit + BTC-Kern {share}', combine(R[('abs', False)], d['close'], share), d)
        rep(f'SHARPE-Satellit + BTC-Kern {share}', combine(R[('sharpe', False)], d['close'], share), d)
    print('--- ohne Top-Gewinner-Coins (Survivorship-Stress) ---')
    for share in (0.0, 0.3):
        rep(f'ABS ohne Gewinner, Kern {share}', combine(R[('abs', True)], dn['close'], share), dn)
        rep(f'SHARPE ohne Gewinner, Kern {share}', combine(R[('sharpe', True)], dn['close'], share), dn)
    print('--- mit 4% p.a. auf Leerlauf-USDT ---')
    rep('SHARPE + Kern 0.2 + 4% Cash-Zins', combine(R[('sharpe', False)], d['close'], 0.2), d, 0.04)
    rep('V2 + 4% Cash-Zins', v2, d, 0.04)
