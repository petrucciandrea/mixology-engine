# ADR-0012 — Ghiaccio di servizio: bilancio a due nodi, colonna e compatibilità col bicchiere

**Stato:** accettata
**Sostituisce:** la cinetica del ghiaccio di servizio di ADR-0008 (sezione
"Aggiornamento: il tipo di ghiaccio entra nel calcolo"); il resto di
ADR-0008 resta valido.

## Contesto

Nello studio, cambiare il tipo di ghiaccio non cambiava la curva di
diluizione nel tempo. Non era un errore di collegamento, era il modello di
ADR-0008:

- il tipo di ghiaccio entrava solo nella costante di tempo del
  *raffreddamento* fino all'equilibrio, un termine nullo per shaken e
  stirred (escono dalla preparazione già al punto di congelamento);
- il calore dall'ambiente era una potenza fissa (6 W) che fondeva ghiaccio
  direttamente, qualunque fosse la superficie, e quindi identica per tutti
  i tipi;
- su un built il transitorio si chiudeva nei primi 2–5 minuti di una curva
  di 30, e da lì le curve coincidevano.

Il risultato era "fisicamente coerente con le ipotesi", ma le ipotesi
escludevano per costruzione l'effetto che un barman si aspetta: con poca
superficie (un cubo grosso) il drink resta più caldo e diluisce meno.

Due richieste si sono aggiunte: un ghiaccio a colonna per i bicchieri alti e
stretti, e l'esclusione automatica dei ghiacci che non entrano nel
bicchiere (il cubo grosso nel Collins o in una coppetta, la colonna nel
tumbler basso).

## Decisione

### 1. Bilancio termico a due nodi

Il calore segue un percorso solo, **ambiente → drink → ghiaccio**:

- dal vetro al drink entra $U\,(T_a - T)$, con $U = 0.3$ W/K (gli stessi
  6 W di prima a 0 °C, ma un drink più freddo ne richiama di più);
- dal drink al ghiaccio passa $h\,A\,(T - T_f)$, con $T_f$ il punto di
  congelamento della miscela *attuale* e $A$ la superficie residua del
  ghiaccio, $A_0\,(m/m_0)^{2/3}$ (ogni pezzo fonde restando simile a sé).

È un'equazione differenziale senza soluzione chiusa. Si integra nel dominio
(solo stdlib) con un passo di 1 s su una griglia fissa:

- la temperatura segue, a coefficienti congelati nel passo, l'esponenziale
  esatto dell'equazione linearizzata, **stabile per qualunque passo** (con
  pezzi piccoli e drink minuscoli la costante di tempo scende sotto il
  secondo);
- la fusione **non si integra**: si ricava dalla conservazione
  dell'entalpia, $(C_0 + m\,c_w)\,T + L\,m = C_0\,T_s + Q_{amb}$, che così
  vale esattamente a ogni passo ed è il controllo principale dei test;
- la griglia fissa fa sì che un punto della curva e il profilo allo stesso
  minuto coincidano bit per bit.

Esaurito il ghiaccio, il drink si scalda verso l'ambiente (prima la
temperatura restava congelata all'ultimo equilibrio).

### 2. La massa del ghiaccio dipende dal tipo

Il ghiaccio che *riempie* (cubetti, tritato) resta pari al volume del
drink. Il **pezzo unico** (cubo grosso, colonna) pesa quanto il pezzo,
qualunque sia il drink: una colonna in un highball da 250 ml non è 250 ml
di ghiaccio.

### 3. La colonna è un tipo a sé

`ServingIce.SPEAR` ("Colonna", 30 × 30 × 120 mm), non una variante del
cubo. Ha geometria, superficie specifica (150 m⁻¹ contro 120 del cubo
grosso) e bicchieri compatibili propri. Un flag "variante" su `LARGE_CUBE`
ammetterebbe stati senza significato (variante colonna di un cubetto), lo
stesso argomento per cui ADR-0008 tiene assenza e tipo in un solo enum.

### 4. Compatibilità ricavata dalla geometria

`domain/serving_geometry.py` descrive i pezzi come prismi a base quadrata
e i bicchieri come tronchi di cono (fondo, bocca, profondità; per calice e
balloon il "fondo" è la pancia). Un pezzo entra se non sporge e se,
appoggiato il più in alto possibile, la sezione ne contiene la diagonale
più 4 mm di gioco; per un bicchiere che si stringe decide la bocca.

Si è preferita una regola a una tabella scritta a mano perché è
verificabile (le misure si accordano con le capienze di ADR-0009 entro il
10%, ed è un test) e perché un bicchiere nuovo eredita la compatibilità
dalle sue misure invece che da una scelta da ricordare.

### 5. È un'invariante dell'aggregate

`Recipe` rifiuta un ghiaccio che non entra nel bicchiere
(`IceDoesNotFitGlassError`, sottoclasse di `InvalidRecipeError`, 422). Il
modulo di geometria importa solo `enums`, così `entities` ne dipende senza
cicli. Senza bicchiere, o con `OTHER`, nessun ghiaccio è escluso.

L'editor non rifà la geometria: `GET /api/v1/glassware` restituisce per
ogni bicchiere capienza e ghiacci compatibili, e lo studio disabilita gli
altri. Cambiando bicchiere, un ghiaccio che non entra più diventa cubetti
se entrano, altrimenti "senza ghiaccio"; con lo stesso ripiego una
migrazione di dati riallinea le ricette salvate.

## Conseguenze

- Cambiare ghiaccio ora sposta la curva anche per shaken e stirred: a 30
  minuti, un Daiquiri su tritato è ~1.4 °C più freddo che su cubo grosso
  ed è diluito di ~5 ml in più. Su un built la differenza resta per tutta
  la curva.
- `ServingProfile` cambia: `cooling_melt_water_ml` e `ambient_melt_water_ml`
  spariscono (nel modello accoppiato la fusione non si divide per causa
  senza arbitrio), `equilibrium_temperature_c` diventa `freezing_point_c`
  (della miscela attuale) e si aggiunge `ambient_heat_j`, che rende la
  legge di conservazione verificabile da fuori. È un cambio di contratto,
  riportato in `frontend/src/types/api.ts`.
- Una curva costa ~2000 passi (pochi millisecondi): resta nella coroutine,
  come il calcolo del profilo (ADR-0002).
- Limiti dichiarati, da tarare o rimuovere con dati misurati: ghiaccio di
  servizio a 0 °C, nessun ghiaccio che si riforma, ghiaccio sopra il livello
  del liquido che non scambia con l'aria, tritato senza una densità di
  impacchettamento propria (stessa massa dei cubetti), misure dei bicchieri
  tipiche e non di produttore. La quota di spazio occupata dal ghiaccio nel
  bicchiere (ADR-0009) resta la stessa per tutti i tipi.
