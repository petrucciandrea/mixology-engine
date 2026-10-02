import type { Ingredient } from "@/types/api";

/**
 * Il profilo organolettico di una miscela.
 *
 * L'aggregazione è fatta qui e non sul backend perché è una scelta di
 * *rappresentazione*, non di dominio: il modello non definisce cosa sia il
 * "sapore di una miscela", e inventarlo nel dominio significherebbe dargli
 * un'autorità che non ha. La regola usata è la più semplice difendibile —
 * media delle intensità pesata sulla quota di volume di ciascun
 * ingrediente — ed è dichiarata accanto al grafico, così chi guarda sa
 * cosa sta leggendo.
 *
 * Un limite noto: 30 ml di un liquore intensamente aromatico pesano quanto
 * 30 ml di acqua, mentre in bocca non è così. Una pesatura per intensità
 * percepita richiederebbe dati che non abbiamo.
 */

/** Etichette italiane dei 32 descrittori (`docs/FLAVOR_TAXONOMY.md`). */
export const FLAVOR_LABELS: Record<string, string> = {
  sweet: "dolce",
  sour: "acido",
  bitter: "amaro",
  salty: "sapido",
  umami: "umami",
  alcohol_heat: "calore",
  astringency: "astringente",
  cooling: "fresco",
  pungency: "pungente",
  citrus: "agrumato",
  orchard_fruit: "pomacee",
  stone_fruit: "drupacee",
  berry: "bacche",
  tropical_fruit: "tropicale",
  dried_fruit: "frutta secca",
  floral: "floreale",
  herbaceous: "erbaceo",
  mint: "menta",
  anise: "anice",
  resinous: "resinoso",
  pepper: "pepe",
  warm_spice: "spezie dolci",
  earthy: "terroso",
  woody: "legno",
  vanilla: "vaniglia",
  caramel: "caramello",
  smoke: "affumicato",
  roasted: "tostato",
  nutty: "nocciolato",
  honey: "miele",
  funky: "fermentato",
  medicinal: "medicinale",
};

export function flavorLabel(descriptor: string): string {
  return FLAVOR_LABELS[descriptor] ?? descriptor;
}

/** Quanti descrittori mostrare. Trentadue barre non si leggono: si tengono
    i più presenti, che sono poi quelli che definiscono il drink. */
const MAX_DESCRIPTORS = 8;

/** Sotto questa intensità un descrittore è rumore di compilazione, non un
    carattere del drink. */
const PRESENCE_FLOOR = 0.02;

export interface FlavorReading {
  descriptor: string;
  label: string;
  intensity: number;
}

/** Media delle intensità pesata sulla quota di volume, descrittore per
    descrittore. Gli ingredienti senza profilo contano nel volume ma non
    aggiungono aromi: diluiscono, come in bocca. */
export function blendFlavor(
  doses: readonly { ingredient: Ingredient; volumeMl: number }[],
): Map<string, number> {
  const blended = new Map<string, number>();
  const totalVolume = doses.reduce((sum, dose) => sum + dose.volumeMl, 0);
  if (totalVolume <= 0) return blended;

  for (const dose of doses) {
    const profile = dose.ingredient.flavor_profile;
    if (profile === null) continue;
    const share = dose.volumeMl / totalVolume;
    for (const [descriptor, intensity] of Object.entries(profile)) {
      blended.set(descriptor, (blended.get(descriptor) ?? 0) + intensity * share);
    }
  }
  return blended;
}

/** I descrittori che caratterizzano la miscela, dal più intenso. */
export function dominantFlavors(blend: Map<string, number>): FlavorReading[] {
  return [...blend.entries()]
    .filter(([, intensity]) => intensity >= PRESENCE_FLOOR)
    .sort((left, right) => right[1] - left[1])
    .slice(0, MAX_DESCRIPTORS)
    .map(([descriptor, intensity]) => ({
      descriptor,
      label: flavorLabel(descriptor),
      intensity,
    }));
}
