# CLAUDE.md — Frontend (`frontend/src/`)

- `types/api.ts`: contratto HTTP **scritto a mano** (non generato), con nomi e
  commenti di dominio. Un cambio di DTO sul backend va riportato qui.
- `lib/api.ts`: unico punto che conosce la rete; gli errori diventano
  `ApiError` con `type` e `message` dal formato `{error: {type, message}}`.
- Bozza e archivio sono due hook: `useRecipe` governa la ricetta sul banco
  (con `recipeId` se deriva da una salvata), `useRecipeBook` l'elenco su
  `/recipes`. "Salva" fa PUT se `recipeId` c'è, altrimenti POST.
- Il browser chiama `/api/v1` sulla stessa origine della pagina; il server
  Next la inoltra al backend (`rewrites` in `next.config.ts`, destinazione
  `BACKEND_INTERNAL_URL`, in Docker `http://backend:8000`). Niente CORS e
  niente IP nel bundle: lo studio si apre anche da altri dispositivi in
  rete. Le rewrite si fissano a build time (argomento di build nel
  Dockerfile).
- `useSolver` governa target ed esito dell'ottimizzazione: l'esito si
  applica subito al dosaggio (`review`, con Mantieni/Ripristina); ogni
  modifica a mano passa da `invalidate()` nella pagina, che scarta le
  risposte superate.
- Nessuna fisica nel frontend: profili, curva di servizio nel tempo
  (`serving_curve`) e riempimento arrivano da `/balance`. Lato client
  restano solo rappresentazione (`lib/flavor.ts`, interpolazioni dei
  disegni in `useTweenedVolumes` e `useGlassShape`).
- I ghiacci compatibili con ciascun bicchiere arrivano da `/glassware`
  (`lib/serving.ts`): lo studio disabilita gli altri e, cambiando
  bicchiere, sostituisce un ghiaccio che non entra più (cubetti, se no
  senza ghiaccio). La geometria resta al backend.

Prossimo pezzo aperto: vista a rete del grafo dei sapori (D3) sopra
`/match/graph` e `/match/bridge`, già pronti.
