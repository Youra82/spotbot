# src/spotbot/utils/exchange.py
"""Bitget-SPOT-Wrapper (kein Hebel, keine Futures).
API-Fehler werden NIE zu leeren/0-Ergebnissen verschluckt (siehe mbot-Liquidations-Bug):
wer den Kontostand nicht sicher kennt, darf nicht handeln -> Exception nach oben."""
import logging
import time

import ccxt
import pandas as pd

logger = logging.getLogger(__name__)


def _retry_call(fn, *a, tries=3, **kw):
    last = None
    for k in range(tries):
        try:
            return fn(*a, **kw)
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
            last = e
            logger.warning(f"{getattr(fn, '__name__', fn)} fehlgeschlagen ({e}), Retry {k + 1}/{tries}")
            time.sleep(2 * (k + 1))
    raise last


def fetch_ohlcv_df(ex, symbol: str, timeframe: str = '1d', limit: int = 200) -> pd.DataFrame:
    """Letzte `limit` ABGESCHLOSSENE Kerzen, paginiert vorwaerts (laufende Kerze wird entfernt)."""
    tf_ms = ex.parse_timeframe(timeframe) * 1000
    now = ex.milliseconds()
    since = now - tf_ms * (limit + 2)
    rows = []
    while since < now:
        o = _retry_call(ex.fetch_ohlcv, symbol, timeframe, since=since, limit=200)
        if not o:
            break
        rows.extend(o)
        nxt = o[-1][0] + tf_ms
        if nxt <= since:
            break
        since = nxt
    if not rows:
        raise RuntimeError(f'Keine OHLCV-Daten fuer {symbol}')
    df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df = df.drop_duplicates('ts').sort_values('ts')
    df = df[df.ts + tf_ms <= now]
    df['ts'] = pd.to_datetime(df.ts, unit='ms', utc=True)
    return df.set_index('ts').iloc[-limit:]


class PublicData:
    """Oeffentliche Marktdaten einer Signal-Boerse (Standard Binance = Datenquelle des Backtests).
    Liquiditaetsrangliste und Signale entsprechen damit exakt dem Backtest."""

    def __init__(self, exchange_id: str = 'binance'):
        self.exchange = getattr(ccxt, exchange_id)({'enableRateLimit': True})
        self.markets = _retry_call(self.exchange.load_markets)

    def fetch_ohlcv_df(self, symbol: str, timeframe: str = '1d', limit: int = 200) -> pd.DataFrame:
        return fetch_ohlcv_df(self.exchange, symbol, timeframe, limit)


class SpotExchange:
    def __init__(self, account_config: dict):
        self.exchange = ccxt.bitget({
            'apiKey': account_config.get('apiKey'),
            'secret': account_config.get('secret'),
            'password': account_config.get('password'),
            'options': {'defaultType': 'spot'},
            'enableRateLimit': True,
        })
        self.markets = self._retry(self.exchange.load_markets)

    def _retry(self, fn, *a, tries=3, **kw):
        last = None
        for k in range(tries):
            try:
                return fn(*a, **kw)
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
                last = e
                logger.warning(f"{getattr(fn, '__name__', fn)} fehlgeschlagen ({e}), Retry {k + 1}/{tries}")
                time.sleep(2 * (k + 1))
        raise last

    # --- Daten ---
    def fetch_ohlcv_df(self, symbol: str, timeframe: str = '1d', limit: int = 200) -> pd.DataFrame:
        return fetch_ohlcv_df(self.exchange, symbol, timeframe, limit)

    def fetch_tickers(self, symbols):
        return self._retry(self.exchange.fetch_tickers, symbols)

    # --- Konto ---
    def fetch_balances(self) -> dict:
        """{asset: total} fuer alle Assets mit Bestand > 0. Wirft bei API-Fehler."""
        b = self._retry(self.exchange.fetch_balance)
        return {k: float(v) for k, v in (b.get('total') or {}).items() if v and float(v) > 0}

    def fetch_free(self, asset: str) -> float:
        b = self._retry(self.exchange.fetch_balance)
        return float((b.get('free') or {}).get(asset) or 0.0)

    # --- Orders ---
    def min_cost(self, symbol: str) -> float:
        c = self.markets[symbol].get('limits', {}).get('cost', {}).get('min')
        return float(c) if c else 1.0

    def market_buy_cost(self, symbol: str, usdt: float):
        """Kauft fuer `usdt` USDT (Quote-Betrag)."""
        logger.info(f'MARKET BUY {symbol} fuer {usdt:.2f} USDT')
        return self.exchange.create_market_buy_order_with_cost(symbol, usdt)

    def market_sell(self, symbol: str, amount: float):
        amt = float(self.exchange.amount_to_precision(symbol, amount))
        logger.info(f'MARKET SELL {amt} {symbol}')
        return self.exchange.create_order(symbol, 'market', 'sell', amt)
