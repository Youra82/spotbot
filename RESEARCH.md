# spotbot: Forschungsprotokoll (2026-09-25)

**Ziel:** höchster PnL bei max. 30% DD, long-only Spot, OOS berücksichtigt.
**Daten:** Binance-Spot 1d ab 2017 (Bitget reicht nicht so weit zurück; Schlusskurse weichen <0,01% ab). IS = 2018–2022, OOS = 2023-01 bis 2026-09.
**Kosten:** 0,1% Gebühr + 0,1% Slippage je Seite. Das Signal entsteht bei Close[t], ausgeführt wird zum Open[t+1].

## 1. Survivorship-Bias
Das Anfangsuniversum (30 heutige Coins) zeigte bei der Rotation ~106% CAGR. Nach Erweiterung um 40 teils tote Coins (LUNA, FTT, WAVES, MATIC, FTM, OMG, XMR, SRM …) plus Point-in-time-Liquiditätsfilter blieben 55–78%, mit starker Streuung je Parameter. Datenlücken über 2 Tage gelten als Delisting (der LUNA-Relaunch hätte sonst +177.000% an einem Tag erzeugt).

## 2. Grid (11.664 Kombis) und Auswahl-Overfitting
Wer den IS-Sieger mit IS-DD ≤ 30% auswählt, bekommt einen **OOS-DD von −42% im Median**. Nur 6% der Top-50 hielten die Grenze auch OOS. Die DD-Grenze wird im IS "hineinoptimiert".

Strukturelle Hebel (Median-OOS-DD): Vol-Target 0,3 → −28% (ohne: −62%), wöchentliches Umschichten −36% (täglich: −46%), Breadth-Filter −38%, BTC-Regime −40% (ohne: −45%).
**Trailing-Stop 20%: wirkungslos.**

## 3. Walk-Forward mit jährlicher Neuauswahl
Je nach Auswahlregel lagen die Ergebnisse zwischen 27% und 55% CAGR und zwischen −27% und −50% DD. Die Parameterauswahl selbst ist also die größte Zufallsquelle.

## 4. Parameter-Ensemble (Durchbruch)
Statt einen Parametersatz auszuwählen, mittelt der Bot alle 432 Mitglieder. Bei vt 0,5: IS-DD −18,5%, OOS-DD −21,8%, 35% CAGR. IS und OOS sind konsistent.

## 5. Umschicht-Wochentag
Der erste Ensemble-Bestwert (vt 1,0: 52% CAGR, DD 28%) war **Wochentag-Glück**. Über alle 7 Phasen schwankte der OOS-DD zwischen −26% und −43%. Die Lösung sind Tranchen: Der Bot mittelt über alle 14 Phasen. Ehrliche Werte: vt 0,8 ergibt 38% CAGR bei DD −32%, vt 0,6 ergibt 32% CAGR bei DD −28,5%.

## 6. Verworfen
- **TSMOM** (Zeitreihen-Momentum je Coin): höchstens ~42% CAGR bei über 38% DD.
- **Mix Rotation + TSMOM:** Korrelation 0,82, kein Sharpe-Gewinn.
- **Trailing-Stop:** kein Effekt.

## 7. Finale Konfiguration
vt 0,6, No-Trade-Band 2%. Das Band senkt den DD von −28,5% auf −26,2% und kostet ~1% CAGR. Die OOS-DDs sind Zermürbungs-DDs in Seitwärtsmärkten (2023, 2024), keine Crashs.

Robustheit:

| Test | Ergebnis |
|---|---|
| doppelte Kosten | DD −26,6% |
| ohne Top-Gewinner (SOL/DOGE/INJ/AVAX/BNB/SHIB/LUNA/FTM/MATIC/SUI), vor Tranchen | leicht schwächer, weiterhin positiv |
| 1 Tag verspätete Ausführung | spürbar schlechter → der Bot muss zeitnah nach 00:00 UTC laufen |

Gemeinsamer Code: `target_weights` auf einem 200-Tage-Live-Fenster ist identisch zum Voll-Backtest (Abweichung < 1e-14, getestet an 5 Stichtagen und in `tests/test_signal.py`).

