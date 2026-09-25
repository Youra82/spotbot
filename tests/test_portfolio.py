import numpy as np
from spotbot.strategy.portfolio import plan_trades


def test_entry_and_exit_always_trade():
    d = plan_trades(np.array([0.3, 0.0]), np.array([0.0, 100.0]), 1000, band=0.5, min_trade_usdt=5)
    assert d[0] == 300 and d[1] == -100


def test_band_suppresses_small_rebalance():
    d = plan_trades(np.array([0.31]), np.array([300.0]), 1000, band=0.02, min_trade_usdt=5)
    assert d[0] == 0
    d = plan_trades(np.array([0.35]), np.array([300.0]), 1000, band=0.02, min_trade_usdt=5)
    assert np.isclose(d[0], 50)


def test_min_trade_blocks_dust():
    d = plan_trades(np.array([0.003]), np.array([0.0]), 1000, band=0.0, min_trade_usdt=5)
    assert d[0] == 0


def test_zero_equity_no_trades():
    assert not plan_trades(np.array([0.5]), np.array([0.0]), 0, 0.02).any()
