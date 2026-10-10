"use client";

import { GlassIcon } from "@/components/studio/GlassIcon";
import { Card, CardBody, CardHeader, CardMeta, CardTitle } from "@/components/ui/card";
import { Segmented, type SegmentedOption } from "@/components/ui/segmented";
import { Slider } from "@/components/ui/slider";
import type { Dose } from "@/hooks/useRecipe";
import { CATEGORY_COLORS } from "@/lib/categoryColors";
import { formatMl } from "@/lib/utils";
import {
  CATEGORY_LABELS,
  DILUTION_METHODS,
  DILUTION_METHOD_LABELS,
  GLASS_LABELS,
  GLASS_TYPES,
  RECIPE_FAMILIES,
  RECIPE_FAMILY_LABELS,
  SERVING_ICES,
  SERVING_ICE_LABELS,
  type DilutionMethod,
  type GlassFit,
  type GlassModel,
  type GlassType,
  type RecipeFamily,
  type ServingIce,
} from "@/types/api";

/** Estremi dello slider, in ml. Coprono dalla goccia di bitter al long
    drink senza costringere a cambiare scala a metà composizione. I
    pulsanti ± non hanno tetto: un mixer da 150 ml si regola lo stesso. */
const MIN_VOLUME_ML = 2.5;
const MAX_SLIDER_ML = 120;

/** Passo del dosatore graduato: è la risoluzione con cui si versa davvero,
    ed è lo stesso arrotondamento che applica il solver. */
const STEP_ML = 2.5;

const METHOD_OPTIONS: SegmentedOption<DilutionMethod>[] = DILUTION_METHODS.map((method) => ({
  value: method,
  label: DILUTION_METHOD_LABELS[method],
}));

/** I ghiacci, con quelli che il bicchiere non accoglie disabilitati. "Senza
    ghiaccio" occupa da solo la prima riga: è la scelta opposta a tutte le
    altre, che sotto stanno a coppie. */
function iceOptions(allowed: readonly ServingIce[]): SegmentedOption<ServingIce>[] {
  return SERVING_ICES.map((ice) => {
    const fits = allowed.includes(ice);
    return {
      value: ice,
      label: SERVING_ICE_LABELS[ice],
      disabled: !fits,
      title: fits ? undefined : "Non entra in questo bicchiere",
      className: ice === "NONE" ? "col-span-2" : undefined,
    };
  });
}

/** La griglia dei bicchieri, compresa la scelta "nessuno": tutti visibili,
    perché la forma si riconosce prima del nome. Quelli che la linea scelta
    non produce restano al loro posto, disabilitati. */
function glassOptions(
  selected: GlassType | null,
  isAvailable: (glass: GlassType) => boolean,
  catalogueName: string,
): SegmentedOption<GlassType | null>[] {
  return [
    { value: null, label: <span aria-hidden>—</span>, ariaLabel: "Bicchiere: nessuno", title: "Nessuno" },
    ...GLASS_TYPES.map((glass) => {
      const available = isAvailable(glass);
      return {
        value: glass,
        label: <GlassIcon glass={glass} isActive={glass === selected} />,
        ariaLabel: `Bicchiere: ${GLASS_LABELS[glass]}`,
        title: available ? GLASS_LABELS[glass] : `${GLASS_LABELS[glass]}: non presente in ${catalogueName}`,
        disabled: !available,
      };
    }),
  ];
}

const SEGMENT_GROUP =
  "grid gap-0.5 rounded-lg border border-line bg-recess p-[3px]";
const SEGMENT = "h-8 rounded-md text-[13px] font-medium";

interface DosePanelProps {
  doses: Dose[];
  method: DilutionMethod;
  servingIce: ServingIce;
  /** Ghiacci che il bicchiere scelto accoglie; gli altri restano visibili
      ma disabilitati. */
  allowedIce: readonly ServingIce[];
  glass: GlassType | null;
  /** Il bicchiere nel catalogo scelto; `null` senza misure. */
  glassModel: GlassModel | null;
  /** Nome del catalogo, per spiegare i bicchieri disabilitati. */
  catalogueName: string;
  isGlassAvailable: (glass: GlassType) => boolean;
  family: RecipeFamily | null;
  glassFit: GlassFit | null;
  onMethodChange: (method: DilutionMethod) => void;
  onServingIceChange: (servingIce: ServingIce) => void;
  onGlassChange: (glass: GlassType | null) => void;
  onFamilyChange: (family: RecipeFamily | null) => void;
  onVolumeChange: (ingredientId: string, volumeMl: number) => void;
  onRemove: (ingredientId: string) => void;
  onOpenPantry: () => void;
}