## 8. Version 2: "ein Vielfaches von BTC" (User-Wunsch, DD-Grenze auf ~40% angehoben)
- **BTC-Trendfilter voll investiert:** Die besten erreichten ×20–23 über 2018–26 statt ×5,7. OOS lagen sie mit 315–389% aber unter Halten (406%), bei ~60% IS-DD.
- **Obergrenze aus dem Grid (rückblickend geschummelt):** Mit OOS-DD ≤ 30% lag das beste OOS-Ergebnis bei 603% (×1,5 BTC). Mit ≤ 40% waren 0,4% der Kombis über dem Doppelten von BTC, also Lotterie.
- **Einzelkonfigurationen vor Robustheitsbehandlung:** Majors-Switch ×236 bei DD −47%; Kern+Satellit ×101 bei DD −37%. Nach Ensemble und Tranchen schrumpfte das auf ×16–50.
- **BTC-Kern-DD entsteht durch Zermürbung in Bärenmärkten**, nicht durch Crash-Tage (schlechtester Tag −9 bis −13%). Ein 4h-Notausstieg hilft daher nicht. Vol-Targeting des Kerns brachte praktisch nichts.
- **Gewählt (nur nach IS, IS-DD ≤ ~33%):** Kern 30% ohne Vol-Target, Satellit ohne Vol-Target, Band 2%. Ergebnis ×26,6, DD −33,1%, OOS +210% bei −29,9%.
  - Alternative "Satelliten-Cash → BTC": ×46, DD −45%, OOS +366%. Verworfen, weil über der Grenze.
- Das 400-Tage-Live-Fenster ist identisch zur Vollhistorie (Abweichung < 4e-15 an 6 Stichtagen).

## 9. Breiter Strategie-Vergleich (User: "nicht nur Parameter, auch andere Strategien, Grid, Martingale, alles")
Jede Familie wurde als vorab festgelegtes Parameter-Ensemble getestet: 2018–2026, IS 2018–22, OOS 2023+, 0,2% Kosten je Seite.
Referenz: V2 ×26,6, DD −33%, OOS +210%. BTC halten ×5,7–6,2, DD −81%, OOS +406%.

| Familie | Ergebnis | Urteil |
|---|---|---|
| Mean-Reversion RSI(2)/Bollinger/N-Tage-Rendite | ×1,1–1,6, DD −29…−42% | kein Edge nach Kosten; als Leerlauf-Füller erhöht sie den DD |
| Dip-Kauf im Bullenmarkt | ×1,9, DD −48% | verworfen |
| Volatilitäts-Breakout (1 Tag halten) | ×0,28, DD −82% | verliert |
| Wochentag Mo/Fr/Sa | ×1,3, OOS −5% | der Effekt existiert auf Renditeebene, **die Kosten fressen ihn auf** |
| Donchian-Breakout/Turtle (ATR-Trailing) | ×28,6, DD −63% | Korrelation 0,82 zu V2, keine Verbesserung in Kombination |
| BTC/ETH-Relativstärke-Switch | ×42, DD −58% | als 30%-Kern: ×39/DD −37% (V3), bei doppelten Kosten nur ×26,5, OOS schlechter, Vorsprung nur 2021 → nicht übernommen |
| DCA-Martingale (3Commas-Stil), BTC/ETH | ×4–13, DD −70…−92% | im Kern Buy&Hold mit Bags; Trendfilter stoppt nur neue Zyklen; mit Stop ×1,1 |
| DCA-Martingale auf Altcoins | DD −68…−94%, meist schlechter als Halten; LUNA **Totalverlust (−100%)**, FTT −91…−98%, MATIC −77…−86% | verworfen |
| Spot-Grid (geometrisch, rollierender Neuaufbau) | mit Trendfilter ×3,4 (BTC) / ×4,9 (ETH); ohne Filter bis −99% | verworfen |
| Anti-Martingale auf Strategie-Equity | erster Test ×5.300 = **Lookahead-Fehler** (Equity[t] enthielt Open[t+2]); korrekt verzögert: kein Gewinn | verworfen |
| Martingale auf Strategie-Equity (im DD verdoppeln) | V2 ×34, DD −42% | keine Effizienzverbesserung |
| Funding-Rate-Überhitzungsfilter | ×10–27 | schadet: überhitzte Phasen laufen weiter |
| Crash-Filter (BTC 3/7-Tage-Einbruch) | ×17–23 | schadet |
| 4h statt 1d (identische Logik) | in 0/36 Paaren besser | verworfen |
| Breiteres Universum (Top 40) | nur IS besser (Altcoin-Saison 2021), OOS nicht; größter Survivorship-Bias | nicht vertrauenswürdig |

**Fazit:** Alles, was funktioniert, ist Trend/Momentum und liegt bei Sharpe 1,0–1,3. Keine Familie und keine Kombination bricht robust aus dieser Effizienzgrenze aus. V2 bleibt auf der Grenze. Mehr Rendite gibt es nur gegen proportional mehr DD, z.B. mit Satelliten-Cash in BTC: ×46 bei DD −45%.

