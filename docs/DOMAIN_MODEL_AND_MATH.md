# Domain Model & Formule Matematiche Mixology

## 1. Proprietà degli Ingredienti
Ogni ingrediente ha i seguenti parametri:
- `volume_ml`: Volume in millilitri (float)
- `abv`: Titolo alcolometrico volumetrico in frazione [0.0 - 1.0]
- `brix`: Massa di **zucchero** ogni 100 g, in gradi Brix [% peso] [0.0 - 100.0]. Non è la lettura del rifrattometro, che conta anche gli acidi (lime: 7.5 letto, 1.7 di zucchero). ADR-0011
- `acidity`: Percentuale peso/volume di acido equivalente (citrico/malico/tartarico), cioè g ogni 100 ml [0.0 - 10.0]
- `density_g_ml`: Densità in g/ml (es. alcol ~0.94, sciroppo 1:1 ~1.23, acqua ~1.00)

## 2. Formule di Bilanciamento Pre-Diluizione
- **Volume Totale:** $V_{tot} = \sum V_i$
- **Alcol Puro (ml):** $V_{alc} = \sum (V_i \cdot ABV_i)$
- **ABV Pre-Diluizione:** $ABV_{pre} = \frac{V_{alc}}{V_{tot}}$
- **Massa Totale Liquidi (g):** $M_{tot} = \sum (V_i \cdot \text{density}_i)$
- **Zuccheri Totali (g):** $M_{sugar} = \sum (V_i \cdot \text{density}_i \cdot \frac{Brix_i}{100})$
- **Brix Pre-Diluizione (°Bx):** $Brix_{pre} = \left(\frac{M_{sugar}}{M_{tot}}\right) \cdot 100$
- **Massa Acidi (g):** $M_{acid} = \sum (V_i \cdot \frac{\text{acidity}_i}{100})$ (senza densità: l'acidità è già per volume)
- **Acidità Pre-Diluizione (% p/v):** $\text{Acidity}_{pre} = \left(\frac{M_{acid}}{V_{tot}}\right) \cdot 100$
- **Sugar-to-Acid Ratio:** $\text{Ratio} = \frac{M_{sugar}}{M_{acid}}$ (g di zucchero per g di acido), definito solo se $\text{Acidity}_{pre} \ge 0.5$ % p/v, altrimenti assente. Non dipende dalla diluizione.
- **Giudizio sui sour:** solo per `RecipeFamily.SOUR`. Equilibrato se $3.5 \le \text{Ratio} \le 12.0$, aspro sotto, dolce sopra. Finestra tarata sui classici del seed (ADR-0011).

## 3. Modello di Diluizione Termodinamica (Dave Arnold)
- **Fattore Diluizione Shakerata:** 
  $$\text{Dil}_{shake} = -1.567 \cdot (ABV_{pre})^2 + 1.742 \cdot ABV_{pre} + 0.203$$
- **Fattore Diluizione Mescolata (Stir):** 
  $$\text{Dil}_{stir} = -1.150 \cdot (ABV_{pre})^2 + 1.350 \cdot ABV_{pre} + 0.150$$
- **Volume Acqua Diluizione (ml):** $V_{h2o} = V_{tot} \cdot \text{Dil}$
- **Volume Finale:** $V_{final} = V_{tot} + V_{h2o}$
- **ABV Finale Effettivo:** $ABV_{post} = \frac{V_{alc}}{V_{final}}$
- **Brix Post-Diluizione:** $Brix_{post} = \left(\frac{M_{sugar}}{M_{tot} + V_{h2o}}\right) \cdot 100$
- **Acidità Post-Diluizione (% p/v):** $\text{Acidity}_{post} = \left(\frac{M_{acid}}{V_{final}}\right) \cdot 100$

## 4. Diluizione da ghiaccio di servizio (bilancio termico a due nodi)
Vale solo per le ricette con `serving_ice ≠ NONE` ed è un profilo **separato** (`ServingProfile`), calcolato dopo $t$ minuti di consumo (default 10, massimo 60). Le curve di Arnold non lo coprono: è un bilancio di calore, con ipotesi dichiarate in `domain/services/serving_dilution.py` (ADR-0012).

- **Punto di congelamento (legge crioscopica ideale):** $T_f = -K_f \cdot \dfrac{n_{EtOH} + n_{saccarosio}}{m_{H_2O}\,[kg]}$, con $K_f = 1.86$ K·kg/mol, saturato a −40 °C. Si ricalcola a ogni istante sull'acqua del drink più quella di fusione.
- **Ghiaccio:** pezzi da `domain/serving_geometry.py` (prismi a base quadrata: cubetti 25 mm, cubo grosso 50 mm, tritato ~6 mm, colonna 30 × 30 × 120 mm). Cubetti e tritato riempiono: $V_{ghiaccio} = V_{final}$. Cubo grosso e colonna sono un pezzo unico: $V_{ghiaccio} = V_{pezzo}$. Superficie iniziale $A_0 = (S/V)_{tipo}\cdot V_{ghiaccio}$; durante la fusione $A = A_0\,(m_{ghiaccio}/m_0)^{2/3}$.
- **Due nodi, un percorso (ambiente → drink → ghiaccio):** $C\,\dfrac{dT}{dt} = U\,(T_a - T) - h\,A\,(T - T_f) - \dot m\,c_w\,(T - T_f)$, con $\dot m = \dfrac{h\,A\,(T - T_f)}{L - c_w\,|T_f|}$ e $C = C_0 + m\,c_w$. Il tipo di ghiaccio entra solo da $A$. Esaurito il ghiaccio resta $C\,\dfrac{dT}{dt} = U\,(T_a - T)$.
- **Temperatura di servizio:** $T_s = T_f$ per shaken/stirred (escono all'equilibrio), $T_s = T_a = 20$ °C per built.
- **Conservazione dell'entalpia** (riferimento: acqua liquida a 0 °C): $(C_0 + m\,c_w)\,T + L\,m = C_0\,T_s + Q_{amb}$, con $Q_{amb} = \int U\,(T_a - T)\,dt$ (`ambient_heat_j`).
- **Integrazione:** passo di 1 s su griglia fissa dall'istante del servizio. A coefficienti congelati nel passo, $T$ segue l'esponenziale esatto verso $T_\infty = \dfrac{U\,T_a + (h\,A + \dot m\,c_w)\,T_f}{U + h\,A + \dot m\,c_w}$ (stabile per qualunque passo), $Q_{amb}$ il suo integrale in forma chiusa, e $m$ si ricava dalla conservazione. La fusione non decresce né supera il ghiaccio; se il passo la porterebbe fuori, si ferma al limite e $T$ si ricava dalla stessa entalpia.
- **Regime quasi stazionario** (drink freddo sul ghiaccio): $T - T_f \approx \dfrac{U\,(T_a - T)}{h\,A + \dot m\,c_w}$. Con poca superficie il drink resta più caldo, richiama meno calore e fonde meno.
- **Totale:** $V_{serving} = V_{final} + m$; ABV, Brix e acidità si ricalcolano sulle nuove masse e volumi. Il ghiaccio residuo è $m_0 - m$.
- **Curva di servizio:** lo stesso modello campionato ogni minuto da $t = 0$ (il drink appena servito) a 30 minuti; accompagna ogni risposta di `/balance` come `serving_curve`.

Ipotesi tarabili (non costanti fisiche): $h = 300$ W/m²K, $U = 0.3$ W/K, $T_a = 20$ °C, volume di ghiaccio di riempimento = volume del drink, dimensioni dei pezzi, ghiaccio a 0 °C, nessun ghiaccio che si riforma, nessuno scambio diretto fra il ghiaccio emerso e l'aria.

## 5. Bicchiere di servizio e capienza
`Recipe.glass` è un `GlassType` **facoltativo**; `Recipe.glassware` (default `GENERIC`) dice da quale catalogo viene (ADR-0013). Se il bicchiere ha misure (tutto tranne `OTHER`), pone un tetto al volume del drink servito. Ipotesi dichiarate in `domain/services/glassware.py`:

- **Capienza:** quella dichiarata dalla scheda del bicchiere nel catalogo (`GlassModel.capacity_ml`, a colmo).
- **Volume utile:** $V_{util} = C \cdot 0.9$ (bordo libero del 10%).
- **Spazio del ghiaccio** (`GlassFit.ice_volume_ml`): per cubetti e tritato una quota $s = 0.35$ dello spazio utile, $V_{ghiaccio} = V_{util}\,s$; per il pezzo unico il suo volume, $V_{ghiaccio} = V_{pezzo}$ (cubo grosso 125 ml, colonna 108 ml), che per la regola di compatibilità sta tutto sotto il bordo. Senza ghiaccio $V_{ghiaccio} = 0$. In ogni caso $V_{max} = V_{util} - V_{ghiaccio}$.
- **Vincolo:** $V_{final} \le V_{max}$ (disuguaglianza SLSQP, normalizzata su $V_{max}$). Se è presente anche il target `final_volume_ml` (uguaglianza) e $V_{target} > V_{max}$ il problema è `INFEASIBLE`.
- **Riempimento:** $\text{fill} = V_{final} / V_{max}$; oltre 1 il drink trabocca (`GlassFit.overflows`).

Limiti: $s$ tarato su drink classici serviti pieni (vale per il ghiaccio che riempie); l'acqua di fusione che si aggiunge dopo il servizio sta nel bordo libero.

**Profilo del bicchiere** (`domain/serving_geometry.py`, ADR-0013). Un bicchiere è un solido di rotazione con profilo $d(t) = D \cdot f(t)$, $t \in [0, 1]$ dal fondo della coppa alla bocca, dove $f$ è la curva della famiglia di forma (massimo 1) e $D$ il diametro massimo interno, quello della scheda meno due pareti da 2 mm. La profondità si ricava dalla capienza dichiarata:

$$H = \frac{V}{\frac{\pi}{4}\,D^2\,\langle f^2 \rangle}$$

con $\langle f^2 \rangle$ integrato sullo stesso profilo campionato (49 punti, trapezi su $d^2$), così $V_{profilo} = V_{scheda}$ per costruzione. Il resto dell'altezza totale è stelo e piede, o fondo pieno; una coppa che non sta nel bicchiere (meno di 3 mm di fondo) rende la scheda invalida.

**Compatibilità ghiaccio–bicchiere.** Un pezzo di lato $a$ e altezza $h_p$ ha bisogno di una sezione larga $a\sqrt{2} + 4$ mm. Si appoggia alla quota più bassa $z_0$ da cui **in su** ogni sezione è larga almeno così (deve passare per tutto ciò che sta sopra), e entra se

$$z_0 + h_p \le H$$

cioè se, appoggiato, non sporge. Se nemmeno la bocca è abbastanza larga, non entra. È un'invariante di `Recipe` (`IceDoesNotFitGlassError`), insieme all'esistenza del bicchiere nel catalogo (`GlassNotInCatalogueError`); senza bicchiere, o con `OTHER`, nessun ghiaccio è escluso. `GET /api/v1/glassware` espone cataloghi, profili e ghiacci compatibili.
