# ADR-0003 — Alembic con driver async e una sola `Base`

**Stato:** accettata

## Contesto

Il pattern standard di Alembic è sincrono, mentre l'applicazione usa
esclusivamente `AsyncEngine` con `asyncpg`. Mantenere due driver
significherebbe due URL, due set di credenziali e la possibilità concreta
che le migrazioni girino su un dialetto diverso da quello di produzione.

C'è inoltre un precedente istruttivo: in questo progetto esistevano *due*
classi `Base` distinte. I modelli ORM ereditavano dalla prima, `env.py`
ispezionava la seconda, i cui metadata erano vuoti. `--autogenerate`
produceva migrazioni senza tabelle e non segnalava nulla.

## Decisione

* `env.py` crea un `AsyncEngine` ed esegue le migrazioni dentro
  `connection.run_sync(...)`;
* l'URL è letto dalle stesse `Settings` dell'applicazione, non
  dall'`alembic.ini`: una sola fonte di verità, nessuna credenziale
  duplicata;
* **una sola `Base`**, in `infrastructure/db/base.py`. Il modo previsto di
  raggiungerla è `from app.infrastructure.db import Base`, perché importare
  il package registra anche tutti i modelli sui metadata;
* `compare_type=True`, altrimenti l'autogenerate ignora i cambi di tipo di
  colonna — esattamente il genere di modifica che ci si dimentica di
  scrivere a mano.

## Conseguenze

Le migrazioni girano sullo stesso driver dell'applicazione. L'autogenerate
è affidabile per costruzione: aggiungere un modello non richiede di
ricordarsi di importarlo altrove.

L'estensione `vector` resta l'unica cosa che l'autogenerate non può
dedurre: va scritta a mano come prima operazione della revisione iniziale,
perché il tipo `vector(32)` non esiste finché l'estensione non è attiva sul
database.
