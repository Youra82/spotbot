import ccxt, os
from fetch_data import fetch, OUT
ex = ccxt.binance({'enableRateLimit': True}); ex.load_markets()
for s in 'BTC ETH SOL BNB XRP ADA DOGE LINK LTC AVAX DOT LUNA FTT MATIC ATOM NEAR'.split():
    p = os.path.join(OUT, f'{s}_1h.csv')
    if os.path.exists(p): continue
    try:
        df = fetch(ex, f'{s}/USDT', '1h'); df.to_csv(p); print(s, len(df), flush=True)
    except Exception as e: print(s, 'ERR', e, flush=True)
