"""Ereignisgenaue Stunden-Simulatoren fuer DCA-Martingale und Spot-Grid (Forschung).
Limit-Orders: Gebuehr FEE je Ausfuehrung (Maker ~0.1%), keine Slippage. Markt-Orders: FEE + SLIP."""
import numpy as np
import pandas as pd

FEE = 0.001
SLIP = 0.001


def load_1h(sym):
    df = pd.read_csv(f'data/{sym}_1h.csv', index_col=0, parse_dates=True)
    gap = df.index.to_series().diff() > pd.Timedelta(days=2)
    if gap.any():
        df = df[df.index < gap[gap].index[0]]
    return df


def dca_martingale(df, base_frac=0.05, so_step=0.02, step_scale=1.2, vol_scale=1.5, max_so=6, tp=0.015,
                   sl=None, regime=None):
    """3Commas-artiger DCA-Bot. Kapital 1.0; Leiter so skaliert, dass alle Orders = 100% Kapital.
    regime: bool-Series (stuendlich, bereits verzoegert) -> neue Zyklen nur wenn True.
    Rueckgabe: stuendliche Equity."""
    sizes = np.array([vol_scale ** k for k in range(max_so + 1)])
    sizes = sizes / sizes.sum()  # Anteile am Zyklus-Kapital
    devs = np.cumsum([0] + [so_step * step_scale ** k for k in range(max_so)])  # Abstand je Order vom Einstieg
    O, H, L, C = (df[c].values for c in ('open', 'high', 'low', 'close'))
    reg = regime.reindex(df.index).fillna(False).values if regime is not None else np.ones(len(df), bool)
    cash = 1.0; qty = 0.0; cost = 0.0; entry = None; k = 0; cyc_cap = 0.0
    eq = np.empty(len(df))
    for t in range(len(df)):
        if entry is None:
            if reg[t]:
                cyc_cap = cash
                px = O[t] * (1 + SLIP)
                spend = cyc_cap * sizes[0]
                qty = spend * (1 - FEE) / px; cost = spend; cash -= spend; entry = O[t]; k = 1
        else:
            avg = cost / (qty / (1 - FEE)) if qty > 0 else entry
            tp_px = cost / qty * (1 + tp)
            if H[t] >= tp_px:  # Take-Profit (Limit)
                cash += qty * tp_px * (1 - FEE); qty = 0; cost = 0; entry = None
            elif sl is not None and L[t] <= cost / qty * (1 - sl):
                px = cost / qty * (1 - sl) * (1 - SLIP)
                cash += qty * px * (1 - FEE); qty = 0; cost = 0; entry = None
            else:
                while k <= max_so and L[t] <= entry * (1 - devs[k]):
                    px = entry * (1 - devs[k])
                    spend = min(cyc_cap * sizes[k], cash)
                    qty += spend * (1 - FEE) / px; cost += spend; cash -= spend; k += 1
        eq[t] = cash + qty * C[t]
    return pd.Series(eq, index=df.index)


def grid(df, width=0.3, n_levels=20, reset_days=30, regime=None, stop_below=None):
    """Spot-Grid, geometrisch, um aktuellen Kurs zentriert (+-width/2 in Log). Alle reset_days
    (oder wenn Kurs die Range verlaesst) Neuaufbau zum Marktpreis. regime False -> alles verkaufen,
    kein Grid. Pfad je Kerze: O->L->H->C wenn gruen, O->H->L->C wenn rot."""
    O, H, L, C = (df[c].values for c in ('open', 'high', 'low', 'close'))
    reg = regime.reindex(df.index).fillna(False).values if regime is not None else np.ones(len(df), bool)
    idx = df.index
    cash = 1.0; eq = np.empty(len(df))
    lv = None; hold = None; q = None; built = None
    reset_h = int(reset_days * 24)

    def liquidate(price):
        nonlocal cash, hold
        if hold is not None:
            cash += (q * hold).sum() * price * (1 - FEE - SLIP)
            hold = None

    def build(price):
        nonlocal lv, hold, q, cash
        lv = price * np.exp(np.linspace(-width / 2, width / 2, n_levels + 1))
        slot_cash = cash / n_levels
        q = slot_cash / lv[:-1]  # Menge je Slot (Kauf bei lv[i])
        hold = lv[:-1] >= price  # Slots ueber Kurs halten Coin (sofort gekauft)
        buy_cost = (q * hold).sum() * price * (1 + FEE + SLIP)
        cash -= buy_cost

    for t in range(len(df)):
        if not reg[t]:
            liquidate(O[t]); lv = None
        elif lv is None or t - built >= reset_h or O[t] > lv[-1] or O[t] < lv[0]:
            liquidate(O[t]); build(O[t]); built = t
        if lv is not None:
            path = (O[t], L[t], H[t], C[t]) if C[t] >= O[t] else (O[t], H[t], L[t], C[t])
            for a, b in zip(path[:-1], path[1:]):
                if b < a:  # faellt: Kauf-Slots mit a > lv[i] >= b
                    s = (~hold) & (lv[:-1] <= a) & (lv[:-1] >= b)
                    cash -= (q[s] * lv[:-1][s]).sum() * (1 + FEE); hold = hold | s
                else:      # steigt: Verkauf-Slots mit a < lv[i+1] <= b
                    s = hold & (lv[1:] >= a) & (lv[1:] <= b)
                    cash += (q[s] * lv[1:][s]).sum() * (1 - FEE); hold = hold & ~s
        eq[t] = cash + ((q * hold).sum() * C[t] if hold is not None else 0.0)
    return pd.Series(eq, index=idx)


def daily_stats(eq, start='2018-01-01', end=None):
    e = eq.resample('1D').last().loc[start:end].dropna()
    e = e / e.iloc[0]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return dict(mult=e.iloc[-1], cagr=(e.iloc[-1] ** (1 / yrs) - 1) * 100, dd=(e / e.cummax() - 1).min() * 100)
