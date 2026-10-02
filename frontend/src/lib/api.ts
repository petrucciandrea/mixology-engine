/**
 * Client HTTP tipizzato.
 *
 * Unico punto in cui l'interfaccia conosce l'esistenza della rete: i
 * componenti chiamano funzioni con nomi di dominio e ricevono tipi, non
 * `Response` da interpretare. Lo stesso principio del repository sul
 * backend — il resto del codice non sa che esiste un protocollo.
 */

import type {
  BalanceResponse,
  FlavorDescriptors,
  Ingredient,
  IngredientCategory,
  Page,
  PairingSuggestion,
  Recipe,
  RecipeInput,
  SolverResult,
  SolverSettingsInput,
  Substitution,
  TargetProfileInput,
} from "@/types/api";

/**
 * L'API si chiama sulla stessa origine della pagina: è il server Next a
 * inoltrarla al backend (`rewrites` in `next.config.ts`). Il bundle non
 * contiene indirizzi, il browser non fa richieste cross-origin, e la stessa
 * pagina funziona da `localhost` come dal telefono sulla rete locale.
 */
const API = "/api/v1";

/**
 * Errore che conserva ciò che il backend ha detto.
 *
 * Il backend risponde con `{error: {type, message}}`: `type` è stabile e
 * serve a ramificare, `message` è scritto per essere letto. Perderli e
 * mostrare "qualcosa è andato storto" butterebbe via l'unica informazione
 * utile a chi sta usando l'applicazione.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly type: string;

  constructor(status: number, type: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    // Distinguere "il server non risponde" da "il server ha detto no" è la
    // differenza fra "controlla che lo stack sia avviato" e "correggi i dati".
    throw new ApiError(0, "NetworkError", "Backend non raggiungibile");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, ...describeFailure(response.status, body));
  }

  return body as T;
}

/** Estrae tipo e messaggio dalle due forme di errore che il backend produce. */
function describeFailure(status: number, body: unknown): [string, string] {
  if (isRecord(body)) {
    // Errore di dominio: {error: {type, message}}
    const domain = body.error;
    if (isRecord(domain) && typeof domain.message === "string") {
      const type = typeof domain.type === "string" ? domain.type : "DomainError";
      return [type, domain.message];
    }
    // Errore di validazione di FastAPI: {detail: ...}
    if (typeof body.detail === "string") {
      return ["ValidationError", body.detail];
    }
    if (Array.isArray(body.detail)) {
      return ["ValidationError", summariseValidation(body.detail)];
    }
  }
  // Un 5xx senza corpo JSON non viene dal backend, che risponde sempre nel
  // suo formato: è il proxy di Next che non l'ha raggiunto, o un crash
  // prima che il backend potesse rispondere.
  if (status >= 500) {
    return ["BackendUnavailable", "Backend non raggiungibile o in errore"];
  }
  return ["HttpError", `Richiesta fallita con stato ${status}`];
}

function summariseValidation(details: unknown[]): string {
  const messages = details
    .filter(isRecord)
    .map((item) => (typeof item.msg === "string" ? item.msg : null))
    .filter((msg): msg is string => msg !== null);
  return messages.length > 0 ? messages.join("; ") : "Dati non validi";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// --- Dispensa ---------------------------------------------------------------

export function listIngredients(options?: {
  category?: IngredientCategory;
  limit?: number;
}): Promise<Page<Ingredient>> {
  const params = new URLSearchParams({ limit: String(options?.limit ?? 200) });
  if (options?.category) params.set("category", options.category);
  return request<Page<Ingredient>>(`/ingredients?${params.toString()}`);
}

export function getFlavorDescriptors(): Promise<FlavorDescriptors> {
  return request<FlavorDescriptors>("/ingredients/flavor-descriptors");
}

// --- Ricettario -------------------------------------------------------------

/** Il default è il massimo accettato dal backend: il ricettario di un bar
    sta in una pagina, e paginare un elenco di poche decine di voci
    aggiungerebbe solo clic. */
export function listRecipes(options?: {
  limit?: number;
  offset?: number;
}): Promise<Page<Recipe>> {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 200),
    offset: String(options?.offset ?? 0),
  });
  return request<Page<Recipe>>(`/recipes?${params.toString()}`);
}

export function createRecipe(recipe: RecipeInput): Promise<Recipe> {
  return request<Recipe>("/recipes", {
    method: "POST",
    body: JSON.stringify(recipe),
  });
}

export function updateRecipe(recipeId: string, recipe: RecipeInput): Promise<Recipe> {
  return request<Recipe>(`/recipes/${encodeURIComponent(recipeId)}`, {
    method: "PUT",
    body: JSON.stringify(recipe),
  });
}

export function deleteRecipe(recipeId: string): Promise<void> {
  return request<void>(`/recipes/${encodeURIComponent(recipeId)}`, { method: "DELETE" });
}

// --- Bilanciamento ----------------------------------------------------------

export function calculateBalance(recipe: RecipeInput): Promise<BalanceResponse> {
  return request<BalanceResponse>("/balance", {
    method: "POST",
    body: JSON.stringify(recipe),
  });
}

export function optimizeRecipe(payload: {
  recipe: RecipeInput;
  target: TargetProfileInput;
  settings?: SolverSettingsInput;
}): Promise<SolverResult> {
  return request<SolverResult>("/optimize", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- Matcher ----------------------------------------------------------------

export function findSubstitutes(
  ingredientId: string,
  limit = 4,
): Promise<Substitution[]> {
  return request<Substitution[]>(
    `/match/substitutes/${encodeURIComponent(ingredientId)}?limit=${limit}`,
  );
}

export function suggestPairings(
  ingredientIds: string[],
  limit = 4,
): Promise<PairingSuggestion[]> {
  return request<PairingSuggestion[]>("/match/pairings", {
    method: "POST",
    body: JSON.stringify({ ingredient_ids: ingredientIds, limit }),
  });
}
