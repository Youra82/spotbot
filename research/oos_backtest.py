import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import numpy as np, pandas as pd
from engine import load
from spotbot.strategy.run import compute_target
from spotbot.analysis.backtest import simulate
from spotbot.strategy.portfolio import plan_trades

START = '2023-01-01'
cfg = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'settings.json'), encoding='utf-8'))['spotbot']
d = load('1d')
tw = compute_target(d['close'], d['qvol'], cfg)  # Indikatoren nutzen Historie vor 2023 nur als Aufwaermphase
tw_oos = tw.loc[pd.Timestamp(START, tz='UTC') - pd.Timedelta(days=1):]

def run(cost=0.002, delay=0):
    w = tw_oos.shift(delay).fillna(0) if delay else tw_oos
    eq = simulate(w, d['open'], cost=cost, band=cfg['rebalance_band'], start_equity=1000.0)
    return eq.dropna()

eq = run()
btc = d['open']['BTC'].reindex(eq.index)
# Gleiche Bewertungskonvention wie die Strategie: Equity[t] = Bewertung zum Open[t+2]
btc_eq = 1000.0 * d['open']['BTC'].shift(-2).reindex(eq.index) / d['open']['BTC'].shift(-1).reindex(eq.index).iloc[0]
btc_eq = btc_eq.dropna(); eq = eq.loc[btc_eq.index]

def dd(e): return (e / e.cummax() - 1).min() * 100
def cagr(e): return ((e.iloc[-1] / e.iloc[0]) ** (365.25 / (e.index[-1] - e.index[0]).days) - 1) * 100
days = (eq.index[-1] - eq.index[0]).days
print(f'OOS-Backtest V3 {eq.index[0].date()} bis {eq.index[-1].date()} ({days} Tage), Start 1000 USDT\n')
print(f"{'':22s} {'V3':>12s} {'BTC halten':>12s}")
print(f"{'Endkapital (USDT)':22s} {eq.iloc[-1]:12,.0f} {btc_eq.iloc[-1]:12,.0f}")
print(f"{'Gewinn':22s} {(eq.iloc[-1]/1000-1)*100:11.0f}% {(btc_eq.iloc[-1]/1000-1)*100:11.0f}%")
print(f"{'CAGR':22s} {cagr(eq):11.1f}% {cagr(btc_eq):11.1f}%")
print(f"{'Max Drawdown':22s} {dd(eq):11.1f}% {dd(btc_eq):11.1f}%")
r, rb = eq.pct_change().dropna(), btc_eq.pct_change().dropna()
print(f"{'Sharpe':22s} {r.mean()/r.std()*np.sqrt(365):12.2f} {rb.mean()/rb.std()*np.sqrt(365):12.2f}")
print(f"{'Vorsprung vs BTC':22s} {(eq.iloc[-1]/btc_eq.iloc[-1]-1)*100:+11.0f}%")

# Trades / Exposure
w = tw_oos.loc[eq.index]
print(f"\nØ investiert: {w.sum(1).mean()*100:.0f}% | Tage 100% USDT: {(w.sum(1) < 0.01).mean()*100:.0f}% | Ø Anzahl Coins (>2%): {(w > 0.02).sum(1).mean():.1f}")
top = w.mean().sort_values(ascending=False).head(10)
print('Meistgehaltene Coins (Ø Gewicht):', ', '.join(f'{k} {v*100:.1f}%' for k, v in top.items()))

print('\nJahre:')
for y in sorted(set(eq.index.year)):
    e, b = eq[eq.index.year == y], btc_eq[btc_eq.index.year == y]
    prev_e = eq[eq.index.year < y]; prev_b = btc_eq[btc_eq.index.year < y]
    e0 = prev_e.iloc[-1] if len(prev_e) else 1000.0; b0 = prev_b.iloc[-1] if len(prev_b) else 1000.0
    print(f'  {y}: V3 {(e.iloc[-1]/e0-1)*100:+6.0f}% (DD {dd(pd.concat([pd.Series([e0]), e]).reset_index(drop=True)):5.1f}%) | BTC {(b.iloc[-1]/b0-1)*100:+6.0f}%')

print('\nMonate (V3 / BTC):')
me = eq.resample('ME').last(); mb = btc_eq.resample('ME').last()
me = pd.concat([pd.Series([1000.0], index=[me.index[0] - pd.offsets.MonthEnd(1)]), me]).pct_change().dropna() * 100
mb = pd.concat([pd.Series([1000.0], index=[mb.index[0] - pd.offsets.MonthEnd(1)]), mb]).pct_change().dropna() * 100
tab = pd.DataFrame({'V3': me, 'BTC': mb})
tab['Jahr'] = tab.index.year; tab['Mon'] = tab.index.month
for y, g in tab.groupby('Jahr'):
    print(f'  {y}: ' + ' '.join(f'{m:02d}:{v:+4.0f}/{b:+4.0f}' for m, v, b in zip(g.Mon, g.V3, g.BTC)))
print(f'  Positive Monate: V3 {(tab.V3 > 0).mean()*100:.0f}% | BTC {(tab.BTC > 0).mean()*100:.0f}% | Monate V3 besser als BTC: {(tab.V3 > tab.BTC).mean()*100:.0f}%')

# Drawdown-Episoden
e = eq.copy(); ddser = e / e.cummax() - 1
print('\nGroesste Drawdowns V3:')
for _ in range(3):
    t = ddser.idxmin(); v = ddser.min(); pk = e.loc[:t].idxmax()
    rec = e.loc[t:][e.loc[t:] >= e.loc[pk]]; end = rec.index[0].date() if len(rec) else 'noch nicht erholt'
    print(f'  {pk.date()} -> {t.date()}: {v*100:.1f}% (erholt: {end})')
    ddser.loc[pk:(rec.index[0] if len(rec) else e.index[-1])] = 0

# Stress
print('\nStress im OOS:')
for name, kw in (('doppelte Kosten', dict(cost=0.004)), ('1 Tag Verzug', dict(delay=1)), ('dreifache Kosten', dict(cost=0.006))):
    x = run(**kw).loc[btc_eq.index]
    print(f'  {name:18s} Endkapital {x.iloc[-1]:8,.0f} USDT ({(x.iloc[-1]/1000-1)*100:+.0f}%) DD {dd(x):.1f}% | vs BTC {(x.iloc[-1]/btc_eq.iloc[-1]-1)*100:+.0f}%')
out = os.path.join(os.path.dirname(__file__), '..', 'artifacts', 'oos_equity.csv')
os.makedirs(os.path.dirname(out), exist_ok=True)
pd.DataFrame({'V3': eq, 'BTC_halten': btc_eq}).to_csv(out)
