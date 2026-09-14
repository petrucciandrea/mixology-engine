# ADR-0007 — Il matcher tiene separate similarità e affinità

**Stato:** accettata

## Contesto

Il matcher deve rispondere a due domande che sembrano la stessa e non lo
sono:

* *"con cosa posso sostituire il lime?"* — il candidato deve **somigliare**
  all'originale;
* *"cosa ci sta bene con il gin?"* — il candidato non deve somigliare a ciò
  che c'è già.

Un unico punteggio di similarità produce il fallimento classico dei
raccomandatori applicati al cibo: suggerire il limone a chi ha già il lime.
Sono organoletticamente vicinissimi, quindi qualunque metrica di similarità
li accoppia — e nel bicchiere sono ridondanti, non complementari.

## Decisione

Due meccanismi distinti, con implementazioni diverse.

**Sostituzione — similarità, servita da pgvector.** Ricerca per prossimità
del coseno sull'indice HNSW, poi riordino nel dominio. Il punteggio finale
è il **prodotto** di due assi:

* similarità organolettica (coseno sul vettore di sapore);
* compatibilità fisica (distanza normalizzata su ABV, Brix e acidità,
  convertita in `1/(1+d)`).

Prodotto e non media: una media lascerebbe passare con 0.5 uno sciroppo al
lime, che sa esattamente di lime e si comporta in modo opposto. Il prodotto
richiede che nessuno dei due assi sia prossimo a zero.

**Abbinamento — affinità, servita da un grafo NetworkX.** Nodi gli
ingredienti, archi pesati da due segnali:

* *co-occorrenza nelle ricette*, normalizzata come coseno sull'incidenza
  (`n_ij / √(n_i·n_j)`), altrimenti lo sciroppo semplice risulterebbe il
  miglior compagno di chiunque;
* *aromi condivisi*, coseno ristretto al blocco delle 23 famiglie
  aromatiche — è l'ipotesi del food pairing resa operativa.

Gusti base e sensazioni tattili sono esclusi dal calcolo dell'affinità: due
sciroppi sono entrambi dolcissimi e due distillati hanno entrambi calore
alcolico, ma quelle coincidenze alzerebbero uniformemente tutti i pesi, che
equivale a non misurare nulla.

## Conseguenze

**Perché un grafo e non una classifica.** Le domande interessanti sono
relazionali. "Cosa aggiungo a questi tre ingredienti *insieme*" è una
propagazione sulla rete, e il PageRank personalizzato premia il candidato
moderatamente affine a tutti i semi sopra quello fortissimamente affine a
uno solo — il comportamento giusto per un drink, dove ogni componente deve
convivere con tutte le altre. "Come arrivo dal mezcal all'orgeat" è un
cammino, e fuori da un grafo non ha formulazione.

Il cammino si calcola su `-log(peso)`: sommare logaritmi equivale a
moltiplicare affinità, quindi il percorso più corto è quello che
**massimizza il prodotto** delle affinità. Minimizzare la somma dei pesi
grezzi darebbe la risposta opposta, preferendo i legami deboli.

**Ridondanza.** Il suggeritore scarta i candidati la cui similarità
complessiva con un ingrediente già presente supera 0.90. È il filtro che
impedisce di proporre il limone a chi ha il lime, e va tenuto distinto
dall'affinità: i due sono fortemente affini *e* ridondanti insieme.

**Potatura.** Gli archi sotto 0.08 vengono scartati. Quasi ogni coppia
condivide *qualche* aroma, e un grafo quasi completo non contiene
informazione: ogni cammino diventa diretto e il PageRank tende
all'uniforme.

**Costi.** La costruzione è O(n²) sulle coppie di ingredienti profilati.
Con una dispensa da bar è questione di millisecondi; il grafo è comunque
messo in cache su Redis con chiave l'impronta dei suoi ingressi, così
l'invalidazione è automatica e non c'è modo di dimenticarsi di svuotarla.
Una cache irraggiungibile degrada la latenza, mai la disponibilità.

**Limite noto.** Il segnale di co-occorrenza è conservativo per
costruzione: conosce solo ciò che è già stato scritto. Su una base di
ricette piccola il grafo è quasi interamente guidato dagli aromi, ed è la
ragione per cui i due segnali convivono invece di scegliere il più
affidabile.
