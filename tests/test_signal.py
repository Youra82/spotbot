import numpy as np
from spotbot.strategy.signal import target_weights, MIN_HISTORY_DAYS
from helpers import synthetic_market

SMALL = dict(btc_sma=[50], coin_sma=[20], mom=[14, 30], top_k=[2, 3], rebal=[7, 14], liq_top=[5],
             breadth_min=[0.3])


def test_weights_bounded_long_only():
    c, q = synthetic_market()
    w = target_weights(c, q, 0.6, grid=SMALL)
    assert (w.values >= 0).all()
    assert (w.sum(1) <= 1 + 1e-9).all()
    assert w.sum(1).max() > 0  # Strategie investiert ueberhaupt


def test_live_window_equals_full_backtest():
    """Kern-Eigenschaft: kurzes Live-Fenster liefert dieselben Zielgewichte wie der lange Backtest."""
    c, q = synthetic_market(n_days=500)
    full = target_weights(c, q, 0.6, grid=SMALL)
    for end in (300, 377, 450, 499):
        a = end - MIN_HISTORY_DAYS - 40
        win = target_weights(c.iloc[a:end + 1], q.iloc[a:end + 1], 0.6, grid=SMALL)
        assert np.allclose(win.iloc[-1].values, full.iloc[end].values, atol=1e-12)


def test_no_lookahead():
    """Aenderung ZUKUENFTIGER Kurse darf das heutige Ziel nicht aendern."""
    c, q = synthetic_market(n_days=400)
    base = target_weights(c, q, 0.6, grid=SMALL).iloc[350]
    c2 = c.copy()
    c2.iloc[351:] *= 3
    assert np.allclose(target_weights(c2, q, 0.6, grid=SMALL).iloc[350], base)


def test_core_satellite_live_window_equals_full_backtest():
    from spotbot.strategy.signal import core_satellite_weights, CORE_HISTORY_DAYS
    c, q = synthetic_market(n_days=CORE_HISTORY_DAYS + 200)
    full = core_satellite_weights(c, q, 0.3, 10.0, grid=SMALL)
    assert (full.sum(1) <= 1 + 1e-9).all() and (full.values >= 0).all()
    for end in (CORE_HISTORY_DAYS + 50, CORE_HISTORY_DAYS + 199):
        a = end - CORE_HISTORY_DAYS + 1
        win = core_satellite_weights(c.iloc[a:end + 1], q.iloc[a:end + 1], 0.3, 10.0, grid=SMALL)
        assert np.allclose(win.iloc[-1].values, full.iloc[end].values, atol=1e-9)


def test_fast_momentum_live_window_equals_full_backtest():
    from spotbot.strategy.signal import fast_momentum_weights, CORE_HISTORY_DAYS
    small = dict(SMALL, rebal=[7])
    c, q = synthetic_market(n_days=CORE_HISTORY_DAYS + 200)
    full = fast_momentum_weights(c, q, 1.5, grid=small)
    assert (full.values >= -1e-12).all() and (full.sum(1) <= 1 + 1e-9).all()
    for end in (CORE_HISTORY_DAYS + 60, CORE_HISTORY_DAYS + 199):
        a = end - CORE_HISTORY_DAYS + 1
        win = fast_momentum_weights(c.iloc[a:end + 1], q.iloc[a:end + 1], 1.5, grid=small)
        assert np.allclose(win.iloc[-1].values, full.iloc[end].values, atol=1e-9)
