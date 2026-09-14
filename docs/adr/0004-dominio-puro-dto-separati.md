# ADR-0004 — Dominio in dataclass pure, DTO Pydantic solo nell'API

**Stato:** accettata

## Contesto

Le entità di dominio erano modelli Pydantic con `from_attributes=True`,
pensati per essere serializzati direttamente dall'API. Comodo, ma con due
conseguenze: il cuore del sistema dipendeva da una libreria del layer di
interfaccia, e il modello interno sarebbe diventato il contratto pubblico —
ogni rinomina interna, un breaking change per i client.

## Decisione

* `domain/` usa `dataclass` frozen della sola libreria standard, con
  validazione negli `__post_init__`. Nessun import di Pydantic, SQLAlchemy,
  FastAPI o SciPy;
* `api/schemas/` contiene DTO Pydantic distinti, con conversione esplicita
  (`from_entity`, `to_domain`) nel layer che conosce entrambi i mondi.

## Conseguenze

La regola di dipendenza diventa verificabile e non solo dichiarata: i test
di dominio girano senza database, senza Redis e senza variabili
d'ambiente, e ci mettono un secondo.

Si paga una conversione esplicita da mantenere, e la validazione è scritta
due volte: una nel dominio (la regola) e una nei DTO (il messaggio di
errore e la documentazione OpenAPI). La duplicazione è limitata ai soli
intervalli numerici, che i DTO attingono dalle costanti del dominio invece
di riscrivere.

Un'entità che esiste è un'entità valida: non c'è modo di costruirne una in
stato illegale, nemmeno da un test.
