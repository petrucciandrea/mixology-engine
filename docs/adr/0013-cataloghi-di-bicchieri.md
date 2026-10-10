# ADR-0013 — Cataloghi di bicchieri reali, profilo ricavato dalla capienza

**Stato:** accettata
**Sostituisce:** la tabella delle capienze di ADR-0009 (punto 3, la
capienza come costante per tipo), la quota di ghiaccio di ADR-0009 per i
pezzi unici, e la geometria a tronco di cono di ADR-0012 (punto 4).
Restano validi il bordo libero e la quota per cubetti e tritato di
ADR-0009, la regola di compatibilità e l'invariante di ADR-0012.

## Contesto

Una revisione delle misure ha trovato due difetti diversi.

- **Nel disegno**: ogni bicchiere aveva la sua scala (da 1.0 a 1.5 px/mm,
  diversa anche fra altezza e larghezza), e le sagome non coincidevano con
  la geometria del backend. Calice e balloon apparivano troppo larghi.
- **Nelle misure vere**: il tronco di cono non sa rappresentare una coppa
  arrotondata o un calice che si stringe. Per far tornare la capienza, le
  profondità erano state accorciate (calice 90 mm contro i ~110 reali):
  numeri tarati a mano, non misure.

Non esiste uno standard normativo per i bicchieri da bar (l'unico è il
calice da degustazione ISO 3591, uno strumento d'analisi). Lo standard di
fatto sono le linee professionali dei produttori.

## Decisione

### 1. Cataloghi di linee reali

`Glassware` elenca i cataloghi: `GENERIC` e tre linee di fascia alta
diffuse nei cocktail bar italiani, **Luigi Bormioli** (Mixology, Bach,
Atelier, Magnifico), **Schott Zwiesel** (Bar Selection di Charles Schumann,
Ivento) e **Nude** (Savage, Refine, Stem Zero). Ogni bicchiere
(`GlassModel`) riporta le misure **come pubblicate** (capienza a colmo,
altezza totale, diametro massimo esterni), il nome del prodotto e la fonte.

Una linea contiene solo i bicchieri che produce davvero: nessuna delle tre
ha mug di rame o tiki. Il catalogo generico copre ogni tipo con misure
tipiche, dichiarate come tali. Le schede incoerenti (una capienza che non
sta nelle misure dichiarate) restano fuori invece di essere aggiustate: è
il caso del Big Top Collins e dello shot Finesse di Nude.

### 2. Il profilo si ricava, non si inserisce

Le schede non danno quasi mai la profondità della coppa. Il profilo nasce
da tre ingredienti:

- una **famiglia di forma** (`GlassShape`: tumbler, coppa, cono, campana,
  tulipano, balloon, flûte, tiki, hurricane), una curva normalizzata;
- il **diametro massimo interno**, quello della scheda meno due pareti da
  2 mm;
- la **capienza**, da cui si ricava la profondità:
  $H = V / (\pi/4 \cdot D^2 \cdot \langle f^2 \rangle)$.

Il volume si integra sullo stesso profilo campionato, quindi profilo e
capienza coincidono per costruzione. Il resto dell'altezza è stelo e piede,
o fondo pieno. Una coppa più profonda del bicchiere fa fallire la
costruzione del modello.

I rapporti di forma che la scheda non dà (bocca/pancia di un tulipano,
rastremazione di un tumbler) prendono un valore tipico, e `estimated` li
elenca.

### 3. Il catalogo è un dato della ricetta

`Recipe.glassware` (default `GENERIC`) è salvato con la ricetta. Una
ricetta bilanciata in un Nick & Nora di Schott Zwiesel deve dare gli stessi
numeri domani, qualunque catalogo scelga chi apre lo studio. Le invarianti
dell'aggregate diventano due:

- il bicchiere deve esistere nel catalogo (`GlassNotInCatalogueError`);
- il ghiaccio deve entrarci (`IceDoesNotFitGlassError`).

`OTHER` resta senza misure in ogni catalogo.

Le impostazioni dello studio scelgono la linea per le bozze nuove (una
preferenza del browser, non del server); sceglierne una la applica anche
alla bozza aperta, con gli stessi ripieghi del cambio di bicchiere.

### 4. Una geometria, un disegno

`GET /api/v1/glassware` restituisce i cataloghi con il profilo calcolato.
Lo studio li disegna a **una scala comune in mm**, ghiaccio compreso, invece
di sagome proprie: le sagome stilizzate restano solo per le icone e per i
bicchieri senza misure.

### 5. Il pezzo unico occupa il suo volume

Lo spazio del ghiaccio nel bicchiere era il 35% del volume utile per ogni
tipo. Per cubetti e tritato è una quota tarata (si impilano lasciando
vuoti, e il pezzo che sporge sopra il livello sposta meno di quanto pesa).
Per il pezzo unico è sbagliata: il cubo grosso è un solido da 125 ml che,
per la regola di compatibilità, sta tutto sotto il bordo. In un tumbler
generico da 300 ml la quota gli dava 94.5 ml, e un drink che sembrava
entrare traboccava.

Cubo grosso e colonna sottraggono ora il loro volume vero
(`services/glassware.ice_space_ml`). La verifica di tutti i classici del
seed nel loro bicchiere, che ADR-0009 citava ma non era nel repository,
diventa un test: ha spostato Penicillin e Gold Rush (176 e 162 ml contro i
145 che restano accanto al cubo) nel doppio tumbler, dove molti bar li
servono. Il seed li sposta solo se la ricetta salvata ha ancora il
tumbler basso.

## Conseguenze

- La compatibilità del ghiaccio dipende dalla linea, com'è giusto. Il
  tumbler basso di Schott Zwiesel (Ø 82 mm, rastremato) non accoglie il cubo
  da 50 mm, il doppio sì. Con la colonna da 120 mm sono abbastanza
  profondi solo i long drink Bormioli, gli hurricane e il Collins
  generico; highball e Collins di Schott Zwiesel e Nude hanno coppe da
  100–117 mm. È un'ipotesi sulla colonna (ADR-0012) che i dati rendono
  visibile.
- Le misure vengono dai distributori più che dai produttori, che raramente
  le pubblicano. Una misura su un esemplare o un disegno tecnico vale più di
  qualunque scheda, e sostituisce la riga senza toccare il codice.
- La migrazione aggiunge `glassware` con `GENERIC` per le ricette
  esistenti. Le due coppie generiche che con le nuove misure non entrano
  più (colonna nell'highball, cubo grosso nel tiki) passano a cubetti.
- Restano ipotesi dichiarate: lo spessore di parete unico, le curve delle
  famiglie di forma, il piede disegnato in proporzione al diametro.
