import {
  SERVING_ICES,
  type GlassModel,
  type GlassType,
  type Glassware,
  type GlasswareCatalogue,
  type ServingIce,
} from "@/types/api";

/** Un catalogo con i suoi bicchieri indicizzati per tipo. */
export interface IndexedCatalogue {
  catalogue: GlasswareCatalogue;
  models: ReadonlyMap<GlassType, GlassModel>;
}

/** I cataloghi di `/glassware`, indicizzati per consultarli senza cercare. */
export type GlasswareIndex = ReadonlyMap<Glassware, IndexedCatalogue>;

export function toIndex(catalogues: readonly GlasswareCatalogue[]): GlasswareIndex {
  return new Map(
    catalogues.map((catalogue) => [
      catalogue.glassware,
      {
        catalogue,
        models: new Map(catalogue.glasses.map((model) => [model.glass, model])),
      },
    ]),
  );
}

/** Il bicchiere `glass` nel catalogo scelto; `null` senza bicchiere, per
    `OTHER` (senza misure), se la linea non lo produce o se i cataloghi
    non sono ancora arrivati. */
export function modelFor(
  index: GlasswareIndex | null,
  glassware: Glassware,
  glass: GlassType | null,
): GlassModel | null {
  if (index === null || glass === null) return null;
  return index.get(glassware)?.models.get(glass) ?? null;
}

/** Il tipo di bicchiere si può scegliere in questo catalogo? `OTHER` sì,
    sempre: è "fuori elenco", non un bicchiere mancante. Finché i cataloghi
    non arrivano non si esclude nulla: l'ultima parola resta al backend. */
export function isGlassAvailable(
  index: GlasswareIndex | null,
  glassware: Glassware,
  glass: GlassType,
): boolean {
  if (index === null || glass === "OTHER") return true;
  return index.get(glassware)?.models.has(glass) ?? true;
}

/**
 * I ghiacci che il bicchiere accoglie. La geometria resta al backend: qui
 * si legge solo il suo verdetto. Senza un bicchiere misurato non si
 * esclude nulla, come fa il dominio.
 */
export function allowedIce(
  index: GlasswareIndex | null,
  glassware: Glassware,
  glass: GlassType | null,
): readonly ServingIce[] {
  return modelFor(index, glassware, glass)?.compatible_ice ?? SERVING_ICES;
}

/**
 * Il ghiaccio da mettere al posto di uno che il nuovo bicchiere non
 * accoglie: cubetti se entrano, così un drink servito "on the rocks" resta
 * tale, altrimenti senza ghiaccio, che entra ovunque. È lo stesso ripiego
 * delle migrazioni che hanno riallineato le ricette salvate.
 */
export function fallbackIce(allowed: readonly ServingIce[]): ServingIce {
  return allowed.includes("CUBES") ? "CUBES" : "NONE";
}
