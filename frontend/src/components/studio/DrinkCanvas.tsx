"use client";

import type { Dose } from "@/hooks/useRecipe";
import { formatMl } from "@/lib/utils";
import type { BalanceProfile, IngredientCategory } from "@/types/api";

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

const GLASS_HEIGHT = 190;
const GLASS_TOP_WIDTH = 150;
const GLASS_BOTTOM_WIDTH = 96;
const VIEWBOX_WIDTH = 190;
const VIEWBOX_HEIGHT = 238;

interface DrinkCanvasProps {
  doses: Dose[];
  profile: BalanceProfile | null;
}

interface Band {
  key: string;
  label: string;
  volumeMl: number;
  color: string;
}

export function DrinkCanvas({ doses, profile }: DrinkCanvasProps) {
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

  // Le bande si impilano dal fondo: si disegnano in ordine inverso, come si
  // versa. `offset` accumula l'altezza già occupata.
  let offset = 0;
  const geometry = bands.map((band) => {
    const height = (band.volumeMl / totalMl) * GLASS_HEIGHT;
    const y = VIEWBOX_HEIGHT - 24 - offset - height;
    offset += height;
    return { band, y, height };
  });

  const centre = VIEWBOX_WIDTH / 2;
  const base = VIEWBOX_HEIGHT - 24;

  /** Il bicchiere è rastremato: la larghezza a una certa altezza si
      interpola fra fondo e bocca, così le bande seguono davvero il profilo
      del vetro invece di essere rettangoli sovrapposti a un disegno. */
  const widthAt = (y: number): number => {
    const progress = (base - y) / GLASS_HEIGHT;
    return GLASS_BOTTOM_WIDTH + (GLASS_TOP_WIDTH - GLASS_BOTTOM_WIDTH) * progress;
  };

  const glassPath = [
    `M ${centre - GLASS_BOTTOM_WIDTH / 2} ${base}`,
    `L ${centre - GLASS_TOP_WIDTH / 2} ${base - GLASS_HEIGHT}`,
    `L ${centre + GLASS_TOP_WIDTH / 2} ${base - GLASS_HEIGHT}`,
    `L ${centre + GLASS_BOTTOM_WIDTH / 2} ${base}`,
    "Z",
  ].join(" ");

  return (
    <div className="flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        className="mx-auto h-auto w-full max-w-[220px]"
        role="img"
        aria-label={`Composizione del drink, ${formatMl(totalMl)} ml totali`}
      >
        <defs>
          <clipPath id="glass-clip">
            <path d={glassPath} />
          </clipPath>
        </defs>

        <g clipPath="url(#glass-clip)">
          {geometry.map(({ band, y, height }) => {
            const topWidth = widthAt(y);
            const bottomWidth = widthAt(y + height);
            return (
              <path
                key={band.key}
                d={[
                  `M ${centre - bottomWidth / 2} ${y + height}`,
                  `L ${centre - topWidth / 2} ${y}`,
                  `L ${centre + topWidth / 2} ${y}`,
                  `L ${centre + bottomWidth / 2} ${y + height}`,
                  "Z",
                ].join(" ")}
                fill={band.color}
                fillOpacity={band.key === "__dilution" ? 0.65 : 0.9}
              />
            );
          })}
        </g>

        <path d={glassPath} fill="none" stroke="#3a4742" strokeWidth={1.5} />
        {/* Stelo e base: bastano a far leggere la forma come un bicchiere
            invece che come un grafico a barre ruotato. */}
        <line
          x1={centre}
          y1={base}
          x2={centre}
          y2={base + 14}
          stroke="#3a4742"
          strokeWidth={1.5}
        />
        <line
          x1={centre - 28}
          y1={base + 16}
          x2={centre + 28}
          y2={base + 16}
          stroke="#3a4742"
          strokeWidth={1.5}
          strokeLinecap="round"
        />
      </svg>

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
