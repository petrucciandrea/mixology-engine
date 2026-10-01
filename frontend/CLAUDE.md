# CLAUDE.md — Frontend (`frontend/src/`)

- `types/api.ts`: contratto HTTP **scritto a mano** (non generato), con nomi e
  commenti di dominio. Un cambio di DTO sul backend va riportato qui.
- `lib/api.ts`: unico punto che conosce la rete; gli errori diventano
  `ApiError` con `type` e `message` dal formato `{error: {type, message}}`.
- Bozza e archivio sono due hook: `useRecipe` governa la ricetta sul banco
  (con `recipeId` se deriva da una salvata), `useRecipeBook` l'elenco su
  `/recipes`. "Salva" fa PUT se `recipeId` c'è, altrimenti POST.
- Il browser raggiunge il backend via `NEXT_PUBLIC_API_URL` (porta
  pubblicata), non l'hostname `backend`.

Prossimo pezzo aperto: vista a rete del grafo dei sapori (D3) sopra
`/match/graph` e `/match/bridge`, già pronti.
