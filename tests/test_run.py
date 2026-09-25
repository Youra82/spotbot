"""run.py mit Fake-Exchange: keine echten API-Calls, keine Orders."""
import numpy as np
import pandas as pd
import pytest
from spotbot.strategy import run as runmod
from helpers import synthetic_market

COINS = ('BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'DOGE')
SMALL = dict(btc_sma=[50], coin_sma=[20], mom=[14], top_k=[3], rebal=[7], liq_top=[6], breadth_min=[0.0])


class FakeEx:
    def __init__(self, close, qvol, balances, fail_balance=False):
        self.close, self.qvol, self.balances, self.fail_balance = close, qvol, balances, fail_balance
        self.markets = {f'{c}/USDT': {'active': True} for c in close.columns}
        self.orders = []

    def fetch_ohlcv_df(self, sym, tf, limit):
        c = sym.split('/')[0]
        return pd.DataFrame({'close': self.close[c], 'volume': self.qvol[c] / self.close[c]}).iloc[-limit:]

    def fetch_balances(self):
        if self.fail_balance:
            raise RuntimeError('API down')
        return dict(self.balances)

    def fetch_tickers(self, syms):
        return {s: {'last': float(self.close[s.split('/')[0]].iloc[-1])} for s in syms}

    def fetch_free(self, a):
        return self.balances.get(a, 0.0)

    def market_buy_cost(self, s, usdt):
        self.orders.append(('buy', s, usdt))

    def market_sell(self, s, amt):
        self.orders.append(('sell', s, amt))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(runmod, 'STATE_PATH', str(tmp_path / 'state.json'))
    monkeypatch.setattr(runmod, 'TRADES_PATH', str(tmp_path / 'trades.csv'))
    monkeypatch.setattr(runmod, 'EQUITY_PATH', str(tmp_path / 'equity.csv'))
    monkeypatch.setattr(runmod, 'send_message', lambda *a, **k: None)
    monkeypatch.setattr(runmod.time, 'sleep', lambda s: None)
    orig = runmod.target_weights
    monkeypatch.setattr(runmod, 'target_weights', lambda c, q, vt, grid=None: orig(c, q, vt, grid=SMALL))
    return tmp_path


def settings(dry):
    return {'spotbot': dict(dry_run=dry, quote='USDT', vol_target=0.6, rebalance_band=0.02,
                            min_trade_usdt=5, history_days=200, universe=list(COINS))}


def bull():
    c, q = synthetic_market(n_days=300, coins=COINS, seed=3)
    return c * np.exp(np.linspace(0, 2, len(c)))[:, None], q


def test_live_mode_places_orders_and_is_idempotent(env, monkeypatch):
    c, q = bull()
    fx = FakeEx(c, q, {'USDT': 1000.0})
    monkeypatch.setattr(runmod, 'SpotExchange', lambda acc: fx)
    runmod.run(settings(False), {'spotbot': {}, 'telegram': {}})
    buys = [o for o in fx.orders if o[0] == 'buy']
    assert buys
    assert sum(o[2] for o in buys) <= 1000
    n = len(fx.orders)
    runmod.run(settings(False), {'spotbot': {}, 'telegram': {}})  # gleiche Kerze -> nichts
    assert len(fx.orders) == n


def test_dry_run_places_no_orders(env, monkeypatch):
    c, q = bull()
    fx = FakeEx(c, q, {'USDT': 1000.0})
    monkeypatch.setattr(runmod, 'SpotExchange', lambda acc: fx)
    runmod.run(settings(True), {'spotbot': {}, 'telegram': {}})
    assert fx.orders == []
    assert (env / 'trades.csv').exists()


def test_balance_api_error_aborts_without_orders(env, monkeypatch):
    c, q = bull()
    fx = FakeEx(c, q, {'USDT': 1000.0}, fail_balance=True)
    monkeypatch.setattr(runmod, 'SpotExchange', lambda acc: fx)
    with pytest.raises(RuntimeError):
        runmod.run(settings(False), {'spotbot': {}, 'telegram': {}})
    assert fx.orders == []


def test_stale_candle_never_trades(env, monkeypatch):
    old_end = pd.Timestamp.now(tz='UTC').normalize().tz_localize(None) - pd.Timedelta(days=5)
    c, q = synthetic_market(n_days=300, coins=COINS, end=old_end)
    fx = FakeEx(c, q, {'USDT': 1000.0})
    monkeypatch.setattr(runmod, 'SpotExchange', lambda acc: fx)
    try:
        runmod.run(settings(False), {'spotbot': {}, 'telegram': {}})
    except RuntimeError:
        pass
    assert fx.orders == []


def test_full_exit_sells_everything_in_bear(env, monkeypatch):
    c, q = synthetic_market(n_days=300, coins=COINS, seed=3)
    c = c * np.exp(np.linspace(0, -3, len(c)))[:, None]  # Baerenmarkt -> Regime aus
    fx = FakeEx(c, q, {'USDT': 100.0, 'SOL': 2.0})
    monkeypatch.setattr(runmod, 'SpotExchange', lambda acc: fx)
    runmod.run(settings(False), {'spotbot': {}, 'telegram': {}})
    sells = [o for o in fx.orders if o[0] == 'sell']
    assert sells and sells[0][1] == 'SOL/USDT' and sells[0][2] == 2.0
    assert not [o for o in fx.orders if o[0] == 'buy']
