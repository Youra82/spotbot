# src/spotbot/strategy/run.py
"""spotbot Live-Lauf: einmal pro abgeschlossener UTC-Tageskerze.

1. Tageskerzen aller Universum-Coins von Bitget-Spot laden (laufende Kerze wird verworfen)
2. Zielgewichte ueber DIESELBE Funktion wie der Backtest (signal.target_weights)
3. Ist-Bestand + Equity ermitteln, Orders ueber DIESELBE Funktion (portfolio.plan_trades)
4. Erst verkaufen, dann kaufen; Telegram-Zusammenfassung
Bei unsicheren Daten (API-Fehler, veraltete Kerze, BTC fehlt) wird NICHT gehandelt."""
import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.append(os.path.join(PROJECT_ROOT, 'src'))

from spotbot.strategy.signal import (CORE_HISTORY_DAYS, ENSEMBLE_GRID, MIN_HISTORY_DAYS,  # noqa: E402
                                     core_satellite_weights, fast_momentum_weights, target_weights)
from spotbot.strategy.portfolio import plan_trades  # noqa: E402
from spotbot.utils.exchange import PublicData, SpotExchange  # noqa: E402
from spotbot.utils.telegram import send_message  # noqa: E402

ARTIFACTS = os.path.join(PROJECT_ROOT, 'artifacts')
STATE_PATH = os.path.join(ARTIFACTS, 'state.json')
TRADES_PATH = os.path.join(ARTIFACTS, 'trades.csv')
EQUITY_PATH = os.path.join(ARTIFACTS, 'equity.csv')

logger = logging.getLogger('spotbot')


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def append_csv(path, row: dict):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def fetch_universe(ex: SpotExchange, coins, quote, history_days, data=None):
    """Signaldaten von `data` (Signal-Boerse, Standard Binance wie im Backtest); handelbar nur,
    was auch auf der Ausfuehrungsboerse `ex` (Bitget) aktiv ist."""
    data = data or ex
    closes, qvols, failed = {}, {}, []
    for c in coins:
        sym = f'{c}/{quote}'
        if sym not in ex.markets or not ex.markets[sym].get('active', True) or sym not in data.markets:
            failed.append(c)
            continue
        try:
            df = data.fetch_ohlcv_df(sym, '1d', limit=history_days)
            closes[c] = df['close']
            qvols[c] = df['close'] * df['volume']
        except Exception as e:  # einzelner Coin -> ausschliessen, aber melden
            logger.warning(f'OHLCV {sym} fehlgeschlagen: {e}')
            failed.append(c)
    close = pd.DataFrame(closes).sort_index()
    qvol = pd.DataFrame(qvols).reindex(close.index)
    return close, qvol, failed


def compute_target(close, qvol, cfg) -> pd.DataFrame:
    """Gleiche Funktion wie run_backtest.py."""
    if cfg.get('strategy') == 'fast_momentum':
        return fast_momentum_weights(close, qvol, float(cfg['vol_target']), int(cfg.get('slow_sma', 150)),
                                     float(cfg.get('slow_floor', 0.5)))
    core = float(cfg.get('core_share', 0.0))
    grid = dict(ENSEMBLE_GRID, rebal=list(cfg.get('rebal_days', ENSEMBLE_GRID['rebal'])))
    if core > 0:
        return core_satellite_weights(close, qvol, core, float(cfg['vol_target']), grid=grid)
    return target_weights(close, qvol, float(cfg['vol_target']), grid=grid)


