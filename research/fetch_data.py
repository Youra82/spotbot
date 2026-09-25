"""Laedt lange Spot-OHLCV-Historie (Binance, oeffentlich) fuer die Forschung.
Binance hat Daten ab 2017 -> Baerenmaerkte 2018 und 2022 sind abgedeckt.
Live-Handel erfolgt spaeter auf Bitget-Spot (Preise praktisch identisch)."""
import os, sys, time
import ccxt
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
SYMBOLS = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'LTC', 'TRX', 'XLM', 'LINK', 'DOGE', 'ETC',
           'ATOM', 'BCH', 'SOL', 'AVAX', 'DOT', 'NEAR', 'UNI', 'AAVE', 'FIL', 'EOS', 'NEO',
           'VET', 'ALGO', 'HBAR', 'INJ', 'SUI', 'APT', 'ARB', 'OP']


def fetch(ex, symbol, tf, since_iso='2017-08-01T00:00:00Z'):
    tf_ms = ex.parse_timeframe(tf) * 1000
    since = ex.parse8601(since_iso)
    rows = []
    while since < ex.milliseconds():
        for attempt in range(5):
            try:
                o = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
                break
            except Exception as e:
                print('  retry', e); time.sleep(3)
        else:
            raise RuntimeError(f'fetch failed {symbol} {tf}')
        if not o:
            # Leere Zwischenantwort vor dem Listing -> vorspulen statt abbrechen
            if not rows:
                since += tf_ms * 1000
                continue
            break
        rows.extend(o)
        since = o[-1][0] + tf_ms
        if len(o) < 2:
            break
    df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df = df.drop_duplicates('ts').sort_values('ts')
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    return df.set_index('ts')


if __name__ == '__main__':
    tfs = sys.argv[1:] or ['1d', '4h']
    ex = ccxt.binance({'enableRateLimit': True})
    ex.load_markets()
    for s in SYMBOLS:
        sym = f'{s}/USDT'
        if sym not in ex.markets:
            print('fehlt', sym); continue
        for tf in tfs:
            path = os.path.join(OUT, f'{s}_{tf}.csv')
            if os.path.exists(path):
                continue
            df = fetch(ex, sym, tf)
            df.to_csv(path)
            print(s, tf, len(df), df.index[0].date(), df.index[-1].date())
