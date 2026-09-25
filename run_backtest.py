# run_backtest.py
"""Backtest mit DERSELBEN Signal-/Umschichtlogik wie live.
Daten: research/data (Binance-Spot-Historie ab 2017, siehe research/fetch_data.py).

  python run_backtest.py                   # Werte aus settings.json
  python run_backtest.py --vol-target 0.7 --band 0.02 --cost 0.004
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'research'))

from engine import load, stats  # noqa: E402
from spotbot.analysis.backtest import simulate  # noqa: E402
from spotbot.strategy.run import compute_target  # noqa: E402


def main():
    cfg = json.load(open(os.path.join(ROOT, 'settings.json'), encoding='utf-8'))['spotbot']
    ap = argparse.ArgumentParser()
    ap.add_argument('--vol-target', type=float, default=cfg['vol_target'])
    ap.add_argument('--core-share', type=float, default=cfg.get('core_share', 0.0))
    ap.add_argument('--band', type=float, default=cfg['rebalance_band'])
    ap.add_argument('--cost', type=float, default=0.002, help='Gebuehr+Slippage je Seite')
    ap.add_argument('--start', default='2018-01-01')
    ap.add_argument('--oos', default='2023-01-01')
    a = ap.parse_args()

    d = load('1d')
    print(f"{d['close'].shape[1]} Coins (inkl. delisteter), berechne Zielgewichte ...", flush=True)
    tw = compute_target(d['close'], d['qvol'], dict(cfg, vol_target=a.vol_target, core_share=a.core_share))
    eq = simulate(tw, d['open'], cost=a.cost, band=a.band).loc[a.start:]
    for name, s, e in (('IS', a.start, a.oos), ('OOS', a.oos, None), ('GESAMT', a.start, None)):
        r = stats(eq, s, e)
        print(f"{name:7s} PnL {r['pnl']:8.1f}%  CAGR {r['cagr']:6.1f}%  MaxDD {r['maxdd']:6.1f}%  Sharpe {r['sharpe']:.2f}")
    out = os.path.join(ROOT, 'artifacts', 'backtest_equity.csv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    eq.to_csv(out)
    print('Equity-Kurve:', out)


if __name__ == '__main__':
    main()
