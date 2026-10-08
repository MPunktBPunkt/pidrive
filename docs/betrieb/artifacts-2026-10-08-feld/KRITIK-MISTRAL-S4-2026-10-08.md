# Kritik Mistral-Übergabe s4 · unabhängig (Cursor) · 2026-10-08

Bezug: Mistral-Canvas/Übergabe zu HEAD `a90c0f0` · Gegenprüfung Rohdaten + GPT-Review · eigener Bericht: [`UEBERGABE-S4-NAECHSTE-KI-2026-10-08.md`](UEBERGABE-S4-NAECHSTE-KI-2026-10-08.md)

## Gesamturteil

**Gut und nutzbar** als Arbeitsübernahme. Kernlage (Ring-Episode 8,26 s, R28, Rename≠P, not_from_head, Lab 0 Drops vs Feld viele Resets) stimmt mit den Artefakten. An **drei Stellen zu absolut** — GPT und Rohdaten stimmen darin überein.

## Bestätigt

| Mistral | Prüfung |
|---------|---------|
| Instrument 8,26 s = Lab ~8,2 s | LIVE-WINDOW #106 PD0127 fav2 — ja |
| R28 BOB + Antenne | Marks 17:13 / 17:18 / 17:24 — ja; **Bayern Ohr** nachziehen (Operator) |
| Rename allein widerlegt | K3 + Rejects — ja |
| not_from_head dominant | 112 im Bridge-Log — ja |
| Lab REPLUG 0 Drops → Versorgung priorisieren | lab-abend-nach-s4-1741 — Richtung ja |
| L0–L3 Gate, Freeze | ja |
| Q10 = 4 KiB nur Kandidat | Mistral sagt das korrekt; nicht als Fakt verkaufen |

## Korrigieren

1. **„Tonfenster = Ring“ / 8,2 s als globale Grenze**  
   Rohdaten #167: Live-s **17.68** bei Ring 49152 / undΔ ~8 M. Metrik = Live-Bytes/bps in der Episode, nicht „HU hörte 17 s“ und nicht „Ring ist 17 s“.  
   **Besser:** Eine saubere Episode trifft das 48‑KiB-Modell; längere Live-s-Zahlen existieren und sind anders zu lesen.

2. **„Verlust 8,2→5–6 s liegt nachweislich in der HU“**  
   Stark plausibel, nicht End-to-End bewiesen.  
   **Besser:** Differenz entsteht nach Ring-/Producer-Seite; HU-Anlauf/Format = stärkste Erklärung.

3. **„Reboots = Versorgung“ als Fakt**  
   Lab schwächt MSC-Softwarepfad; Identität Auto≠Lab; kein `rst:`-Log.  
   **Besser:** Software-Zwangsreboot unwahrscheinlich; Versorgung/VBUS priorisiert, unbewiesen.

4. **Klasse A/B Replug** (von GPT/Operator) fehlte bei Mistral zu wenig betont:  
   Replug **ohne** ESP-Reset ist die wertvolle Bedingung — nicht pauschal „Stecken = Reboot“.

## Bayern

Mistral erwähnt Bayern teils mit; Log zeigt Stream-Start fav1, Operator bestätigt Bild+Ton ~5–6 s. Für die nächste KI: **drei Sender Operator [B]**, instrumentierte Live-Fenster-Zahl vor allem BOB #106.

## Nächste Schritte

Mistrals Reihenfolge (Versorgung → P → Sniffer → Stall) bleibt richtig; Formulierungen wie oben schärfen. Kein Stall-Go ohne P0 Reset-Reason oder explizites Go.
