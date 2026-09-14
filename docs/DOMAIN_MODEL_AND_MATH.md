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