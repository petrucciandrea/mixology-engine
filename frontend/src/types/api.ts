/**
 * Tipi del contratto HTTP con il backend.
 *
 * Sono scritti a mano e non generati da OpenAPI: il generatore produrrebbe
 * tipi fedeli ma anonimi, mentre qui i nomi e i commenti trasportano il
 * significato di dominio — quali grandezze sono frazioni e quali
 * percentuali, quali sono pre e quali post diluizione. È la distinzione che
 * in questo dominio si sbaglia più spesso.
 *
 * Restano allineati al backend dal type check: ogni campo usato
 * dall'interfaccia è dichiarato qui, e un cambio di contratto si manifesta
 * come errore di compilazione invece che come `undefined` a schermo.
 */

export type DilutionMethod = "SHAKEN" | "STIRRED" | "BUILT";

export const DILUTION_METHODS: readonly DilutionMethod[] = [
  "SHAKEN",
  "STIRRED",
  "BUILT",
] as const;

/** Etichette da bar, non identificatori tecnici. */
export const DILUTION_METHOD_LABELS: Record<DilutionMethod, string> = {
  SHAKEN: "Shakerato",
  STIRRED: "Mescolato",
  BUILT: "Costruito",
};

/**
 * Ghiaccio nel bicchiere di servizio. Indipendente dalla tecnica: un
 * Daiquiri è shakerato e servito senza ghiaccio, un Whiskey Sour è
 * shakerato e servito su cubetti. `NONE` è "servito senza ghiaccio".
 */
export type ServingIce = "NONE" | "CUBES" | "LARGE_CUBE" | "CRUSHED";

export const SERVING_ICES: readonly ServingIce[] = [
  "NONE",
  "CUBES",
  "LARGE_CUBE",
  "CRUSHED",
] as const;

export const SERVING_ICE_LABELS: Record<ServingIce, string> = {
  NONE: "Senza ghiaccio",
  CUBES: "Cubetti",
  LARGE_CUBE: "Ghiaccio grosso",
  CRUSHED: "Tritato",
};

/**
 * Bicchiere di servizio. Facoltativo: una ricetta può non dichiararlo, e
 * in quel caso non c'è un tetto al volume. `OTHER` non ha capienza nota.
 */
export type GlassType =
  | "COUPE"
  | "MARTINI"
  | "NICK_AND_NORA"
  | "ROCKS"
  | "DOUBLE_ROCKS"
  | "HIGHBALL"
  | "COLLINS"
  | "FLUTE"
  | "WINE"
  | "BALLOON"
  | "COPPER_MUG"
  | "TIKI"
  | "HURRICANE"
  | "SHOT"
  | "OTHER";

export const GLASS_TYPES: readonly GlassType[] = [
  "COUPE",
  "MARTINI",
  "NICK_AND_NORA",
  "ROCKS",
  "DOUBLE_ROCKS",
  "HIGHBALL",
  "COLLINS",
  "FLUTE",
  "WINE",
  "BALLOON",
  "COPPER_MUG",
  "TIKI",
  "HURRICANE",
  "SHOT",
  "OTHER",
] as const;

export const GLASS_LABELS: Record<GlassType, string> = {
  COUPE: "Coppa",
  MARTINI: "Coppa martini",
  NICK_AND_NORA: "Nick & Nora",
  ROCKS: "Tumbler basso",
  DOUBLE_ROCKS: "Doppio tumbler",
  HIGHBALL: "Highball",
  COLLINS: "Collins",
  FLUTE: "Flûte",
  WINE: "Calice",
  BALLOON: "Balloon",
  COPPER_MUG: "Tazza di rame",
  TIKI: "Tiki mug",
  HURRICANE: "Hurricane",
  SHOT: "Bicchierino",
  OTHER: "Altro",
};

/**
 * Famiglia del drink, per struttura (non per tecnica né per bicchiere).
 * Facoltativa: un Kir non ricade in nessuna, e `null` è meglio di
 * un'etichetta forzata.
 */
