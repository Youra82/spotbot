import numpy as np, pandas as pd
from engine import load, run_weights, stats
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
d = load('1d')
def m(eq):
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01'); x = eq.loc['2018-01-01':]
    return f"IS {a['pnl']:7.0f}% dd {a['maxdd']:6.1f} | OOS {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | x{x.iloc[-1]/x.iloc[0]:6.1f} DD {f['maxdd']:6.1f} sh {f['sharpe']:.2f}"
base = {'V2': pd.read_pickle('prod_cs_0.3.pkl'), 'BTCETH': pd.read_pickle('fam_BTCETH.pkl'), 'BRK': pd.read_pickle('fam_BRK.pkl')}
print('Durchschnittliche Exposure:', {k: round(float(w.sum(1).loc['2018':].mean()), 2) for k, w in base.items()})
for k, w in base.items(): print(f'{k:8s} basis          ', m(run_weights(w, d)))
print('\n--- Kombinationen (gleichgewichtet) ---')
for combo in (('V2', 'BTCETH'), ('V2', 'BRK'), ('BTCETH', 'BRK'), ('V2', 'BTCETH', 'BRK')):
    w = sum(base[c] for c in combo) / len(combo)
    print(f'{"+".join(combo):18s}', m(run_weights(w, d)))
    # ungenutztes Kapital der Kombi auf die aktiven Teile hochskalieren (max 100%)
    s = w.sum(1); w2 = w.div(np.maximum(s, 1e-9), axis=0).mul(np.minimum(1, s * len(combo)), axis=0).fillna(0)
    print(f'{"+".join(combo)+" skaliert":18s}', m(run_weights(w2, d)))
print('\n--- Anti-Martingale / Martingale auf der Strategie-Equity (Signal nur aus Vergangenheit) ---')
for k in ('V2', 'BTCETH'):
    w = base[k]; eq = run_weights(w, d)
    for mode, n in (('anti_sma', 20), ('anti_sma', 50), ('anti_high', 0.1), ('anti_high', 0.2), ('martin_dd', 0.1), ('martin_dd', 0.2)):
        if mode == 'anti_sma':    # Voller Einsatz nur wenn Equity > SMA(n), sonst halber
            f = np.where(eq > eq.rolling(n).mean(), 1.0, 0.5)
        elif mode == 'anti_high':  # Einsatz faellt linear mit Abstand zum Hoch, halbiert bei n DD
            dd = 1 - eq / eq.cummax(); f = np.clip(1 - dd / n * 0.5, 0.5, 1)
        else:                      # Martingale: im DD Einsatz verdoppeln (max 100%)
            dd = 1 - eq / eq.cummax(); f = np.where(dd > n, 2.0, 1.0)
        f = pd.Series(f, index=eq.index)
        ws = w.mul(f, axis=0); ws = ws.div(np.maximum(ws.sum(1), 1.0), axis=0)
        print(f'{k:7s} {mode:9s} {n:<5}', m(run_weights(ws, d)))
