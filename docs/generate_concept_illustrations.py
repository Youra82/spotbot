"""
Erzeugt die README-Illustrationen (docs/*.png) fuer spotbot.
Nicht Teil der Trading-Pipeline -- manuell ausfuehren, wenn sich Strategie/Ergebnisse aendern:

    python research/fetch_data.py 1d        # einmalig: Forschungsdaten (Binance, ab 2017)
    python docs/generate_concept_illustrations.py

Gleiche Farbpalette wie titanbot (docs/generate_concept_illustrations.py dort), damit alle
Bots einheitlich aussehen. Alle Kurven werden mit DEMSELBEN Code wie live berechnet
(spotbot.strategy.run.compute_target + spotbot.analysis.backtest.simulate).
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DOCS_DIR)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'research'))

from engine import load  # noqa: E402
from spotbot.analysis.backtest import simulate  # noqa: E402
from spotbot.strategy.run import compute_target  # noqa: E402
from spotbot.strategy.signal import btc_core_signal  # noqa: E402

# --- titanbot-Palette ---
BG = '#0d1117'
GRID = '#1e2a3a'
SPINE = '#2a3a4a'
TEXT = '#e0e0e0'
MUTED = '#888888'
BULL = '#26a69a'
BEAR = '#ef5350'
GOLD = '#ffd700'
ORANGE = '#ffaa44'
BLUE = '#4488ff'
GREEN = '#00c853'
RED = '#ff1744'
PURPLE = '#b388ff'
FILL_GREEN = '#0a3a2a'
FILL_ORANGE = '#3a2a0a'

CFG = json.load(open(os.path.join(ROOT, 'settings.json'), encoding='utf-8'))['spotbot']
V21 = dict(strategy='core_satellite', core_share=0.2, rebal_days=[7], vol_target=10.0)


def _style_ax(ax, xticks=True):
    ax.set_facecolor(BG)
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(SPINE)
    if not xticks:
        ax.set_xticks([])
    ax.grid(axis='y', color=GRID, linewidth=0.4, zorder=0)


def _save(fig, name):
    out = os.path.join(DOCS_DIR, name)
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    print(f'saved {out}')


def _cached(name, fn):
    p = os.path.join(ROOT, 'research', name)
    if os.path.exists(p):
        return pd.read_pickle(p)
    x = fn()
    x.to_pickle(p)
    return x


# ============================================================
# 1) concept_strategy.png -- echte Entscheidung an einem Tag:
#    Momentum-Ranking der liquidesten Coins -> Allokation.
# ============================================================
def make_strategy(d, w, day='2024-11-10'):
    t = pd.Timestamp(day, tz='UTC')
    c = d['close'].loc[:t]
    liq = d['qvol'].loc[:t].rolling(30).mean().iloc[-1].dropna().sort_values(ascending=False).head(10)
    coins = list(liq.index)
    mom = (c[coins].iloc[-1] / c[coins].iloc[-15] - 1) * 100
    above = c[coins].iloc[-1] > c[coins].rolling(20).mean().iloc[-1]
    mom = mom.sort_values(ascending=True)
    alloc = w.loc[t]
    alloc = alloc[alloc > 0.005].sort_values(ascending=False)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw=dict(width_ratios=[1.35, 1]))
    fig.patch.set_facecolor(BG)
    _style_ax(ax1)
    top3 = set(mom[above[mom.index]].sort_values(ascending=False).head(3).index)
    colors = [GOLD if k in top3 else (BULL if above[k] and v > 0 else BEAR) for k, v in mom.items()]
    bars = ax1.barh(range(len(mom)), mom.values, color=colors, zorder=3, height=0.6)
    ax1.set_yticks(range(len(mom)))
    ax1.set_yticklabels(mom.index, color=TEXT, fontsize=10)
    ax1.axvline(0, color=MUTED, linewidth=0.9)
    ax1.grid(axis='x', color=GRID, linewidth=0.4, zorder=0)
    for b, v in zip(bars, mom.values):
        ax1.text(v + (1 if v >= 0 else -1), b.get_y() + b.get_height() / 2, f'{v:+.0f}%', va='center',
                 ha='left' if v >= 0 else 'right', color=TEXT, fontsize=9, fontweight='bold')
    ax1.set_title('① 14-Tage-Momentum der 10 liquidesten Coins', color=TEXT, fontsize=12, pad=10, fontweight='bold')
    ax1.set_xlabel('Rendite letzte 14 Tage (%)', color=MUTED, fontsize=9)
    ax1.legend(handles=[mpatches.Patch(color=GOLD, label='Top 3 → gekauft'),
                        mpatches.Patch(color=BULL, label='im Trend, nicht Top'),
                        mpatches.Patch(color=BEAR, label='unter SMA / negativ → gesperrt')],
               loc='lower right', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=8)

    ax2.set_facecolor(BG)
    pal = [GOLD, ORANGE, BLUE, BULL, PURPLE, '#ff80ab', '#80deea', '#c5e1a5']
    vals = list(alloc.values) + ([1 - alloc.sum()] if alloc.sum() < 0.995 else [])
    labels = list(alloc.index) + (['USDT'] if alloc.sum() < 0.995 else [])
    cols = pal[:len(alloc)] + ([MUTED] if alloc.sum() < 0.995 else [])
    wedges, _ = ax2.pie(vals, colors=cols, startangle=90, counterclock=False,
                        wedgeprops=dict(width=0.38, edgecolor=BG, linewidth=2))
    for wdg, lab, v in zip(wedges, labels, vals):
        if v < 0.04:
            continue
        ang = np.deg2rad((wdg.theta1 + wdg.theta2) / 2)
        ax2.text(0.81 * np.cos(ang), 0.81 * np.sin(ang), f'{lab}\n{v:.0%}', ha='center', va='center',
                 color=BG, fontsize=9, fontweight='bold')
    ax2.text(0, 0, 'Ensemble-\nAllokation', ha='center', va='center', color=TEXT, fontsize=11, fontweight='bold')
    ax2.set_title('② Ergebnis: Mittel aus 144 Varianten × 7 Tranchen', color=TEXT, fontsize=12, pad=10,
                  fontweight='bold')
    fig.suptitle(f'spotbot V3 – echte Entscheidung am {t.date()} (BTC im Aufwärtstrend)',
                 color=TEXT, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    _save(fig, 'concept_strategy.png')


# ============================================================
# 2) concept_regime.png -- BTC-Regime + tatsaechlicher Investitionsgrad
# ============================================================
def make_regime(d, w, start='2021-01-01'):
    b = d['close']['BTC']
    sma50, sma150 = b.rolling(50).mean(), b.rolling(150).mean()
    core_all = btc_core_signal(b) == 1
    b, sma50, sma150, core_all = (x.loc[start:] for x in (b, sma50, sma150, core_all))
    ww = w.loc[start:]
    btc_w = ww['BTC']
    alt_w = ww.sum(1) - btc_w

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1]))
    fig.patch.set_facecolor(BG)
    _style_ax(ax1); _style_ax(ax2)
    below = (b < sma150)
    for flag, color in ((below, FILL_ORANGE), (core_all & ~below, FILL_GREEN)):
        runs = flag.astype(int).diff().fillna(flag.iloc[0]).ne(0).cumsum()
        for _, seg in flag[flag].groupby(runs[flag]):
            ax1.axvspan(seg.index[0], seg.index[-1], color=color, alpha=0.55, zorder=0, linewidth=0)
    ax1.plot(b.index, b, color=TEXT, linewidth=1.2, label='BTC', zorder=3)
    ax1.plot(sma50.index, sma50, color=BLUE, linewidth=1.0, label='SMA50 (Einstieg)', zorder=3)
    ax1.plot(sma150.index, sma150, color=ORANGE, linewidth=1.3, label='SMA150 (Bärenmarkt-Bremse)', zorder=3)
    ax1.set_yscale('log')
    ax1.yaxis.tick_right()
    ax1.legend(handles=[mpatches.Patch(color=FILL_GREEN, label='alle 5 BTC-Trendfilter an → Leerlauf in BTC'),
                        mpatches.Patch(color=FILL_ORANGE, label='BTC < SMA150 → Einsatz halbiert'),
                        *ax1.get_legend_handles_labels()[0]],
               loc='upper left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=8)
    ax1.set_title('spotbot V3 – Markt-Regime und tatsächlicher Investitionsgrad', color=TEXT, fontsize=13,
                  pad=12, fontweight='bold')
    ax2.stackplot(ww.index, btc_w * 100, alt_w * 100, colors=[ORANGE, BULL], alpha=0.9,
                  labels=['BTC', 'Altcoins'], zorder=3)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel('investiert %', color=MUTED, fontsize=9)
    ax2.yaxis.tick_right()
    ax2.legend(loc='upper left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=8)
    ax2.text(0.99, 0.9, 'Rest = USDT', transform=ax2.transAxes, ha='right', color=MUTED, fontsize=9)
    plt.tight_layout()
    _save(fig, 'concept_regime.png')


def _eq(w, d, start):
    eq = simulate(w, d['open'], cost=0.002, band=CFG['rebalance_band'], start_equity=1000.0).loc[start:].dropna()
    return eq / eq.iloc[0] * 1000


def _btc(d, idx):
    """BTC halten, gleiche Bewertungskonvention wie simulate(): Kauf Open[t0+1], Bewertung Open[t+2]."""
    o = d['open']['BTC']
    e = o.shift(-2).reindex(idx)
    return (e / o.shift(-1).reindex(idx).iloc[0] * 1000).dropna()


# ============================================================
# 3) oos_equity.png -- OOS 2023+ V3 vs BTC halten, mit Drawdown
# ============================================================
def make_oos(d, w):
    eq = _eq(w, d, '2023-01-01')
    bh = _btc(d, eq.index)
    eq = eq.loc[bh.index]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw=dict(height_ratios=[2.4, 1]))
    fig.patch.set_facecolor(BG)
    _style_ax(ax1); _style_ax(ax2)
    ax1.plot(eq.index, eq, color=GOLD, linewidth=2.0, label=f'spotbot V3: {eq.iloc[-1]:,.0f} USDT ({eq.iloc[-1] / 10 - 100:+.0f}%)', zorder=4)
    ax1.plot(bh.index, bh, color=BLUE, linewidth=1.4, label=f'BTC halten: {bh.iloc[-1]:,.0f} USDT ({bh.iloc[-1] / 10 - 100:+.0f}%)', zorder=3)
    ax1.set_yscale('log')
    ax1.yaxis.tick_right()
    ax1.axhline(1000, color=MUTED, linewidth=0.8, linestyle=':')
    nov = eq.loc['2024-11-01':'2024-11-30']
    ax1.annotate('Nov 2024: +172%\n(DOGE/XRP-Rallye)\n– größter Einzelbeitrag',
                 xy=(nov.index[-1], nov.iloc[-1]), xytext=(pd.Timestamp('2025-03-01', tz='UTC'), eq.max() * 0.22),
                 color=ORANGE, fontsize=9, fontweight='bold', arrowprops=dict(arrowstyle='->', color=ORANGE, lw=1.4))
    ax1.legend(loc='upper left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=10)
    ax1.set_title('Out-of-Sample 2023–2026: spotbot V3 vs. BTC halten (Start 1.000 USDT, inkl. Kosten)',
                  color=TEXT, fontsize=13, pad=12, fontweight='bold')
    dd, ddb = (eq / eq.cummax() - 1) * 100, (bh / bh.cummax() - 1) * 100
    ax2.fill_between(dd.index, dd, 0, color=GOLD, alpha=0.35, zorder=3)
    ax2.plot(dd.index, dd, color=GOLD, linewidth=1.0, label=f'V3 max. {dd.min():.0f}%', zorder=4)
    ax2.plot(ddb.index, ddb, color=BLUE, linewidth=1.0, label=f'BTC max. {ddb.min():.0f}%', zorder=4)
    ax2.set_ylabel('Drawdown %', color=MUTED, fontsize=9)
    ax2.yaxis.tick_right()
    ax2.legend(loc='lower left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=9)
    plt.tight_layout()
    _save(fig, 'oos_equity.png')


# ============================================================
# 4) full_equity.png -- 2018-2026, log, V3 / V2.1 / BTC
# ============================================================
def make_full(d, w3, w21):
    e3 = _eq(w3, d, '2018-01-01')
    e21 = _eq(w21, d, '2018-01-01').loc[e3.index]
    bh = _btc(d, e3.index)
    e3, e21 = e3.loc[bh.index], e21.loc[bh.index]
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor(BG)
    _style_ax(ax)
    ax.axvspan(pd.Timestamp('2023-01-01', tz='UTC'), e3.index[-1], color=FILL_GREEN, alpha=0.5, zorder=0)
    ax.text(pd.Timestamp('2023-02-01', tz='UTC'), 1300, 'OOS 2023+', color=BULL, fontsize=10, fontweight='bold')
    ax.axvspan(pd.Timestamp('2018-01-01', tz='UTC'), pd.Timestamp('2018-12-15', tz='UTC'), color='#3a0a0a', alpha=0.6, zorder=0)
    ax.axvspan(pd.Timestamp('2021-11-10', tz='UTC'), pd.Timestamp('2022-12-31', tz='UTC'), color='#3a0a0a', alpha=0.6, zorder=0)
    ax.text(pd.Timestamp('2018-02-01', tz='UTC'), 250, 'Bärenmarkt\nBTC −72%', color=BEAR, fontsize=9, fontweight='bold')
    ax.text(pd.Timestamp('2022-01-15', tz='UTC'), 250, 'Bärenmarkt\nBTC −64%', color=BEAR, fontsize=9, fontweight='bold')
    for e, col, lw, lab in ((e3, GOLD, 2.0, 'spotbot V3'), (e21, BULL, 1.4, 'spotbot V2.1 (konservativ)'), (bh, BLUE, 1.4, 'BTC halten')):
        ax.plot(e.index, e, color=col, linewidth=lw, label=f'{lab}: ×{e.iloc[-1] / 1000:.1f}', zorder=4)
    ax.set_yscale('log')
    ax.yaxis.tick_right()
    ax.legend(loc='upper left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=10)
    ax.set_title('2018–2026: Vermögensentwicklung (log, Start 1.000 USDT, 70 Coins inkl. abgestürzter)',
                 color=TEXT, fontsize=13, pad=12, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'full_equity.png')
    return e3, bh


# ============================================================
# 5) yearly_returns.png
# ============================================================
def make_yearly(e3, bh):
    def yr(e):
        y = e.resample('YE').last()
        r = y.pct_change()
        r.iloc[0] = y.iloc[0] / e.iloc[0] - 1
        return r * 100
    a, b = yr(e3), yr(bh)
    years = [i.year for i in a.index]
    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(14, 6.5))
    fig.patch.set_facecolor(BG)
    _style_ax(ax)
    b1 = ax.bar(x - 0.2, a.values, width=0.4, color=[GOLD if v >= 0 else BEAR for v in a.values], zorder=3, label='spotbot V3')
    b2 = ax.bar(x + 0.2, b.values, width=0.4, color=[BLUE if v >= 0 else '#7a2a2a' for v in b.values], zorder=3, label='BTC halten')
    for bars in (b1, b2):
        for r in bars:
            v = r.get_height()
            ax.text(r.get_x() + r.get_width() / 2, v + (6 if v >= 0 else -14), f'{v:+.0f}%', ha='center',
                    color=TEXT, fontsize=8, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) + (' (bis Sep)' if y == years[-1] else '') for y in years], color=TEXT, fontsize=10)
    ax.axhline(0, color=MUTED, linewidth=0.9)
    ax.legend(handles=[mpatches.Patch(color=GOLD, label='spotbot V3'), mpatches.Patch(color=BLUE, label='BTC halten')],
              loc='upper left', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=10)
    ax.set_ylabel('Jahresrendite %', color=MUTED, fontsize=9)
    ax.set_title('Jahresrenditen: Bärenmärkte (2018, 2022) aussitzen ist der größte Hebel',
                 color=TEXT, fontsize=13, pad=12, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'yearly_returns.png')


# ============================================================
# 6) strategy_comparison.png -- alle getesteten Familien (Werte aus RESEARCH.md)
# ============================================================
def make_comparison():
    rows = [  # (Name, Endwert 2018-2026, Max-DD %)
        ('Vol-Breakout (1 Tag)', 0.28, -82), ('Wochentag Mo/Fr/Sa', 1.3, -43), ('Mean-Reversion', 1.6, -29),
        ('Dip-Kauf im Bullenmarkt', 1.9, -48), ('Spot-Grid (mit Filter)', 3.4, -37), ('BTC halten', 5.7, -81),
        ('DCA-Martingale BTC', 6.0, -72), ('V1 Rotation (vt 0.6)', 10.2, -26), ('BTC-Trendfilter voll', 22.7, -58),
        ('V2 Kern+Satellit', 26.6, -33), ('Turtle-Breakout', 28.6, -63), ('V2.1 wöchentlich', 38.8, -35),
        ('BTC/ETH-Switch', 42.3, -58), ('V3 Fast Momentum', 106.5, -40),
    ]
    names, mult, dd = zip(*rows)
    fig, ax = plt.subplots(figsize=(13, 7.5))
    fig.patch.set_facecolor(BG)
    _style_ax(ax)
    cols = [GOLD if n.startswith('V3') else (BLUE if n == 'BTC halten' else (GREEN if d_ > -41 else BEAR)) for n, d_ in zip(names, dd)]
    bars = ax.barh(range(len(names)), mult, color=cols, zorder=3, height=0.6)
    ax.set_xscale('log')
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, color=TEXT, fontsize=10)
    ax.grid(axis='x', color=GRID, linewidth=0.4, zorder=0)
    ax.axvline(1, color=MUTED, linewidth=0.9)
    for b, m, d_ in zip(bars, mult, dd):
        ax.text(m * 1.08, b.get_y() + b.get_height() / 2, f'×{m:g}   DD {d_}%', va='center', color=TEXT, fontsize=9,
                fontweight='bold')
    ax.set_xlim(0.2, 600)
    ax.set_xlabel('Endwert 2018–2026 (log, 1 = kein Gewinn)', color=MUTED, fontsize=9)
    ax.legend(handles=[mpatches.Patch(color=GREEN, label='Max-DD ≤ 40%'), mpatches.Patch(color=BEAR, label='Max-DD > 40%'),
                       mpatches.Patch(color=BLUE, label='Benchmark'), mpatches.Patch(color=GOLD, label='gewählt')],
              loc='lower right', facecolor=BG, edgecolor=SPINE, labelcolor=TEXT, fontsize=9)
    ax.set_title('~20 getestete Spot-Strategien (Ensembles, 0,2% Kosten je Seite)', color=TEXT, fontsize=13,
                 pad=12, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'strategy_comparison.png')


if __name__ == '__main__':
    d = load('1d')
    w3 = _cached('v3_candidate.pkl', lambda: compute_target(d['close'], d['qvol'], CFG))
    w21 = _cached('A_rebal7_0.2.pkl', lambda: compute_target(d['close'], d['qvol'], dict(CFG, **V21)))
    make_strategy(d, w3)
    make_regime(d, w3)
    make_oos(d, w3)
    e3, bh = make_full(d, w3, w21)
    make_yearly(e3, bh)
    make_comparison()
