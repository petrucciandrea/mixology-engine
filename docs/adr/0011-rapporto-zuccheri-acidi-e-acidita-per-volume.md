# ADR-0011 — Rapporto zuccheri/acidi da masse, giudizio solo per i sour, acidità per volume

**Stato:** accettata

## Contesto

Un controllo dei calcoli, partito dalla sensazione che alcuni drink
risultassero troppo dolci, ha trovato quattro difetti che si sommavano:

1. **Il rapporto non aveva significato fuori dai sour.** Gin Tonic e Negroni
   mostravano 85 e 44: zuccheri veri divisi per tracce d'acido (0.07 % e
   0.3 % p/v). L'unica guardia era una soglia anti-overflow (10⁻⁹).
2. **Il giudizio "dolce/aspro" valeva per ogni ricetta**, con la finestra
   5.5–7.0 pensata per i sour, anche se `Recipe.family` esiste. La finestra
   era inoltre duplicata nel frontend.
3. **La finestra era più stretta dei sour tradizionali.** Whiskey Sour 9.4,
   Last Word 10.0, Paper Plane 10.2 risultavano "dolci".
4. **Dati e unità incoerenti.** Il Brix del lime (7.5) era una lettura da
   rifrattometro, che conta anche l'acido; il limone (2.5) era a soli
   zuccheri. E l'acidità, dichiarata in % p/v, veniva moltiplicata per la
   densità e restituita come g/g, mentre l'interfaccia la etichettava "% w/v".

## Decisione

1. **Il rapporto è un quoziente di masse**: grammi di zucchero per grammo di
   acido. È adimensionale, indipendente dalla diluizione e dalla densità del
   drink. Brix (% peso) diviso acidità (% p/v) mescolerebbe due basi.
2. **Il rapporto esiste solo sopra `SUGAR_ACID_MIN_ACIDITY` = 0.5 % p/v**
   (pre-diluizione); sotto è `None`. È una soglia sensoriale, volutamente
   bassa: tiene fuori le tracce senza togliere il rapporto a un solver che
   sta aggiungendo acido. Il solver non la usa: ottimizza il residuo lineare
   `zuccheri − r·acidi` sulle masse, definito anche in acido nullo.
3. **Il giudizio è `assess_sour_balance(family, profile)`** in
   `domain/balance.py`: `TOO_TART | BALANCED | TOO_SWEET` solo per
   `RecipeFamily.SOUR` con rapporto definito, altrimenti `None`. Sostituisce
   `is_balanced_sour`. L'API espone `sour_balance` e gli estremi della
   finestra; il frontend non ne conosce i valori.
4. **La finestra è 3.5–12.0**, tarata sui classici del seed: sui 20 sour
   giudicabili il rapporto va da 3.8 (Margarita) a 10.7 (Penicillin); fuori
   resta solo l'Amaretto Sour (16.2), dolce per costruzione. La taratura è
   un test (`tests/unit/test_sour_balance.py`), non una dichiarazione.
5. **L'acidità è % p/v**: `M_acid = Σ V_i · acidity_i / 100`, senza densità;
   `acidity_pre = M_acid / V_tot`, `acidity_post = M_acid / V_final`. Il Brix
   resta % peso. Vale anche per `ServingProfile.acidity`.
6. **Il Brix degli ingredienti è la massa di zucchero**, non la lettura del
   rifrattometro. Il seed corregge lime (7.5 → 1.7), pompelmo (9 → 8),
   frutto della passione (14 → 11) e mirtillo rosso (14 → 13). Per i database
   già popolati, `SUPERSEDED_PROFILES` in `scripts/seed.py` ricorda il valore
   precedente e il seed riallinea un ingrediente **solo se** il suo profilo
   salvato coincide ancora con quello: un dato ritoccato a mano non si tocca.

## Conseguenze

- Gin Tonic, Negroni e gli altri drink con acidi in tracce mostrano "—" invece
  di 85 o 44; Screwdriver, Spritz e Mimosa non hanno più un giudizio.
- Daiquiri 60/30/20: rapporto 7.9 → 7.1, Brix servito 8.7 → 7.6 °Bx.
- `acidity_post` cambia di ~3-5 % sui drink con succhi: i target di acidità
  del solver sono ora in % p/v, coerenti con l'etichetta mostrata.
- Cambio di contratto API: `is_balanced_sour` (bool) diventa `sour_balance`
  (enum nullable), più `sour_ratio_lower_bound` e `sour_ratio_upper_bound`.
- Altri succhi (arancia, ananas, mela, pesca, pomodoro) restano alle letture
  attuali: da rivedere con lo stesso criterio quando si avrà una fonte.
- I coefficienti dello stirred in `dilution.py` (−1.150/1.350/0.150) non
  sono stati toccati: differiscono da quelli comunemente citati per Arnold
  (−1.21/1.246/0.145) e vanno verificati sul testo primario prima di cambiarli.
