import type { GlassType } from "@/types/api";

/**
 * Sagome dei bicchieri come solidi di rotazione.
 *
 * Ogni bicchiere è un profilo `width(t)`, la larghezza relativa (0–1) a
 * un'altezza relativa `t` (0 = fondo della coppa, 1 = bordo). Poiché il
 * bicchiere è un solido di rotazione, la sezione a quota `t` è
 * proporzionale a `width(t)²`: il volume versato fino a `t` è l'integrale
 * di quella, **non** una frazione dell'altezza. Una coppa a metà altezza
 * contiene molto meno della metà del suo volume, ed è ciò che rende il
 * disegno onesto rispetto alle quantità.
 */
export interface GlassShape {
  /** Altezza della coppa (il solo vano del liquido), in unità del viewBox. */
  heightPx: number;
  /** Larghezza massima, in unità del viewBox. */
  widthPx: number;
  /** Lunghezza dello stelo; 0 = bicchiere senza stelo. */
  stemPx: number;
  /** Larghezza del piede, se c'è lo stelo. */
  footPx: number;
  width: (t: number) => number;
}

const lerp = (from: number, to: number, t: number): number => from + (to - from) * t;
/** Emisfero: parte da zero sul fondo e raggiunge la larghezza piena al bordo. */
const hemisphere = (t: number): number => Math.sqrt(Math.max(0, 1 - (1 - t) ** 2));

/** Coppa a uovo: fondo arrotondato (quarto di ellisse) fino alla massima
    larghezza a quota `widest`, poi restringimento a coseno fino alla
    larghezza `mouth` al bordo: parte tangente alla pancia e arriva al bordo
    con la parete inclinata, senza la "spalla" smussata di un'ellisse. È la forma di un calice o di un
    balloon, dove la bocca è più stretta della pancia. */
const tulip =
  (widest: number, mouth: number) =>
  (t: number): number => {
    if (t <= widest) return Math.sqrt(Math.max(0, 1 - ((widest - t) / widest) ** 2));
    return mouth + (1 - mouth) * Math.cos(((t - widest) / (1 - widest)) * (Math.PI / 2));
  };

export const GENERIC_SHAPE: GlassShape = {
  heightPx: 150,
  widthPx: 140,
  stemPx: 14,
  footPx: 56,
  width: (t) => lerp(0.64, 1, t),
};

const SHAPES: Record<GlassType, GlassShape> = {
  COUPE: { heightPx: 62, widthPx: 150, stemPx: 36, footPx: 56, width: hemisphere },
  MARTINI: { heightPx: 96, widthPx: 150, stemPx: 36, footPx: 56, width: (t) => t },
  NICK_AND_NORA: {
    heightPx: 78,
    widthPx: 112,
    stemPx: 34,
    footPx: 50,
    width: (t) => Math.sqrt(Math.max(0, 1 - (1 - t) ** 2.2)),
  },
  ROCKS: { heightPx: 80, widthPx: 112, stemPx: 0, footPx: 0, width: (t) => lerp(0.85, 1, t) },
  DOUBLE_ROCKS: {
    heightPx: 92,
    widthPx: 126,
    stemPx: 0,
    footPx: 0,
    width: (t) => lerp(0.85, 1, t),
  },
  HIGHBALL: { heightPx: 142, widthPx: 80, stemPx: 0, footPx: 0, width: (t) => lerp(0.88, 1, t) },
  COLLINS: { heightPx: 154, widthPx: 74, stemPx: 0, footPx: 0, width: (t) => lerp(0.92, 1, t) },
  FLUTE: {
    heightPx: 136,
    widthPx: 58,
    stemPx: 40,
    footPx: 44,
    width: (t) => lerp(0.3, 1, Math.sqrt(t)),
  },
  WINE: { heightPx: 98, widthPx: 100, stemPx: 40, footPx: 52, width: tulip(0.42, 0.68) },
  BALLOON: { heightPx: 104, widthPx: 140, stemPx: 26, footPx: 54, width: tulip(0.4, 0.5) },
  COPPER_MUG: { heightPx: 92, widthPx: 100, stemPx: 0, footPx: 0, width: (t) => lerp(0.9, 1, t) },
  TIKI: {
    heightPx: 104,
    widthPx: 104,
    stemPx: 0,
    footPx: 0,
    width: (t) => 0.78 + 0.22 * Math.sin(Math.PI * Math.min(1, t * 0.9 + 0.05)),
  },
  HURRICANE: {
    heightPx: 142,
    widthPx: 84,
    stemPx: 18,
    footPx: 46,
    width: (t) => 0.55 + 0.45 * Math.sin(Math.PI * (0.12 + 0.76 * t)),
  },
  SHOT: { heightPx: 60, widthPx: 54, stemPx: 0, footPx: 0, width: (t) => lerp(0.75, 1, t) },
  OTHER: GENERIC_SHAPE,
};

export function shapeFor(glass: GlassType | null): GlassShape {
  return glass === null ? GENERIC_SHAPE : SHAPES[glass];
}

/** Passi di campionamento del profilo: abbastanza fitti perché le curve
    non si vedano a spezzata, abbastanza pochi da restare economici. */
const SAMPLES = 64;

const cumulativeCache = new WeakMap<GlassShape, number[]>();

/** Volume cumulato fino a ciascun campione, normalizzato a 1 al bordo. */
function cumulativeVolume(shape: GlassShape): number[] {
  const cached = cumulativeCache.get(shape);
  if (cached !== undefined) return cached;

  const cumulative = [0];
  for (let i = 1; i <= SAMPLES; i++) {
    const before = shape.width((i - 1) / SAMPLES) ** 2;
    const after = shape.width(i / SAMPLES) ** 2;
    cumulative.push(cumulative[i - 1]! + (before + after) / 2);
  }
  const total = cumulative[SAMPLES]!;
  const normalised = cumulative.map((value) => value / total);
  cumulativeCache.set(shape, normalised);
  return normalised;
}

/** Altezza relativa `t` a cui il liquido raggiunge la frazione `fraction`
    del volume al bordo: l'inversa dell'integrale di `width²`. */
export function levelForFraction(shape: GlassShape, fraction: number): number {
  const cumulative = cumulativeVolume(shape);
  const target = Math.min(Math.max(fraction, 0), 1);
  for (let i = 1; i <= SAMPLES; i++) {
    const high = cumulative[i]!;
    if (high >= target) {
      const low = cumulative[i - 1]!;
      const within = high === low ? 0 : (target - low) / (high - low);
      return (i - 1 + within) / SAMPLES;
    }
  }
  return 1;
}

/** Il vano fra due altezze relative, come poligono: il profilo sinistro
    in salita, poi il destro in discesa. */
export function sliceOutline(
  shape: GlassShape,
  from: number,
  to: number,
  centreX: number,
  bottomY: number,
): string {
  const steps = Math.max(2, Math.ceil((to - from) * SAMPLES) + 1);
  const left: string[] = [];
  const right: string[] = [];
  for (let i = 0; i < steps; i++) {
    const t = from + ((to - from) * i) / (steps - 1);
    const half = (shape.width(t) * shape.widthPx) / 2;
    const y = bottomY - t * shape.heightPx;
    left.push(`${centreX - half} ${y}`);
    right.push(`${centreX + half} ${y}`);
  }
  return `M ${left.join(" L ")} L ${right.reverse().join(" L ")} Z`;
}
