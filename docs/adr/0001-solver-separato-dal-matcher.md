# ADR-0001 — Il solver calcola i volumi, il matcher sceglie gli ingredienti

**Stato:** accettata

## Contesto

"Creare un cocktail equilibrato" comprende due domande diverse: *quali*
ingredienti usare, e *quanto* metterne. Trattarle insieme produrrebbe un
problema di ottimizzazione misto — variabili intere per la selezione,
continue per i volumi — mal condizionato e difficile da spiegare.

## Decisione

Due componenti separate, con contratti distinti:

* il **solver** (`application/solver/`) riceve un insieme fisso di
  ingredienti e cerca il vettore dei volumi che serve i target. Puramente
  continuo, vincolato, risolto con SLSQP;
* il **matcher** (pgvector + NetworkX, da realizzare) propone *quali*
  ingredienti mettere sul tavolo, per similarità organolettica e per
  affinità di abbinamento.

## Conseguenze

Il problema del solver resta ben posto: gli ingredienti fissano le colonne
della matrice, e si cerca solo il vettore x. Ogni componente è testabile in
isolamento — il solver senza database, il matcher senza SciPy.

Il costo è che il sistema non risponde in un colpo solo alla domanda
"inventami un drink": serve comporre le due fasi. È un costo accettabile,
ed è anche il flusso di lavoro reale di chi crea ricette, che sceglie gli
ingredienti e poi ne aggiusta le dosi.
