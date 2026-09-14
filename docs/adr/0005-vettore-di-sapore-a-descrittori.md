# ADR-0005 — Profilo organolettico a descrittori espliciti, non embedding

**Stato:** accettata
**Sostituisce:** la colonna `vector(38)` non documentata della prima versione

## Contesto

Il profilo organolettico serve al matcher per trovare ingredienti simili e
sostituzioni sensate. La prima versione dichiarava `vector(38)` senza
spiegare cosa fossero le 38 componenti, mentre la configurazione puntava a
`all-MiniLM-L6-v2`, che produce vettori a **384** dimensioni: i due valori
raccontavano due progetti diversi.

Le opzioni erano tre: embedding testuale di schede di degustazione,
tassonomia di descrittori compilata a mano, oppure entrambe.

## Decisione

Un vettore a **32 descrittori espliciti**, definito in
`domain/flavor.py` e organizzato in tre famiglie:

* 5 gusti fondamentali (dolce, acido, amaro, salato, umami);
* 4 sensazioni trigeminali e tattili (calore alcolico, astringenza,
  raffreddamento, pungenza);
* 23 famiglie aromatiche (agrumato, erbaceo, tostato, affumicato…).

Ogni componente è un'intensità in [0, 1].

## Conseguenze

**Interpretabilità.** La similarità fra due ingredienti si può spiegare a
voce: "differiscono soprattutto su `smoke` e `warm_spice`". Due embedding
vicini dicono soltanto che le *descrizioni testuali* si somigliano.

**Determinismo.** Lo stesso ingrediente produce sempre lo stesso vettore: i
test sono ripetibili e le migrazioni non dipendono dalla versione di un
modello.

**Peso.** Non trascina `torch` nell'immagine Docker, che su Mac Intel
x86_64 costerebbe qualche GB e diversi minuti di build.

Il prezzo è che i vettori vanno compilati a mano, o derivati da schede di
degustazione strutturate: non c'è generazione automatica. Per una dispensa
di qualche decina di ingredienti è lavoro di un pomeriggio; per migliaia,
andrebbe riconsiderato — ed è allora che la terza opzione (due colonne, una
tassonomica e una da embedding) tornerebbe sul tavolo.

**Vincoli operativi.** La dimensione è parte dello schema: la colonna è
`vector(32)`, e aggiungere un descrittore richiede una migrazione che
riscriva la colonna. L'ordine di `FLAVOR_DESCRIPTORS` è significativo e non
va cambiato. Un test fissa entrambe le cose.
