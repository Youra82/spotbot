import itertools, os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import load, run_weights, stats
import families as F

IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)

GRIDS = {
    'MR_rsi': (F.mean_reversion, dict(kind=['rsi'], n=[2, 3], thr=[5, 10, 20], exit_sma=[3, 5], trend_filter=[0, 200], regime=[0, 50], liq_top=[10, 20])),
    'MR_bb': (F.mean_reversion, dict(kind=['bb'], n=[20], thr=[15, 20, 25], exit_sma=[5, 10], trend_filter=[0, 200], regime=[0, 50], liq_top=[10, 20])),
    'MR_ret': (F.mean_reversion, dict(kind=['ret'], n=[3, 7], thr=[10, 20, 30], exit_sma=[5], trend_filter=[0, 200], regime=[0, 50], liq_top=[10, 20])),
    'DIP': (F.dip_buy, dict(drop=[10, 15, 25], lookback=[3, 7], hold=[3, 7, 14], regime=[0, 50], liq_top=[10, 20])),
    'BRK': (F.breakout, dict(n_in=[20, 50, 100], atr_mult=[2, 3, 5], regime=[0, 50], liq_top=[10, 20], slots=[3, 5])),
    'VBO': (F.vol_breakout, dict(k=[0.3, 0.5, 0.8], regime=[0, 50], liq_top=[5, 10, 20], slots=[3, 5])),
    'WDAY': (F.weekday, dict(days=[(0, 4, 5), (0,), (4, 5), (0, 5), (5, 6, 0)], regime=[0, 50, 100])),
    'BTCETH': (F.btc_eth_switch, dict(n=[14, 30, 60], regime=[0, 50, 100])),
}

_d = _v2 = None


def init():
    global _d, _v2
    _d = load('1d')
    _v2 = pd.read_pickle('prod_cs_0.3.pkl')


def m(eq):
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    x = eq.loc['2018-01-01':]
    return dict(is_pnl=a['pnl'], is_dd=a['maxdd'], oos_pnl=b['pnl'], oos_dd=b['maxdd'], mult=x.iloc[-1] / x.iloc[0],
                full_dd=f['maxdd'], sharpe=f['sharpe'])


def job(a):
    fam, p = a
    fn = GRIDS[fam][0]
    w = fn(_d, **p).fillna(0)
    eq = run_weights(w, _d)
    return fam, p, w.values.astype(np.float32), m(eq), eq.pct_change().loc['2018':]


if __name__ == '__main__':
    jobs = []
    for fam, (fn, g) in GRIDS.items():
        keys = list(g)
        jobs += [(fam, dict(zip(keys, v))) for v in itertools.product(*g.values())]
    print(len(jobs), 'Konfigurationen', flush=True)
    d = load('1d'); v2 = pd.read_pickle('prod_cs_0.3.pkl')
    v2eq = run_weights(v2, d); v2r = v2eq.pct_change().loc['2018':]
    idle = (1 - v2.sum(1)).clip(lower=0)
    rows, famw = [], {}
    with Pool(os.cpu_count() - 1, initializer=init) as pool:
        for fam, p, w, met, r in pool.imap_unordered(job, jobs, chunksize=4):
            rows.append(dict(fam=fam, params=str(p), corr_v2=r.corr(v2r), **met))
            famw.setdefault(fam, []).append(w)
    g = pd.DataFrame(rows); g.to_csv('families.csv', index=False)
    pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 90)
    print('\n=== Familien-Ensemble (Mittel aller Konfigs), allein und als Leerlauf-Fueller fuer V2 ===')
    print('V2 allein:', {k: round(float(v), 1) for k, v in m(v2eq).items()})
    out = []
    for fam, ws in famw.items():
        W = pd.DataFrame(np.mean(ws, axis=0), index=d['close'].index, columns=d['close'].columns)
        W.to_pickle(f'fam_{fam}.pkl')
        s = W.sum(1)
        Wn = W.div(np.maximum(s, 1e-12), axis=0).fillna(0)  # auf 100% normierte Familienallokation
        e1 = run_weights(W, d)
        fill = v2 + Wn.mul(np.minimum(idle, s * 0 + 1) * np.minimum(s, 1), axis=0)  # nur im Leerlauf-Cash
        e2 = run_weights(fill, d)
        out.append(dict(fam=fam, **{f'solo_{k}': v for k, v in m(e1).items()}, corr=e1.pct_change().loc['2018':].corr(v2r),
                        expo=s.loc['2018':].mean(), **{f'fill_{k}': v for k, v in m(e2).items()}))
    o = pd.DataFrame(out).set_index('fam')
    print(o[['solo_mult', 'solo_full_dd', 'solo_oos_pnl', 'solo_sharpe', 'corr', 'expo']].round(2).to_string())
    print('\nV2 + Familie im Leerlauf-Cash:')
    print(o[['fill_mult', 'fill_full_dd', 'fill_is_dd', 'fill_oos_pnl', 'fill_oos_dd', 'fill_sharpe']].round(2).to_string())
    print('\n=== Beste Einzelkonfig je Familie nach IS-Sharpe-Proxy (IS-PnL bei IS-DD > -40) ===')
    for fam, gg in g.groupby('fam'):
        s = gg[gg.is_dd > -40].sort_values('is_pnl', ascending=False).head(2)
        print(s[['fam', 'params', 'is_pnl', 'is_dd', 'oos_pnl', 'oos_dd', 'mult', 'full_dd', 'corr_v2']].round(2).to_string(index=False, header=False))
