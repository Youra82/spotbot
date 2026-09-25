import numpy as np
import pandas as pd


def trend_rotation(d, btc_sma=100, coin_sma=50, mom=30, top_k=3, rebal=7,
                   vol_target=None, vol_win=30, liq_top=20, daily_exit=True, weighting='invvol'):
    """Dual-Momentum-Rotation long-only:
    Regime: BTC Close > SMA(btc_sma). Kandidaten: Close > SMA(coin_sma), Momentum>0,
    unter den liquidesten `liq_top` Coins. Top-K nach Momentum, Gewicht invers zur Vola,
    Gesamtexposure per Vol-Targeting skaliert (max 100%, kein Hebel)."""
    c = d['close']
    sma = c.rolling(coin_sma, min_periods=coin_sma).mean()
    mo = c / c.shift(mom) - 1
    rets = c.pct_change(fill_method=None)
    vol = rets.rolling(vol_win, min_periods=vol_win).std() * np.sqrt(365)
    liq = d['qvol'].rolling(30, min_periods=30).mean()
    liq_rank = liq.rank(axis=1, ascending=False)
    btc = c['BTC']
    regime = (btc > btc.rolling(btc_sma).mean()) if btc_sma else pd.Series(True, index=c.index)
    elig = (c > sma) & (mo > 0) & (liq_rank <= liq_top) & vol.notna()

    W = np.zeros(c.shape); cols = list(c.columns)
    cur = np.zeros(len(cols))
    for i in range(len(c)):
        e = elig.iloc[i].values
        if not regime.iloc[i]:
            cur = np.zeros(len(cols))
        elif i % rebal == 0:
            m = np.where(e, mo.iloc[i].values, -np.inf)
            idx = [j for j in np.argsort(-m)[:top_k] if np.isfinite(m[j])]
            cur = np.zeros(len(cols))
            if idx:
                v = vol.iloc[i].values[idx]
                ww = (1 / v) if weighting == 'invvol' else np.ones(len(idx))
                ww = ww / ww.sum()
                # Portfolio-Vola-Schaetzung (Korrelation ~ grob per Kovarianz)
                if vol_target:
                    sub = rets.iloc[max(0, i - vol_win + 1):i + 1, idx].fillna(0)
                    pv = np.sqrt(ww @ (sub.cov().values * 365) @ ww)
                    ww = ww * min(1.0, vol_target / pv) if pv > 0 else ww
                else:
                    ww = ww * 1.0
                # Gleichgewicht auf K Slots: bei weniger Kandidaten nicht voll investieren? -> nein, voll
                cur[idx] = ww
        elif daily_exit:
            cur = np.where(e, cur, 0.0)
        W[i] = cur
    return pd.DataFrame(W, index=c.index, columns=cols)


def btc_trend(d, sma=100):
    c = d['close']
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w['BTC'] = (c['BTC'] > c['BTC'].rolling(sma).mean()).astype(float)
    return w


def buy_hold(d, sym='BTC'):
    c = d['close']
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w[sym] = 1.0
    return w
