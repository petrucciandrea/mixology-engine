"use client";

import type { Dose } from "@/hooks/useRecipe";
import { GENERIC_SHAPE, levelForFraction, shapeFor, sliceOutline } from "@/lib/glassShapes";
import { formatMl } from "@/lib/utils";
import {
  GLASS_LABELS,
  type BalanceProfile,
  type GlassFit,
  type GlassType,
  type IngredientCategory,
} from "@/types/api";

/**
 * Il drink come volume, non come elenco.
 *
 * Il colore di ogni banda viene dalla famiglia merceologica, non da una
 * tavolozza arbitraria: un distillato è ambrato, un succo di agrume è
 * verde-giallo, un bitter è rosso. Chi conosce il bar riconosce la ricetta
 * dalla proporzione dei colori prima di leggere i nomi.
 */
const CATEGORY_COLORS: Record<IngredientCategory, string> = {
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

/** L'acqua di fusione ha un colore proprio e desaturato: è l'unica banda
    che nessuno versa, e deve leggersi come diversa dalle altre. */
const DILUTION_COLOR = "#2f4048";

const VIEWBOX_WIDTH = 190;
const VIEWBOX_HEIGHT = 238;
/** Dove poggia il piede (o il fondo, se non c'è stelo). */
const BASELINE_Y = 226;
const OUTLINE = "#3a4742";

interface DrinkCanvasProps {
  doses: Dose[];
  profile: BalanceProfile | null;
  glass: GlassType | null;
  glassFit: GlassFit | null;
}

interface Band {
  key: string;
  label: string;
  volumeMl: number;
  color: string;
}

export function DrinkCanvas({ doses, profile, glass, glassFit }: DrinkCanvasProps) {
  const bands: Band[] = doses.map((dose) => ({
    key: dose.ingredient.id,
    label: dose.ingredient.name,
    volumeMl: dose.volumeMl,
    color: CATEGORY_COLORS[dose.ingredient.category],
  }));

  const dilutionMl = profile?.dilution_water_ml ?? 0;
  if (dilutionMl > 0) {
    bands.push({
      key: "__dilution",
      label: "Acqua di fusione",
      volumeMl: dilutionMl,
      color: DILUTION_COLOR,
    });
  }

  const totalMl = bands.reduce((sum, band) => sum + band.volumeMl, 0);

  if (totalMl === 0) {
    return (
      <div className="flex h-full min-h-[240px] items-center justify-center text-sm text-muted">
        Il bicchiere è vuoto.
      </div>
    );
  }

  // Con un bicchiere dalla capienza nota il disegno è in scala: il liquido
  // sale fin dove il suo volume arriva, dentro la sagoma vera del vetro.
  // Senza (nessun bicchiere, o "altro") si ripiega sul bicchiere generico
  // riempito per intero, dove le bande mostrano solo le proporzioni.
  const sized = glass !== null && glassFit !== null;
  const shape = sized ? shapeFor(glass) : GENERIC_SHAPE;
  const capacityMl = sized ? glassFit.capacity_ml : totalMl;
  const overflows = sized && totalMl > capacityMl;
  // Se trabocca, il liquido si ferma al bordo e le bande si riscalano: il
  // disegno non può mostrare più vetro di quello che c'è.
  const volumeScale = overflows ? capacityMl / totalMl : 1;

  const centre = VIEWBOX_WIDTH / 2;
  const bowlBottom = BASELINE_Y - shape.stemPx;

  // Le bande si impilano dal fondo: `poured` accumula il volume già sotto.
  let poured = 0;
  const geometry = bands.map((band) => {
    const from = levelForFraction(shape, (poured * volumeScale) / capacityMl);
    poured += band.volumeMl;
    const to = levelForFraction(shape, (poured * volumeScale) / capacityMl);
    return { band, path: sliceOutline(shape, from, to, centre, bowlBottom) };
  });

  const glassPath = sliceOutline(shape, 0, 1, centre, bowlBottom);
  const maxLevel = sized ? levelForFraction(shape, glassFit.max_volume_ml / capacityMl) : null;
  const maxY = maxLevel === null ? 0 : bowlBottom - maxLevel * shape.heightPx;
  const maxHalf = maxLevel === null ? 0 : (shape.width(maxLevel) * shape.widthPx) / 2;
  const stroke = overflows ? "#f87171" : OUTLINE;

  return (
    <div className="flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        className="mx-auto h-auto w-full max-w-[220px]"
        role="img"
        aria-label={`Composizione del drink${glass !== null ? ` in ${GLASS_LABELS[glass]}` : ""}, ${formatMl(totalMl)} ml totali`}
      >
        <defs>
          <clipPath id="glass-clip">
            <path d={glassPath} />
          </clipPath>
        </defs>

        <g clipPath="url(#glass-clip)">
          {geometry.map(({ band, path }) => (
            <path
              key={band.key}
              d={path}
              fill={band.color}
              fillOpacity={band.key === "__dilution" ? 0.65 : 0.9}
            />
          ))}
        </g>

        <path d={glassPath} fill="none" stroke={stroke} strokeWidth={1.5} />

        {shape.stemPx > 0 && (
          <>
            <line
              x1={centre}
              y1={bowlBottom}
              x2={centre}
              y2={BASELINE_Y}
              stroke={OUTLINE}
              strokeWidth={1.5}
            />
            <line
              x1={centre - shape.footPx / 2}
              y1={BASELINE_Y}
              x2={centre + shape.footPx / 2}
              y2={BASELINE_Y}
              stroke={OUTLINE}
              strokeWidth={1.5}
              strokeLinecap="round"
            />
          </>
        )}

        {/* Il massimo che il bicchiere ammette (bordo libero e ghiaccio
            inclusi): il tetto che il solver rispetta, non il bordo. */}
        {sized && (
          <line
            x1={centre - maxHalf}
            y1={maxY}
            x2={centre + maxHalf}
            y2={maxY}
            stroke="#34d399"
            strokeWidth={1}
            strokeDasharray="3 3"
          >
            <title>Volume massimo ammesso: {formatMl(glassFit.max_volume_ml)} ml</title>
          </line>
        )}
      </svg>

      {sized && glass !== null && (
        <p className="tabular text-center font-mono text-[0.68rem] text-muted">
          {GLASS_LABELS[glass]} · {formatMl(glassFit.capacity_ml)} ml a filo
          {overflows && <span className="ml-1 text-alert">· trabocca</span>}
        </p>
      )}

      <ul className="flex flex-col gap-1">
        {bands.map((band) => (
          <li
            key={band.key}
            className="flex items-baseline justify-between gap-2 text-xs"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-sm"
                style={{ backgroundColor: band.color }}
                aria-hidden
              />
              <span
                className={
                  band.key === "__dilution"
                    ? "truncate italic text-muted"
                    : "truncate text-foreground"
                }
              >
                {band.label}
              </span>
            </span>
            <span className="tabular shrink-0 font-mono text-muted">
              {formatMl(band.volumeMl)} ml
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
