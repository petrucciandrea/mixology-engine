"use client";

import { DrinkGlass, type GlassBand } from "@/components/studio/DrinkGlass";
import { Card, CardMeta, CardTitle } from "@/components/ui/card";
import { useGlassShape } from "@/hooks/useGlassShape";
import type { Dose } from "@/hooks/useRecipe";
import { useTweenedVolumes } from "@/hooks/useTweenedVolumes";
import { CATEGORY_COLORS } from "@/lib/categoryColors";
import { cn, formatMl } from "@/lib/utils";
import {
  GLASS_LABELS,
  SERVING_ICE_LABELS,
  type BalanceProfile,
  type GlassFit,
  type GlassType,
  type RecipeFamily,
  type ServingIce,
  type ServingProfile,
} from "@/types/api";

/** L'acqua di fusione ha un colore proprio e desaturato: è l'unica banda
    che nessuno versa, e deve leggersi come diversa dalle altre. Quella che
    fonde nel bicchiere dopo il servizio è un tono più chiaro della stessa. */
const DILUTION = { key: "__dilution", label: "Acqua di fusione", color: "#2f4048" };
const MELT = { key: "__melt", label: "Fusione nel bicchiere", color: "#3d5560" };

/** Le famiglie con anidride carbonica: le uniche in cui disegnare bollicine. */
const SPARKLING_FAMILIES: readonly RecipeFamily[] = ["SPRITZ", "SPARKLING"];

interface GlassStageProps {
  doses: Dose[];
  profile: BalanceProfile | null;
  glass: GlassType | null;
  glassFit: GlassFit | null;
  servingIce: ServingIce;
  family: RecipeFamily | null;
  /** Il drink al minuto scelto sulla curva; `null` = appena servito. */
  moment: ServingProfile | null;
}

export function GlassStage({
  doses,
  profile,
  glass,
  glassFit,
  servingIce,
  family,
  moment,
}: GlassStageProps) {
  const shape = useGlassShape(glass);

  const target: Record<string, number> = {};
  for (const dose of doses) target[dose.ingredient.id] = dose.volumeMl;
  target[DILUTION.key] = profile?.dilution_water_ml ?? 0;
  // La fusione resta in elenco anche a zero: tornando al minuto 0 la banda
  // si ritira invece di sparire di colpo.
  target[MELT.key] = moment?.melt_water_ml ?? 0;
  const shown = useTweenedVolumes(target);

  const bands: GlassBand[] = [
    ...doses.map((dose) => ({
      key: dose.ingredient.id,
      label: dose.ingredient.name,
      volumeMl: shown[dose.ingredient.id] ?? dose.volumeMl,
      color: CATEGORY_COLORS[dose.ingredient.category],
    })),
    { ...DILUTION, volumeMl: shown[DILUTION.key] ?? 0, isWater: true },
    { ...MELT, volumeMl: shown[MELT.key] ?? 0, isWater: true },
  ];
  const legend = bands.filter((band) => band.volumeMl > 0.05);

  const glassLabel = glass === null ? "Nessun bicchiere" : GLASS_LABELS[glass];
  const servedMl = moment?.final_volume_ml ?? profile?.final_volume_ml ?? 0;

  return (
    <Card className="flex flex-col gap-3.5 border-line-soft bg-recess px-5 pb-4 pt-[18px]">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <CardTitle>Nel bicchiere</CardTitle>
        <CardMeta>
          {glassLabel}
          {glassFit !== null && ` · ${formatMl(glassFit.capacity_ml)} ml a filo`} ·{" "}
          {SERVING_ICE_LABELS[servingIce]}
        </CardMeta>
      </div>

      <div className="flex justify-center py-1.5">
        <DrinkGlass
          shape={shape}
          bands={bands}
          capacityMl={glassFit?.capacity_ml ?? null}
          maxVolumeMl={glassFit?.max_volume_ml ?? null}
          iceVolumeMl={glassFit?.ice_volume_ml ?? 0}
          iceType={servingIce}
          iceRemaining={moment === null ? 1 : moment.remaining_ice_g / moment.ice_mass_g}
          overflows={glassFit?.overflows ?? false}
          bubbles={family !== null && SPARKLING_FAMILIES.includes(family)}
          width={400}
          ariaLabel={`Composizione del drink${glass !== null ? ` in ${GLASS_LABELS[glass]}` : ""}, ${formatMl(servedMl)} ml totali`}
        />
      </div>

      {doses.length === 0 ? (
        <p className="text-center text-[13px] text-muted">
          Il bicchiere è vuoto: aggiungi un ingrediente dalla Dispensa.
        </p>
      ) : (
        <ul className="flex flex-wrap justify-center gap-1.5">
          {legend.map((band) => (
            <li
              key={band.key}
              className={cn(
                "flex items-center gap-[7px] rounded-full border border-line px-2.5 py-1 text-[13px]",
                band.isWater ? "italic text-muted" : "text-foreground",
              )}
            >
              <span
                className="h-[9px] w-[9px] rounded-full"
                style={{ backgroundColor: band.color }}
                aria-hidden
              />
              {band.label}
              <span className="tabular font-mono text-[12.5px] not-italic text-soft">
                {formatMl(band.volumeMl)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <dl className="grid grid-cols-2 gap-y-3 border-t border-line-soft pt-3 sm:grid-cols-4">
        <Measure label="Brix" value={profile?.brix_post.toFixed(1)} unit="°Bx" />
        <Measure label="Acidità" value={profile?.acidity_post.toFixed(2)} unit="% w/v" />
        <Measure
          label="Alcol puro"
          value={profile === null ? undefined : formatMl(profile.pure_alcohol_ml)}
          unit="ml"
        />
        <Measure
          label="Diluizione"
          value={profile === null ? undefined : (profile.dilution_factor * 100).toFixed(0)}
          unit="%"
        />
      </dl>
    </Card>
  );
}

function Measure({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | undefined;
  unit: string;
}) {
  return (
    <div>
      <dt className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted">
        {label}
      </dt>
      <dd className="tabular mt-1 font-mono text-base">
        {value ?? "—"}
        {value !== undefined && <span className="text-xs text-muted"> {unit}</span>}
      </dd>
    </div>
  );
}
