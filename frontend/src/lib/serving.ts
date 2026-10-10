import { SERVING_ICES, type GlassSpec, type GlassType, type ServingIce } from "@/types/api";

/** Il catalogo dei bicchieri, indicizzato per tipo. */
export type GlassCatalogue = ReadonlyMap<GlassType, GlassSpec>;

export function toCatalogue(specs: readonly GlassSpec[]): GlassCatalogue {
  return new Map(specs.map((spec) => [spec.glass, spec]));
}

/**
 * I ghiacci che il bicchiere accoglie. La geometria resta al backend: qui
 * si legge solo il suo verdetto. Senza bicchiere, o finché il catalogo non
 * è arrivato (o non arriva), non si esclude nulla: l'ultima parola resta
 * comunque al dominio, che rifiuta la coppia.
 */
export function allowedIce(
  catalogue: GlassCatalogue | null,
  glass: GlassType | null,
): readonly ServingIce[] {
  if (glass === null || catalogue === null) return SERVING_ICES;
  return catalogue.get(glass)?.compatible_ice ?? SERVING_ICES;
}

/**
 * Il ghiaccio da mettere al posto di uno che il nuovo bicchiere non
 * accoglie: cubetti se entrano, così un drink servito "on the rocks" resta
 * tale, altrimenti senza ghiaccio, che entra ovunque. È lo stesso ripiego
 * della migrazione che ha riallineato le ricette salvate.
 */
export function fallbackIce(allowed: readonly ServingIce[]): ServingIce {
  return allowed.includes("CUBES") ? "CUBES" : "NONE";
}