def run(settings: dict, secret: dict, force: bool = False):
    cfg = settings['spotbot']
    quote = cfg.get('quote', 'USDT')
    coins = list(cfg['universe'])
    dry = bool(cfg.get('dry_run', True))
    tg = secret.get('telegram', {})
    notify = lambda msg: send_message(tg.get('bot_token'), tg.get('chat_id'), msg)  # noqa: E731

    ex = SpotExchange(secret['spotbot'])
    sig_ex = cfg.get('signal_exchange', 'bitget')
    data = PublicData(sig_ex) if sig_ex != 'bitget' else ex
    close, qvol, failed = fetch_universe(ex, coins, quote, cfg.get('history_days', 200), data)

    # --- Datenqualitaet: lieber nicht handeln als falsch handeln ---
    if 'BTC' not in close.columns:
        raise RuntimeError('BTC-Daten fehlen -> Regime nicht bestimmbar, Abbruch.')
    if len(failed) > 0.2 * len(coins):
        raise RuntimeError(f'Zu viele Coins ohne Daten ({len(failed)}/{len(coins)}): {failed}')
    last_day = close.index[-1]
    expected = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    if last_day.date() != expected:
        if datetime.now(timezone.utc).hour < 2:  # kurz nach Mitternacht normal -> naechster Cron-Lauf
            logger.info(f'Kerze {expected} noch nicht verfuegbar (letzte: {last_day.date()}), spaeter erneut.')
            return
        raise RuntimeError(f'Letzte abgeschlossene Kerze {last_day.date()} != erwartet {expected}. Abbruch.')
    min_hist = CORE_HISTORY_DAYS if (cfg.get('core_share', 0) > 0 or cfg.get('strategy') == 'fast_momentum') else MIN_HISTORY_DAYS
    if len(close) < min_hist:
        raise RuntimeError(f'Nur {len(close)} Tage Historie (< {min_hist}).')
    # Coins ohne aktuelle Kerze nicht als Ziel zulassen
    close = close.loc[:, close.iloc[-1].notna()]
    qvol = qvol[close.columns]

    state = load_json(STATE_PATH, {}) or {}
    if not force and state.get('last_candle') == str(last_day.date()):
        logger.info(f'Kerze {last_day.date()} bereits verarbeitet.')
        return

    target = compute_target(close, qvol, cfg).iloc[-1]
    target = target[target > 1e-6].sort_values(ascending=False)
    logger.info(f'Ziel ({last_day.date()}): investiert {target.sum():.1%} ' +
                ', '.join(f'{k} {v:.1%}' for k, v in target.items()))

    # --- Ist-Zustand (wirft bei API-Fehler -> kein Handel) ---
    balances = ex.fetch_balances()
    managed = list(close.columns)
    tickers = ex.fetch_tickers([f'{c}/{quote}' for c in managed])
    px = np.array([float(tickers[f'{c}/{quote}']['last']) for c in managed])
    qty = np.array([balances.get(c, 0.0) for c in managed])
    hold_val = qty * px
    usdt = balances.get(quote, 0.0)
    equity = usdt + hold_val.sum()
    cap = cfg.get('max_capital_usdt')
    budget = min(equity, float(cap)) if cap else equity
    # Staub (unter Mindestorder) zaehlt nicht als Position
    min_trade = float(cfg.get('min_trade_usdt', 5.0))
    hold_for_plan = np.where(hold_val >= min_trade, hold_val, 0.0)

    tw = target.reindex(managed).fillna(0.0).values
    delta = plan_trades(tw, hold_for_plan, budget, float(cfg.get('rebalance_band', 0.02)), min_trade)

    orders = []
    # 1) Verkaeufe
    for j in np.where(delta < 0)[0]:
        c = managed[j]
        full_exit = tw[j] <= 1e-9
        amount = qty[j] if full_exit else min(qty[j], -delta[j] / px[j])
        orders.append(('SELL', c, amount, amount * px[j]))
        if not dry:
            try:
                if full_exit:  # exakt den freien Bestand verkaufen (Gebuehren wurden in Coin abgezogen)
                    amount = ex.fetch_free(c)
                ex.market_sell(f'{c}/{quote}', amount)
            except Exception as e:
                logger.error(f'Verkauf {c} fehlgeschlagen: {e}', exc_info=True)
                notify(f'spotbot FEHLER Verkauf {c}: {e}')
    # 2) Kaeufe (mit tatsaechlich verfuegbarem USDT)
    buys = [(j, delta[j]) for j in np.where(delta > 0)[0]]
    if buys:
        if not dry:
            time.sleep(2)
            usdt_free = ex.fetch_free(quote)
        else:
            usdt_free = usdt + sum(o[3] for o in orders)
        need = sum(v for _, v in buys)
        scale = min(1.0, usdt_free * 0.995 / need) if need > 0 else 0
        for j, v in buys:
            c = managed[j]
            cost = v * scale
            if cost < min_trade:
                continue
            orders.append(('BUY', c, cost / px[j], cost))
            if not dry:
                try:
                    ex.market_buy_cost(f'{c}/{quote}', cost)
                except Exception as e:
                    logger.error(f'Kauf {c} fehlgeschlagen: {e}', exc_info=True)
                    notify(f'spotbot FEHLER Kauf {c}: {e}')

    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for side, c, amount, value in orders:
        append_csv(TRADES_PATH, dict(time=now, candle=str(last_day.date()), side=side, coin=c,
                                     amount=f'{amount:.8f}', usdt=f'{value:.2f}', price=f'{px[managed.index(c)]:.8g}',
                                     dry_run=dry))
    append_csv(EQUITY_PATH, dict(time=now, candle=str(last_day.date()), equity_usdt=f'{equity:.2f}',
                                 invested_pct=f'{hold_val.sum() / equity * 100 if equity else 0:.1f}',
                                 target_invested_pct=f'{target.sum() * 100:.1f}', dry_run=dry))
    state.update(last_candle=str(last_day.date()), last_run=now,
                 target={k: round(float(v), 5) for k, v in target.items()})
    save_json(STATE_PATH, state)

    head = f"spotbot {'[DRY-RUN] ' if dry else ''}{last_day.date()}"
    lines = [head, f'Equity: {equity:.2f} {quote} | Ziel investiert: {target.sum():.0%}']
    if target.empty:
        lines.append('Regime AUS -> 100% USDT')
    else:
        lines.append('Ziel: ' + ', '.join(f'{k} {v:.0%}' for k, v in target.head(8).items()))
    if orders:
        lines += [f'{s} {c} {v:.2f} {quote}' for s, c, _, v in orders]
    else:
        lines.append('Keine Orders (innerhalb Band)')
    if failed:
        lines.append(f'Ohne Daten: {", ".join(failed)}')
    msg = '\n'.join(lines)
    logger.info(msg)
    if orders or cfg.get('telegram_daily_summary', True):
        notify(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true', help='auch wenn Kerze schon verarbeitet')
    args = ap.parse_args()
    os.makedirs(os.path.join(PROJECT_ROOT, 'logs'), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(os.path.join(PROJECT_ROOT, 'logs', 'spotbot.log')),
                                  logging.StreamHandler()])
    settings = load_json(os.path.join(PROJECT_ROOT, 'settings.json'))
    # Lokale, nicht versionierte Overrides (dry_run, max_capital_usdt, ...) ueberleben update.sh
    local = load_json(os.path.join(PROJECT_ROOT, 'settings.local.json'), {}) or {}
    settings['spotbot'].update(local.get('spotbot', {}))
    secret = load_json(os.path.join(PROJECT_ROOT, 'secret.json'))
    if not secret:
        raise SystemExit('secret.json fehlt')
    try:
        run(settings, secret, force=args.force)
    except Exception as e:
        logger.critical(f'Lauf abgebrochen: {e}', exc_info=True)
        tg = secret.get('telegram', {})
        send_message(tg.get('bot_token'), tg.get('chat_id'), f'spotbot ABBRUCH (kein Handel): {e}')
        raise


if __name__ == '__main__':
    main()