export function DosePanel({
  doses,
  method,
  servingIce,
  allowedIce,
  glass,
  glassModel,
  catalogueName,
  isGlassAvailable,
  family,
  glassFit,
  onMethodChange,
  onServingIceChange,
  onGlassChange,
  onFamilyChange,
  onVolumeChange,
  onRemove,
  onOpenPantry,
}: DosePanelProps) {
  const totalMl = doses.reduce((sum, dose) => sum + dose.volumeMl, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dosaggio</CardTitle>
        <CardMeta>{formatMl(totalMl)} ml pre-diluizione</CardMeta>
      </CardHeader>

      <CardBody className="flex flex-col gap-3">
        <Segmented
          ariaLabel="Tecnica"
          options={METHOD_OPTIONS}
          value={method}
          onChange={onMethodChange}
          className={`${SEGMENT_GROUP} grid-cols-3`}
          optionClassName={SEGMENT}
        />
        <Segmented
          ariaLabel="Servizio"
          options={iceOptions(allowedIce)}
          value={servingIce}
          onChange={onServingIceChange}
          className={`${SEGMENT_GROUP} grid-cols-2`}
          optionClassName={`${SEGMENT} whitespace-nowrap px-1 text-[12.5px]`}
        />

        <label className="flex items-center justify-between gap-2.5">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted">
            Famiglia
          </span>
          <select
            value={family ?? ""}
            onChange={(event) =>
              onFamilyChange(
                event.target.value === "" ? null : (event.target.value as RecipeFamily),
              )
            }
            className="h-[34px] flex-1 rounded-[7px] border border-line bg-surface-2 px-2.5 text-sm focus:border-accent focus:outline-none"
          >
            <option value="">Nessuna</option>
            {RECIPE_FAMILIES.map((option) => (
              <option key={option} value={option}>
                {RECIPE_FAMILY_LABELS[option]}
              </option>
            ))}
          </select>
        </label>

        <div>
          <Segmented
            ariaLabel="Bicchiere"
            options={glassOptions(glass, isGlassAvailable, catalogueName)}
            value={glass}
            onChange={onGlassChange}
            className="grid grid-cols-8 gap-[3px]"
            optionClassName="flex h-[42px] items-center justify-center rounded-md font-mono text-sm text-muted"
          />
          <p className="mt-1.5 text-[12.5px] text-soft">
            {glass === null ? "Nessun bicchiere" : GLASS_LABELS[glass]}
            {glassModel !== null && <span className="text-muted"> · {glassModel.product}</span>}
            <span className="text-muted">
              {glassFit !== null
                ? ` · tetto ${formatMl(glassFit.max_volume_ml)} ml`
                : glass === null
                  ? " · nessun tetto al volume"
                  : " · capienza non nota"}
            </span>
          </p>
        </div>

        <div className="my-0.5 h-px bg-line-soft" />

        {doses.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            Nessun ingrediente.{" "}
            <button
              type="button"
              onClick={onOpenPantry}
              className="cursor-pointer text-accent-strong underline-offset-2 hover:underline"
            >
              Apri la dispensa
            </button>{" "}
            per iniziare.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {doses.map((dose) => (
              <DoseRow
                key={dose.ingredient.id}
                dose={dose}
                share={totalMl > 0 ? dose.volumeMl / totalMl : 0}
                onVolumeChange={onVolumeChange}
                onRemove={onRemove}
              />
            ))}
          </ul>
        )}

        <p className="text-[12.5px] leading-normal text-muted">
          {method === "BUILT"
            ? "Costruito nel bicchiere: il profilo mostrato è quello del drink appena versato, senza diluizione da preparazione."
            : "La curva di diluizione di Dave Arnold determina quanta acqua di fusione entra nel drink."}
        </p>
      </CardBody>
    </Card>
  );
}

function DoseRow({
  dose,
  share,
  onVolumeChange,
  onRemove,
}: {
  dose: Dose;
  share: number;
  onVolumeChange: (ingredientId: string, volumeMl: number) => void;
  onRemove: (ingredientId: string) => void;
}) {
  const { ingredient, volumeMl } = dose;
  const color = CATEGORY_COLORS[ingredient.category];
  const stepper =
    "h-[26px] w-[26px] cursor-pointer rounded-[5px] border border-line bg-surface-2 font-mono text-[15px] leading-none hover:bg-line";

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1.5">
      <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-[3px]"
          style={{ backgroundColor: color }}
          role="img"
          aria-label={CATEGORY_LABELS[ingredient.category]}
          title={CATEGORY_LABELS[ingredient.category]}
        />
        <span className="truncate">{ingredient.name}</span>
        <span className="tabular font-mono text-xs font-normal text-muted">
          {Math.round(share * 100)}%
        </span>
      </span>

      <span className="flex items-center gap-0.5">
        <button
          type="button"
          className={stepper}
          aria-label={`${ingredient.name}: −${STEP_ML} ml`}
          onClick={() => onVolumeChange(ingredient.id, Math.max(MIN_VOLUME_ML, volumeMl - STEP_ML))}
        >
          −
        </button>
        <span className="tabular w-16 text-center font-mono text-[14.5px] font-medium text-accent-strong">
          {formatMl(volumeMl)} ml
        </span>
        <button
          type="button"
          className={stepper}
          aria-label={`${ingredient.name}: +${STEP_ML} ml`}
          onClick={() => onVolumeChange(ingredient.id, volumeMl + STEP_ML)}
        >
          +
        </button>
        <button
          type="button"
          className="ml-1 h-[26px] w-[26px] cursor-pointer rounded-[5px] text-[17px] leading-none text-muted hover:text-alert"
          aria-label={`Togli ${ingredient.name}`}
          onClick={() => onRemove(ingredient.id)}
        >
          ×
        </button>
      </span>

      <Slider
        className="col-span-2"
        rangeColor={color}
        value={[volumeMl]}
        min={MIN_VOLUME_ML}
        max={MAX_SLIDER_ML}
        step={STEP_ML}
        aria-label={`Volume di ${ingredient.name} in millilitri`}
        onValueChange={([next]) => {
          if (next !== undefined) onVolumeChange(ingredient.id, next);
        }}
      />
    </li>
  );
}
