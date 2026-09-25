import numpy as np
import pandas as pd


def synthetic_market(n_days=400, coins=('BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'DOGE'), seed=1, end=None):
    rng = np.random.default_rng(seed)
    end = end if end is not None else (pd.Timestamp.now(tz='UTC').normalize() - pd.Timedelta(days=1))
    idx = pd.date_range(end=end, periods=n_days, freq='D')
    trend = np.sin(np.linspace(0, 6, n_days)) * 0.004
    close, qvol = {}, {}
    for k, c in enumerate(coins):
        r = trend + rng.normal(0.0005, 0.03 + 0.005 * k, n_days)
        close[c] = 100 * np.exp(np.cumsum(r)) * (k + 1)
        qvol[c] = rng.uniform(1e6, 5e6, n_days) * (len(coins) - k)
    return pd.DataFrame(close, index=idx), pd.DataFrame(qvol, index=idx)
