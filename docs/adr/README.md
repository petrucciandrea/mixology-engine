# Architecture Decision Records

Ogni file registra una decisione: il contesto in cui è stata presa, cosa
si è deciso, e cosa si è accettato in cambio. Sono documenti immutabili —
una decisione che cambia non si riscrive, si supera con un ADR nuovo che
dichiara quale sostituisce.

| ADR | Decisione | Stato |
|-----|-----------|-------|
| [0001](0001-solver-separato-dal-matcher.md) | Il solver calcola i volumi, il matcher sceglie gli ingredienti | Accettata |
| [0002](0002-solver-fuori-dall-event-loop.md) | SLSQP gira su thread pool via `asyncio.to_thread` | Accettata |
| [0003](0003-alembic-async.md) | Alembic con driver async e una sola `Base` | Accettata |
| [0004](0004-dominio-puro-dto-separati.md) | Dominio in dataclass pure, DTO Pydantic solo nell'API | Accettata |
| [0005](0005-vettore-di-sapore-a-descrittori.md) | Profilo organolettico a descrittori espliciti, non embedding | Accettata |
| [0006](0006-volume-come-vincolo.md) | Il volume finale è un vincolo, non un obiettivo pesato | Accettata |
| [0007](0007-matcher-similarita-e-affinita.md) | Il matcher tiene separate similarità (sostituzione) e affinità (abbinamento) | Accettata |
