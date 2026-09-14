"use client";

import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import type { Dose } from "@/hooks/useRecipe";
import { formatMl } from "@/lib/utils";
import {
  CATEGORY_LABELS,
  DILUTION_METHODS,
  DILUTION_METHOD_LABELS,
  type DilutionMethod,
} from "@/types/api";

/** Estremi dello slider, in ml. Coprono dalla goccia di bitter al long
    drink senza costringere a cambiare scala a metà composizione. */
const MIN_VOLUME_ML = 2.5;
const MAX_VOLUME_ML = 120;

/** Passo del dosatore graduato: è la risoluzione con cui si versa davvero,
    ed è lo stesso arrotondamento che applica il solver. */
const STEP_ML = 2.5;

interface RecipeBuilderProps {
  doses: Dose[];
  method: DilutionMethod;
  totalVolumeMl: number;
  onMethodChange: (method: DilutionMethod) => void;
  onVolumeChange: (ingredientId: string, volumeMl: number) => void;
  onRemove: (ingredientId: string) => void;
}

export function RecipeBuilder({
  doses,
  method,
  totalVolumeMl,
  onMethodChange,
  onVolumeChange,
  onRemove,
}: RecipeBuilderProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Dosaggio</CardTitle>
        {doses.length > 0 && (
          <span className="tabular font-mono text-xs text-muted">
            {formatMl(totalVolumeMl)} ml pre-diluizione
          </span>
        )}
      </CardHeader>

      <CardBody className="flex flex-col gap-5">
        <fieldset className="flex flex-col gap-2">
          <legend className="sr-only">Tecnica di preparazione</legend>
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted">
            Tecnica
          </span>
          <div className="flex flex-wrap gap-1.5">
            {DILUTION_METHODS.map((candidate) => (
              <Button
                key={candidate}
                size="sm"
                variant={candidate === method ? "primary" : "secondary"}
                onClick={() => onMethodChange(candidate)}
                aria-pressed={candidate === method}
              >
                {DILUTION_METHOD_LABELS[candidate]}
              </Button>
            ))}
          </div>
          <p className="text-xs leading-relaxed text-muted">
            {method === "BUILT"
              ? "Costruito nel bicchiere: il profilo mostrato è quello del drink appena versato, senza diluizione da preparazione."
              : "La curva di diluizione di Dave Arnold determina quanta acqua di fusione entra nel drink."}
          </p>
        </fieldset>

        {doses.length === 0 ? (
          <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            Scegli un ingrediente dalla dispensa per iniziare.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {doses.map((dose) => {
              const share = totalVolumeMl > 0 ? dose.volumeMl / totalVolumeMl : 0;
              return (
                <li key={dose.ingredient.id} className="flex flex-col gap-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="flex min-w-0 items-baseline gap-2">
                      <span className="truncate text-sm font-medium">
                        {dose.ingredient.name}
                      </span>
                      <Badge>{CATEGORY_LABELS[dose.ingredient.category]}</Badge>
                    </div>
                    <div className="flex shrink-0 items-baseline gap-2">
                      <span className="tabular font-mono text-sm text-accent">
                        {formatMl(dose.volumeMl)} ml
                      </span>
                      <span className="tabular font-mono text-[0.65rem] text-muted">
                        {(share * 100).toFixed(0)}%
                      </span>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => onRemove(dose.ingredient.id)}
                        aria-label={`Togli ${dose.ingredient.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </Button>
                    </div>
                  </div>

                  <Slider
                    value={[dose.volumeMl]}
                    min={MIN_VOLUME_ML}
                    max={MAX_VOLUME_ML}
                    step={STEP_ML}
                    aria-label={`Volume di ${dose.ingredient.name} in millilitri`}
                    onValueChange={([next]) => {
                      if (next !== undefined) onVolumeChange(dose.ingredient.id, next);
                    }}
                  />
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
