"""Portfolio-Backtest-Engine fuer Long-only-Spot (Forschung).
Konvention: Gewichte werden mit Daten bis Close[t] berechnet und zum Open[t+1]
umgesetzt; Rendite der Haltedauer = Open[t+2]/Open[t+1]-1. Kein Lookahead."""
import os, glob
import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
COST = 0.002  # 0.1% Gebuehr + 0.1% Slippage je Seite


def load(tf='1d', exclude=()):
    closes, opens, highs, lows, vols = {}, {}, {}, {}, {}
    for p in sorted(glob.glob(os.path.join(DATA, f'*_{tf}.csv'))):
        s = os.path.basename(p).split('_')[0]
        if s in exclude:
            continue
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        df = df[df.index < df.index.max()]  # letzte (laufende) Kerze weg
        # Datenluecke > 2 Tage = Delisting/Relisting (z.B. LUNA alt->neu): ab dort abschneiden
        gap = df.index.to_series().diff().dt.days
        if (gap > 2).any():
            df = df[df.index < gap[gap > 2].index[0]]
        closes[s], opens[s], highs[s], lows[s], vols[s] = df.close, df.open, df.high, df.low, df.close * df.volume
    f = lambda d: pd.DataFrame(d).sort_index()
    return dict(close=f(closes), open=f(opens), high=f(highs), low=f(lows), qvol=f(vols))


def run_weights(w, d, cost=COST):
    """w: Zielgewichte (Index=Datum t, berechnet bis Close t). Liefert taegl. Equity."""
    o = d['open']
    w = w.reindex(o.index).fillna(0.0)
    # Rendite von Open[t+1] -> Open[t+2], zugeordnet zu t
    r = (o.shift(-2) / o.shift(-1) - 1)
    # Coin endet (Delisting) -> Verkauf zum letzten Kurs, danach 0
    r = r.where(o.shift(-2).notna() | o.shift(-1).isna(), 0.0).fillna(0.0)
    turnover = (w - w.shift(1).fillna(0.0)).abs().sum(axis=1)
    # Drift der Gewichte ignoriert (taegliche Rebalance-Naeherung nur bei Aenderung) -> exakte Simulation:
    return _simulate(w, r, cost)


def _simulate(w, r, cost):
    """Exakte Simulation mit Drift: rebalanciert nur, wenn sich das Zielgewicht aendert."""
    W = w.values; R = r.values
    n, m = W.shape
    prevW = np.vstack([np.zeros((1, m)), W[:-1]])
    change = (np.abs(W - prevW) > 1e-9).any(axis=1)
    eq = np.empty(n); cash = 1.0; hold = np.zeros(m)
    for t in range(n):
        if change[t]:
            total = cash + hold.sum()
            tgt = W[t] * total
            total -= np.abs(tgt - hold).sum() * cost
            hold = W[t] * total
            cash = total - hold.sum()
        hold = hold * (1 + R[t])
        eq[t] = cash + hold.sum()
    return pd.Series(eq, index=w.index)


def stats(eq, start=None, end=None):
    e = eq.loc[start:end]
    e = e / e.iloc[0]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    cagr = e.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd = (e / e.cummax() - 1).min()
    dr = e.pct_change().dropna()
    sharpe = dr.mean() / dr.std() * np.sqrt(365) if dr.std() > 0 else 0
    return dict(pnl=(e.iloc[-1] - 1) * 100, cagr=cagr * 100, maxdd=dd * 100, sharpe=sharpe)
