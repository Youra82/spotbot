import ccxt, os
from fetch_data import fetch, OUT
ex = ccxt.binance({'enableRateLimit': True}); ex.load_markets()
cand = 'LUNA FTT WAVES MATIC FTM ZIL OMG IOTA QTUM ZEC DASH XMR ICP THETA SAND MANA AXS CHZ GRT SHIB KSM MKR COMP SNX CRV SUSHI 1INCH XTZ ONT BAT ICX KAVA EGLD RUNE SRM BTT HOT CELO SXP CAKE'.split()
for s in cand:
    p = os.path.join(OUT, f'{s}_4h.csv')
    if os.path.exists(p): continue
    try:
        df = fetch(ex, f'{s}/USDT', '4h')
        if len(df): df.to_csv(p); print(s, len(df), flush=True)
    except Exception as e: print(s, 'ERR', e, flush=True)
