import sys
from engine import load, run_weights, stats
from strategies import *
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
def show(name, w, d):
    eq = run_weights(w, d)
    a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
    print(f"{name:34s} IS pnl {a['pnl']:8.0f}% dd {a['maxdd']:6.1f} | OOS pnl {b['pnl']:6.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:6.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f}")
d = load('1d')
print('Universum:', d['close'].shape[1], 'Coins')
show('BuyHold BTC', buy_hold(d), d)
show('BTC>SMA50', btc_trend(d, 50), d)
for lt in (10, 20, 30):
    show(f'Rotation liq{lt}', trend_rotation(d, liq_top=lt), d)
    show(f'Rotation liq{lt} vt0.5', trend_rotation(d, liq_top=lt, vol_target=0.5), d)
# Ohne die groessten Hindsight-Gewinner
d2 = load('1d', exclude=('SOL', 'DOGE', 'INJ', 'AVAX', 'BNB', 'SHIB', 'LUNA', 'FTM', 'MATIC'))
show('Rotation liq20 OHNE Top-Gewinner', trend_rotation(d2), d2)
show('  dito vt0.5', trend_rotation(d2, vol_target=0.5), d2)
