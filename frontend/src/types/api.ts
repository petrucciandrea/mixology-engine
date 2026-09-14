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
  is_balanced_sour: boolean;
}

export interface BalanceResponse {
  recipe: Recipe;
  profile: BalanceProfile;
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
