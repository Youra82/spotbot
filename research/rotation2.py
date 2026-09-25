"""Rotation-Varianten: Ranking-Modi + BTC als Standard-Fueller (Forschung)."""
import numpy as np
import pandas as pd


def rotation2(P, btc_sma=50, coin_sma=20, mom=30, top_k=5, rebal=7, liq_top=15, breadth_min=0.3,
              rank='abs', skip=0, fill_btc=False, rs_gate=False, phase=0, cash_slots=True):
    """rank: 'abs' = Momentum in USD, 'rs' = Momentum gegen BTC, 'sharpe' = Momentum / Vola.
    skip: letzte `skip` Tage aus dem Momentum auslassen.
    rs_gate: Altcoin nur, wenn er BTC ueber `mom` Tage geschlagen hat.
    fill_btc: freie Slots (Regime an) gehen in BTC statt USDT."""
    C = P.C; b = P.btc
    c = P.d['close']
    m_abs = ((c.shift(skip) / c.shift(mom + skip)) - 1).values
    btc_m = m_abs[:, b:b + 1]
    m_rs = (1 + m_abs) / (1 + btc_m) - 1
    if rank == 'abs':
        score = m_abs
    elif rank == 'rs':
        score = m_rs
    else:
        score = m_abs / np.where(P.vol > 0, P.vol, np.nan)
    S = P.sma(coin_sma); B = P.sma(btc_sma)
    with np.errstate(invalid='ignore'):
        above = C > S
        elig = above & (m_abs > 0) & (P.liq_rank <= liq_top) & ~np.isnan(P.vol) & ~np.isnan(score)
        if rs_gate:
            elig &= m_rs > 0
    elig[:, b] = elig[:, b]  # BTC darf normal Kandidat sein
    inliq = (P.liq_rank <= liq_top) & ~np.isnan(S)
    breadth = (above & inliq).sum(1) / np.maximum(inliq.sum(1), 1)
    n, m = C.shape
    W = np.zeros((n, m)); cur = np.zeros(m)
    for i in range(n):
        reg = (not np.isnan(B[i, b])) and C[i, b] > B[i, b] and breadth[i] >= breadth_min
        if not reg:
            cur = np.zeros(m)
        elif (i + phase) % rebal == 0:
            sc = np.where(elig[i], score[i], -np.inf)
            idx = [j for j in np.argsort(-sc)[:top_k] if np.isfinite(sc[j])]
            cur = np.zeros(m)
            if idx:
                ww = 1 / P.vol[i, idx]; ww = ww / ww.sum() * (len(idx) / top_k if cash_slots else 1.0)
                cur[idx] = ww
            if fill_btc:
                cur[b] += 1 - cur.sum()
        else:
            keep = elig[i].copy()
            if fill_btc:
                keep[b] = True  # BTC-Fueller bleibt bis Regime aus
            cur = np.where(keep, cur, 0.0)
        W[i] = cur
    return W
