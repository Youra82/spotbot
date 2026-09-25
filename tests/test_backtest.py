import numpy as np
import pandas as pd
from spotbot.analysis.backtest import simulate
from helpers import synthetic_market


def test_all_cash_is_flat():
    c, _ = synthetic_market(n_days=50)
    eq = simulate(pd.DataFrame(0.0, index=c.index, columns=c.columns), c, cost=0.002)
    assert np.allclose(eq.dropna(), 1000.0)


def test_full_btc_tracks_price_minus_cost():
    c, _ = synthetic_market(n_days=50)
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w['BTC'] = 1.0
    eq = simulate(w, c, cost=0.002, start_equity=1000)
    # Kauf zum Open[1] mit Kosten, Bewertung Open[t+2]
    expected = 1000 / 1.002 * c['BTC'].iloc[-1] / c['BTC'].iloc[1]
    assert np.isclose(eq.iloc[-2], expected, rtol=1e-9)
