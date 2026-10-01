# ADR-0009 — Il bicchiere è un attributo facoltativo della ricetta e ne limita il volume

**Stato:** accettata

## Contesto

Una ricetta dice come si prepara (`DilutionMethod`) e se c'è ghiaccio nel
bicchiere (`ServingIce`, ADR-0008), ma non *in che bicchiere* si serve. È
un'informazione di servizio che il bar dà per scontata — una coppa, un
highball — e che ha anche una conseguenza fisica: il bicchiere ha una
capienza, e il solver, che può scegliere qualunque volume finale, non ne
sapeva nulla (ADR-0006: "una coppa da 90 ml ne contiene 90").

## Decisione

1. **`GlassType`** è un enum chiuso (`COUPE`, `MARTINI`, `ROCKS`, `HIGHBALL`,
   `BALLOON`, …, `OTHER`), come `ServingIce`. Una tabella/entità dedicata
   servirebbe solo se il bicchiere portasse dati propri modificabili a
   runtime; la capienza è una costante di dominio per tipo.
2. **`Recipe.glass: GlassType | None = None`.** A differenza di
   `serving_ice` è *facoltativo*: ometterlo non rende falsa nessuna
   affermazione, significa solo "nessun tetto". Nel database la colonna è
   nullable e senza default; nei DTO è opzionale.
3. **Il bicchiere limita il volume.** `domain/services/glassware.py`
   calcola il volume massimo del drink: capienza × 0.9 di bordo libero, e
   con ghiaccio di servizio ridotto della quota occupata dal solido
   (`ICE_SHARE_OF_USABLE_VOLUME` = 0.35). `OTHER` non ha capienza e non
   limita.
4. **Nel solver è un vincolo di disuguaglianza** `V_final ≤ V_max`, che si
   somma all'uguaglianza su `final_volume_ml` se presente. Il solver non
   sceglie né cambia il bicchiere: lo legge dalla ricetta (ADR-0001 resta
   intatto). Un target di volume sopra la capienza dà `INFEASIBLE`, con un
   messaggio che nomina il bicchiere.
5. **`BalanceResult.glass_fit`** (`GlassFit`: capienza, massimo, volume,
   `fill_ratio`, `overflows`) espone il riempimento anche senza ottimizzare,
   così l'editor può avvisare mentre si muovono gli slider.

## Conseguenze

- Ricette e migrazioni esistenti restano valide senza toccare nulla; il
  seed assegna il bicchiere ai classici, e un test di sistema (tutti i 55
  entrano nel loro bicchiere) ha guidato la taratura delle costanti.
- **La quota di ghiaccio non è `ICE_VOLUME_PER_DRINK_VOLUME`.** Quella è la
  massa termica disponibile al raffreddamento (ADR-0008); riusarla come
  spazio occupato (1:1) dava overflow su drink classici normalissimi.
  Sono due grandezze diverse e restano due costanti.
- La capienza si valuta sulla soluzione continua, come il volume (ADR-0006);
  l'arrotondamento al dosatore può superarla di pochi ml, assorbiti dal
  bordo libero.
- Le capienze sono valori tipici per tipo, non misure: da tarare. Una
  capienza specifica per bicchiere (di un bar) richiederebbe un'entità e
  un nuovo ADR che superi questo.
- Non cambia la diluizione né il `ServingProfile`: il bicchiere non entra
  nella termodinamica.
