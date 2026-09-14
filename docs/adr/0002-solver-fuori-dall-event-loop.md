# ADR-0002 — SLSQP gira su thread pool, non nell'event loop

**Stato:** accettata

## Contesto

Lo stack è interamente asincrono (FastAPI, asyncpg, redis.asyncio) e gira
in un solo processo con un solo event loop. Il solver è invece puramente
CPU-bound: con il multi-start attivo esegue qualche centinaio di
valutazioni della funzione obiettivo, per decine di millisecondi.

Una coroutine che occupa il loop per 50 ms mette in coda *ogni* altra
richiesta del processo per 50 ms — inclusi gli health check letti
dall'orchestratore.

## Decisione

I casi d'uso che invocano il solver lo fanno con `asyncio.to_thread`.

## Conseguenze

L'event loop resta libero durante l'ottimizzazione. Il parallelismo è
reale e non solo apparente: SciPy rilascia il GIL nelle routine numeriche,
quindi più ottimizzazioni concorrenti usano davvero più core.

Il calcolo del solo profilo di bilanciamento resta invece nella coroutine:
sono poche somme su pochi ingredienti, nell'ordine dei microsecondi, e
spostarle su un thread costerebbe più della loro esecuzione.

Se in futuro il carico crescesse oltre quello che il thread pool regge, il
passo successivo è una coda di lavoro (Celery, ARQ) — ma la firma dei casi
d'uso non cambierebbe.