## 10. Ranking-Varianten und V2.1 (User: "brauchbare Ergebnisse")
Getestet wurden Ranking-Modi (USD-Momentum, relative Stärke zu BTC, Momentum/Vola), "Skip"-Momentum, ein BTC-Füller für freie Plätze, ein RS-Filter gegen BTC und Zins auf Leerlauf-USDT.
- **Relative Stärke als Ranking ist identisch mit USD-Momentum:** Alle Coins werden durch denselben BTC-Faktor geteilt, die Rangfolge bleibt also gleich.
- **Skip-3-Momentum:** schlechter (×29 statt ×59, jeweils Satellit ohne Kern).
- **Risiko-Ranking (Momentum/Vola):** sah zuerst nach ×55 aus. Die Ablation zeigt keinen echten Vorteil: Endwert gleich, OOS schlechter (201% statt 244%), ohne Gewinner-Coins deutlich schlechter (146% statt 199%). → **verworfen**
- **"Neues Grid" (Top 3/5, ohne Breadth 0,5 und Top 8):** ×52–59. Das ist höhere Konzentration, also mehr DD (−37,6%, ohne Gewinner −42,8%). Ein Risiko-Tausch, keine Effizienz. → nicht übernommen
- **V2.1 = V2-Ensemble mit nur wöchentlichem Umschichten und 20% statt 30% Kern:**
  - normal: ×38,8, DD −34,9%, OOS +244% (V2: ×26,6 / −33,1% / +210%)
  - doppelte Kosten: ×30,3 (V2: ×21,9)
  - ohne Gewinner-Coins: ×18,8 / −40,0% (V2: ×14,1 / −38,0%)
  - Sharpe 1,32 statt 1,29, also überwiegend mehr Rendite gegen etwas mehr DD. Besser in allen Stressszenarien und innerhalb der ~40%-Grenze → **übernommen**
- **Zins auf Leerlauf-USDT (4% p.a., z.B. Bitget Earn):** ca. +25% Endwert, DD leicht besser. Nicht automatisiert (Kontrahentenrisiko, Earn-Umbuchungen); wäre manuell möglich.

## 11. V3 "Fast Momentum" (User-Ziel: mindestens 30% mehr als BTC halten)
Ziel: OOS 2023+ ≥ +558% (BTC halten +406%, Endwert ×5,06 → Ziel ×6,6).

**Wichtig:** Ab hier wurde gezielt auf den Zeitraum 2023+ hingearbeitet. Er ist damit **nicht mehr sauber out-of-sample**.

- **Majors-Analyse (192 Einzelkonfigs):** Kurzes Momentum (14 T) ist im IS (+516% Median) **und** OOS (+678%) am besten. Wöchentlich schlägt täglich, BTC-Regime hilft im IS.
- **Fast-Momentum-Ensemble** (mom 7–21, Top 1–3 von 5–10 liquidesten, wöchentlich, 7 Tranchen): ×93–116, DD 41–45%, OOS +474–495% → über BTC, aber unter dem Ziel.
- **Leerlauf → BTC-Trendkern:** OOS +590…743% (Ziel erreicht), aber DD 55–60%, weil der BTC-Kern die Bärenmarkt-DDs übernimmt.
- **Strenger Füller (alle 5 BTC-Filter positiv):** DD 48–51%, Endwert höher.
- **Schnellerer Füller / Portfolio-Vol-Target:** hilft kaum, weil die DDs schleichend sind (Bärenmarkt-Rallyes), keine Vola-Spitzen.
- **Langsamer Filter BTC > SMA150/200/250:** Hart ausgestiegen kostet zu viel Rendite. Weich (darunter 50% Exposure) ergibt ein Plateau: OOS +570…680%, DD 40–45%.
- **Gewählt: V3 = vt 1,5 + strenger Füller + SMA150 weich**
  - normal: ×106,5, DD −40,0% (IS −34,9%), OOS +680%
  - 2× Kosten: OOS +502%
  - 1 Tag Verzug: +529%
  - ohne 10 Gewinner-Coins: +450% bei DD −50,7%
- **Live-Fund:** Die Liquiditätsrangliste von Bitget weicht von Binance ab (ZEC/UNI statt NEAR/SOL vorne). Für die konzentrierte V3 ist das entscheidend. Lösung: Signaldaten von Binance (`signal_exchange`), Ausführung auf Bitget. Im Trockenlauf 2026-09-24 war das Live-Ziel identisch zum Backtest-Ziel.
