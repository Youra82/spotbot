import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import pandas as pd
from engine import load, stats
from spotbot.strategy.signal import target_weights
from spotbot.analysis.backtest import simulate
IS, OOS = ('2018-01-01', '2022-12-31'), ('2023-01-01', None)
vt = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
d = load('1d')
t0 = time.time()
tw = target_weights(d['close'], d['qvol'], vt)
print('target_weights', f'{time.time() - t0:.0f}s', flush=True)
tw.to_pickle(f'prod_tw_{vt}.pkl')
old = pd.read_pickle(f'tr_w_{vt}.pkl')
print('max |prod - research| Gewicht:', float((tw - old).abs().max().max()))
for band in (0.0, 0.01, 0.02, 0.03, 0.05):
    for cost in (0.002, 0.004):
        eq = simulate(tw, d['open'], cost=cost, band=band)
        a, b, f = stats(eq, *IS), stats(eq, *OOS), stats(eq, '2018-01-01')
        print(f"vt {vt} band {band:.2f} cost {cost}: IS pnl {a['pnl']:6.0f}% dd {a['maxdd']:6.1f} | OOS pnl {b['pnl']:5.0f}% dd {b['maxdd']:6.1f} | FULL cagr {f['cagr']:5.1f} dd {f['maxdd']:6.1f} sh {f['sharpe']:.2f}", flush=True)
