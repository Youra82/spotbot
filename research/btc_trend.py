import numpy as np, pandas as pd
from engine import load, run_weights, stats
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def show(name, w, d):
    eq = run_weights(w, d)
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    x = eq.loc['2018-01-01':]; mult = x.iloc[-1] / x.iloc[0]
    print(f"{name:34s} IS {a['pnl']:7.0f}% dd {a['maxdd']:6.1f} | OOS {b['pnl']:6.0f}% dd {b['maxdd']:6.1f} | FULL x{mult:6.1f} cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f}", flush=True)
for tf, k in (('1d', 1), ('4h', 6)):
    d = load(tf); c = d['close']; b = c['BTC']
    def W(sig):
        w = pd.DataFrame(0.0, index=c.index, columns=c.columns); w['BTC'] = sig.astype(float); return w
    print(f'--- {tf} ---')
    show('BuyHold', W(b > 0), d)
    for n in (20, 50, 100, 200):
        show(f'SMA{n}d', W(b > b.rolling(n * k).mean()), d)
    for f_, s_ in ((10, 30), (20, 50), (50, 100)):
        show(f'EMA{f_}/{s_}d', W(b.ewm(span=f_ * k).mean() > b.ewm(span=s_ * k).mean()), d)
    for n in (20, 50):
        hi = b.rolling(n * k).max().shift(1); lo = b.rolling(n // 2 * k).min().shift(1)
        sig = pd.Series(np.nan, index=b.index); sig[b > hi] = 1; sig[b < lo] = 0
        show(f'Donchian{n}/{n//2}d', W(sig.ffill().fillna(0) > 0), d)
