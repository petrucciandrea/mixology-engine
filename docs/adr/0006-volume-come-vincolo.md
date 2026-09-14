# ADR-0006 — Il volume finale è un vincolo, non un obiettivo pesato

**Stato:** accettata

## Contesto

La prima versione del solver trattava il volume finale come un termine
della funzione obiettivo, pesato 0.5 rispetto ai target organolettici. Il
solver poteva quindi scambiare volentieri qualche millilitro di troppo per
un ABV leggermente più preciso.

Ma il volume non è negoziabile come lo è un grado Brix: una coppa da 90 ml
ne contiene 90. Un drink che ne produce 110 trabocca, uno che ne produce 70
arriva al tavolo mezzo vuoto.

## Decisione

`target.final_volume_ml` diventa un **vincolo di uguaglianza** di SLSQP,
normalizzato sul target. Nella funzione obiettivo restano solo i target
organolettici: ABV, Brix, acidità e rapporto zuccheri/acidi.

I bounds per singolo ingrediente restano vincoli di disuguaglianza.

## Conseguenze

Il modello è più corretto e la formulazione più difendibile: si distingue
ciò che si desidera da ciò che si richiede.

Un vincolo può però essere **irrealizzabile** — tre ingredienti con tetto a
10 ml non riempiono un tiki mug da 500. Il solver lo rileva e restituisce
`SolverStatus.INFEASIBLE` invece di una ricetta plausibile e sbagliata.

L'ammissibilità si valuta sulla soluzione continua, prima
dell'arrotondamento al passo del dosatore: la quantizzazione a 0.5 ml è
attesa e non è un fallimento, e giudicarla con la stessa tolleranza
marcherebbe come irrisolvibili problemi risolti bene.

Quando il volume è l'*unico* target, il problema non è più
un'ottimizzazione ma un riscalamento: la soluzione esatta è moltiplicare
tutti i volumi per lo stesso fattore, perché ABV, Brix e acidità sono
invarianti per riscalamento (proprietà verificata con Hypothesis). Il
termine di regolarizzazione verso le proporzioni originali fa sì che il
solver trovi proprio quella.
