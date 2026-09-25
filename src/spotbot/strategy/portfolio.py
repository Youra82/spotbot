# src/spotbot/strategy/portfolio.py
"""Umschicht-Logik (EINE Funktion fuer Live und Backtest).
Ein Coin wird nur gehandelt, wenn
  - er komplett raus soll (Ziel 0, Bestand > 0) oder neu rein (Bestand 0, Ziel > 0), oder
  - die Abweichung |Ziel-Gewicht - Ist-Gewicht| > band ist,
und der Orderwert >= min_trade_usdt ist (Bitget-Mindestorder / Staub)."""
import numpy as np


def plan_trades(target_w: np.ndarray, hold_value: np.ndarray, equity: float, band: float,
                min_trade_usdt: float = 0.0) -> np.ndarray:
    """Gewuenschte Wertaenderung je Coin in USDT (+ kaufen, - verkaufen)."""
    target_w = np.asarray(target_w, dtype=float)
    hold_value = np.asarray(hold_value, dtype=float)
    if equity <= 0:
        return np.zeros_like(hold_value)
    diff = target_w * equity - hold_value
    cur_w = hold_value / equity
    full_exit = (target_w <= 1e-9) & (hold_value > 0)
    new_entry = (hold_value <= 1e-9) & (target_w > 1e-9)
    trade = full_exit | new_entry | (np.abs(target_w - cur_w) > band)
    trade &= np.abs(diff) >= min_trade_usdt
    return np.where(trade, diff, 0.0)
