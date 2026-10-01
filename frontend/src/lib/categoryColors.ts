import type { IngredientCategory } from "@/types/api";

/** Colore di ogni famiglia: lo usano il bicchiere e i puntini nelle liste. */
export const CATEGORY_COLORS: Record<IngredientCategory, string> = {
  SPIRIT: "#d9a441",
  LIQUEUR: "#e2b062",
  FORTIFIED_WINE: "#a8573f",
  WINE: "#8f3b52",
  BITTER: "#c23b3b",
  AMARO: "#7a3b2e",
  JUICE: "#b8c44a",
  SYRUP: "#e8d08a",
  ACID_SOLUTION: "#cfe3a8",
  MIXER: "#6f8f9a",
  WATER: "#5d7f8c",
  OTHER: "#6b7570",
};