export type RecipeFamily =
  | "SOUR"
  | "SPIRIT_FORWARD"
  | "HIGHBALL"
  | "TROPICAL"
  | "SPRITZ"
  | "SPARKLING"
  | "EMULSIFIED";

export const RECIPE_FAMILIES: readonly RecipeFamily[] = [
  "SOUR",
  "SPIRIT_FORWARD",
  "HIGHBALL",
  "TROPICAL",
  "SPRITZ",
  "SPARKLING",
  "EMULSIFIED",
] as const;

// I nomi delle famiglie sono termini di bar e restano in inglese.
export const RECIPE_FAMILY_LABELS: Record<RecipeFamily, string> = {
  SOUR: "Sour",
  SPIRIT_FORWARD: "Spirit-Forward",
  HIGHBALL: "Highball",
  TROPICAL: "Tropical",
  SPRITZ: "Spritz",
  SPARKLING: "Sparkling",
  EMULSIFIED: "Emulsified",
};

export type IngredientCategory =
  | "SPIRIT"
  | "LIQUEUR"
  | "FORTIFIED_WINE"
  | "WINE"
  | "BITTER"
  | "AMARO"
  | "JUICE"
  | "SYRUP"
  | "ACID_SOLUTION"
  | "MIXER"
  | "WATER"
  | "OTHER";

export const CATEGORY_LABELS: Record<IngredientCategory, string> = {
  SPIRIT: "Distillato",
  LIQUEUR: "Liquore",
  FORTIFIED_WINE: "Vino fortificato",
  WINE: "Vino",
  BITTER: "Bitter",
  AMARO: "Amaro",
  JUICE: "Succo",
  SYRUP: "Sciroppo",
  ACID_SOLUTION: "Soluzione acida",
  MIXER: "Mixer",
  WATER: "Acqua",
  OTHER: "Altro",
};

export interface PhysicalProfile {
  density_g_ml: number;
  brix: number;
  /** Acido equivalente in % peso/volume. */
  acidity: number;
  /** Frazione, non percentuale: 0.40 significa 40% vol. */
  abv: number;
}

export interface Ingredient {
  id: string;
  name: string;
  category: IngredientCategory;
  physical_profile: PhysicalProfile;
  /** Mappa descrittore → intensità in [0, 1]. Assente se non profilato. */
  flavor_profile: Record<string, number> | null;
  dominant_flavors: string[];
  is_active: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface RecipeIngredientInput {
  ingredient_id: string;
  volume_ml: number;
}

export interface RecipeInput {
  name: string;
  dilution_method: DilutionMethod;
  serving_ice: ServingIce;
  glass?: GlassType | null;
  family?: RecipeFamily | null;
  ingredients: RecipeIngredientInput[];
  instructions?: string | null;
}

export interface RecipeIngredient {
  ingredient: Ingredient;
  volume_ml: number;
}

export interface Recipe {
  id: string;
  name: string;
  dilution_method: DilutionMethod;
  serving_ice: ServingIce;
  glass: GlassType | null;
  family: RecipeFamily | null;
  ingredients: RecipeIngredient[];
  instructions: string | null;
}

/**
 * Profilo calcolato. Le grandezze `_pre` descrivono la miscela prima del
 * ghiaccio, le `_post` il drink servito — ed è su queste ultime che si
 * esprime un giudizio.
 */
export interface BalanceProfile {
  total_volume_ml: number;
  pure_alcohol_ml: number;
  total_mass_g: number;
  sugar_mass_g: number;
  acid_mass_g: number;

  abv_pre: number;
  brix_pre: number;
  acidity_pre: number;
  sugar_acid_ratio: number | null;

  dilution_factor: number;
  dilution_water_ml: number;
  final_volume_ml: number;
  final_mass_g: number;

  abv_post: number;
  brix_post: number;
  acidity_post: number;

