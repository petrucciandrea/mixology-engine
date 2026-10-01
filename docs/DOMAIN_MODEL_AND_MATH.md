# Domain Model & Formule Matematiche Mixology

## 1. Proprietà degli Ingredienti
Ogni ingrediente ha i seguenti parametri:
- `volume_ml`: Volume in millilitri (float)
- `abv`: Titolo alcolometrico volumetrico in frazione [0.0 - 1.0]
- `brix`: Concentrazione zuccherina in gradi Brix [% peso] [0.0 - 100.0]
- `acidity`: Percentuale peso/volume di acido equivalente (citrico/malico/tartarico) [0.0 - 10.0]
- `density_g_ml`: Densità in g/ml (es. alcol ~0.94, sciroppo 1:1 ~1.23, acqua ~1.00)

## 2. Formule di Bilanciamento Pre-Diluizione
- **Volume Totale:** $V_{tot} = \sum V_i$
- **Alcol Puro (ml):** $V_{alc} = \sum (V_i \cdot ABV_i)$
- **ABV Pre-Diluizione:** $ABV_{pre} = \frac{V_{alc}}{V_{tot}}$
- **Massa Totale Liquidi (g):** $M_{tot} = \sum (V_i \cdot \text{density}_i)$
- **Zuccheri Totali (g):** $M_{sugar} = \sum (V_i \cdot \text{density}_i \cdot \frac{Brix_i}{100})$
- **Brix Pre-Diluizione (°Bx):** $Brix_{pre} = \left(\frac{M_{sugar}}{M_{tot}}\right) \cdot 100$
- **Massa Acidi (g):** $M_{acid} = \sum (V_i \cdot \text{density}_i \cdot \frac{\text{acidity}_i}{100})$
- **Acidità Pre-Diluizione (%):** $\text{Acidity}_{pre} = \left(\frac{M_{acid}}{M_{tot}}\right) \cdot 100$
- **Sugar-to-Acid Ratio:** $\text{Ratio} = \frac{Brix_{pre}}{\text{Acidity}_{pre}}$ (Target Sour standard: 5.5 - 7.0)

## 3. Modello di Diluizione Termodinamica (Dave Arnold)
- **Fattore Diluizione Shakerata:** 
  $$\text{Dil}_{shake} = -1.567 \cdot (ABV_{pre})^2 + 1.742 \cdot ABV_{pre} + 0.203$$
- **Fattore Diluizione Mescolata (Stir):** 
  $$\text{Dil}_{stir} = -1.150 \cdot (ABV_{pre})^2 + 1.350 \cdot ABV_{pre} + 0.150$$
- **Volume Acqua Diluizione (ml):** $V_{h2o} = V_{tot} \cdot \text{Dil}$
- **Volume Finale:** $V_{final} = V_{tot} + V_{h2o}$
- **ABV Finale Effettivo:** $ABV_{post} = \frac{V_{alc}}{V_{final}}$
- **Brix Post-Diluizione:** $Brix_{post} = \left(\frac{M_{sugar}}{M_{tot} + V_{h2o}}\right) \cdot 100$
- **Acidità Post-Diluizione:** $\text{Acidity}_{post} = \left(\frac{M_{acid}}{M_{tot} + V_{h2o}}\right) \cdot 100$

## 4. Diluizione da ghiaccio di servizio (bilancio termico)
Vale solo per le ricette con `serving_ice ≠ NONE` ed è un profilo **separato** (`ServingProfile`), calcolato dopo $t$ minuti di consumo (default 10, massimo 60). Le curve di Arnold non lo coprono: è un bilancio di calore, con ipotesi dichiarate in `domain/services/serving_dilution.py`.

- **Punto di congelamento (legge crioscopica ideale):** $T_f = -K_f \cdot \dfrac{n_{EtOH} + n_{saccarosio}}{m_{H_2O}\,[kg]}$, con $K_f = 1.86$ K·kg/mol, saturato a −40 °C.
- **Raffreddamento fino all'equilibrio:** $m_{eq}\,(L - c_w\,|T_f|) = M\,c_p\,(T_s - T_f)$, con $L = 334$ J/g; $T_f$ dipende da $m_{eq}$ (si risolve per bisezione). $T_s = T_f$ per shaken/stirred (già raffreddati: termine nullo), $T_s = 20$ °C per built.
- **Cinetica (il tipo di ghiaccio entra qui):** $m_{cool}(t) = m_{eq}\,(1 - e^{-t/\tau})$, con $\tau = \dfrac{M\,c_p}{h\,A}$, $A = (S/V)_{tipo}\cdot V_{ghiaccio}$. Superfici specifiche $S/V = 6/a$: cubetti 25 mm, cubo grosso 50 mm, tritato ~6 mm.
- **Calore ambiente:** $m_{amb}(t) = P\,t / L$, con $P = 6$ W.
- **Totale:** $V_{serving} = V_{final} + m_{cool} + m_{amb}$, limitato al ghiaccio disponibile ($V_{ghiaccio} = V_{final}$); ABV, Brix e acidità si ricalcolano sulle nuove masse e volumi.

Ipotesi tarabili (non costanti fisiche): $h = 300$ W/m²K, $P = 6$ W, volume di ghiaccio = volume del drink, dimensioni caratteristiche dei tipi di ghiaccio, ghiaccio a 0 °C, superficie costante durante la fusione.

## 5. Bicchiere di servizio e capienza
`Recipe.glass` è un `GlassType` **facoltativo**. Se presente e con capienza nota (tutto tranne `OTHER`), pone un tetto al volume del drink servito. Ipotesi dichiarate in `domain/services/glassware.py`:

- **Volume utile:** $V_{util} = C \cdot 0.9$, con $C$ capienza a filo bordo (bordo libero del 10%).
- **Con ghiaccio di servizio** il solido occupa una quota $s = 0.35$ dello spazio utile: $V_{max} = V_{util}\,(1 - s)$. Senza ghiaccio $V_{max} = V_{util}$.
- **Vincolo:** $V_{final} \le V_{max}$ (disuguaglianza SLSQP, normalizzata su $V_{max}$). Se è presente anche il target `final_volume_ml` (uguaglianza) e $V_{target} > V_{max}$ il problema è `INFEASIBLE`.
- **Riempimento:** $\text{fill} = V_{final} / V_{max}$; oltre 1 il drink trabocca (`GlassFit.overflows`).

Limiti: capienze tipiche, non misure di produttore; $s$ tarato su drink classici serviti pieni; l'acqua di fusione che si aggiunge dopo il servizio sta nel bordo libero.