  abv_post_percent: number;
  /** Giudizio sul rapporto zuccheri/acidi: solo per i sour con acidità
      percepibile, `null` per ogni altro drink (la finestra non lo descrive). */
  sour_balance: SourBalance | null;
  /** Estremi della finestra dei sour, dal dominio: servono a disegnare la
      barra, non a giudicare. */
  sour_ratio_lower_bound: number;
  sour_ratio_upper_bound: number;
}

export type SourBalance = "TOO_TART" | "BALANCED" | "TOO_SWEET";

/**
 * Il drink dopo la diluizione dovuta al ghiaccio nel bicchiere, a
 * `consumption_minutes` dal servizio. Distinto da `BalanceProfile`, che
 * descrive il drink appena servito.
 */
export interface ServingProfile {
  consumption_minutes: number;
  initial_temperature_c: number;
  equilibrium_temperature_c: number;
  /** Temperatura del drink a `consumption_minutes`. */
  temperature_c: number;
  cooling_melt_water_ml: number;
  ambient_melt_water_ml: number;
  melt_water_ml: number;
  /** Ghiaccio messo nel bicchiere, e quanto ne resta a `consumption_minutes`. */
  ice_mass_g: number;
  remaining_ice_g: number;
  final_volume_ml: number;
  final_mass_g: number;
  total_dilution_factor: number;
  abv: number;
  abv_percent: number;
  brix: number;
  acidity: number;
}

/** Quanto il drink riempie il bicchiere; `fill_ratio` oltre 1 = trabocca. */
export interface GlassFit {
  capacity_ml: number;
  max_volume_ml: number;
  /** Spazio occupato dal ghiaccio di servizio; 0 senza ghiaccio. Con
      `max_volume_ml` fa il volume utile del bicchiere. */
  ice_volume_ml: number;
  volume_ml: number;
  fill_ratio: number;
  overflows: boolean;
}

export interface BalanceResponse {
  recipe: Recipe;
  profile: BalanceProfile;
  /** `null` per le ricette servite senza ghiaccio. */
  serving_profile: ServingProfile | null;
  /** Lo stesso profilo campionato al minuto, da `t = 0` (il drink appena
      servito) a 30 minuti. `null` per le ricette servite senza ghiaccio. */
  serving_curve: ServingProfile[] | null;
  /** `null` senza bicchiere, o con un bicchiere senza capienza nota. */
  glass_fit: GlassFit | null;
}

export interface TargetProfileInput {
  abv?: number | null;
  brix?: number | null;
  acidity?: number | null;
  sugar_acid_ratio?: number | null;
  final_volume_ml?: number | null;
}

export interface VolumeBoundsInput {
  min_ml: number;
  max_ml: number;
}

export interface SolverSettingsInput {
  default_bounds?: VolumeBoundsInput;
  bounds_by_ingredient?: Record<string, VolumeBoundsInput>;
  rounding_step_ml?: number;
  restarts?: number;
}

export type SolverStatus = "CONVERGED" | "MAX_ITERATIONS" | "INFEASIBLE" | "FAILED";

/** Solo i primi due stati producono una ricetta utilizzabile. */
export const USABLE_SOLVER_STATUSES: readonly SolverStatus[] = [
  "CONVERGED",
  "MAX_ITERATIONS",
] as const;

export const SOLVER_STATUS_LABELS: Record<SolverStatus, string> = {
  CONVERGED: "Ottimo trovato",
  MAX_ITERATIONS: "Iterazioni esaurite",
  INFEASIBLE: "Vincoli irrealizzabili",
  FAILED: "Fallimento numerico",
};

export interface TargetResidual {
  name: string;
  target: number;
  achieved: number | null;
  absolute_error: number | null;
  relative_error: number | null;
}

export interface SolverResult {
  status: SolverStatus;
  recipe: Recipe;
  profile: BalanceProfile;
  objective_value: number;
  iterations: number;
  residuals: TargetResidual[];
  max_relative_error: number | null;
  message: string;
}

export interface Substitution {
  ingredient: Ingredient;
  flavor_similarity: number;
  physical_compatibility: number;
  overall: number;
  warnings: string[];
}

export interface PairingSuggestion {
  ingredient: Ingredient;
  affinity: number;
  rationale: string;
}

export interface FlavorDescriptors {
  dimension: number;
  descriptors: string[];
  families: Record<string, string[]>;
}

/** Corpo di errore uniforme del backend. */
export interface ApiErrorBody {
  error: { type: string; message: string };
}
