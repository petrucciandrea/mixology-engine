"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import type { Dose } from "@/hooks/useRecipe";
import { ApiError, optimizeRecipe } from "@/lib/api";
import { formatMl, formatPercent } from "@/lib/utils";
import {
  SOLVER_STATUS_LABELS,
  USABLE_SOLVER_STATUSES,
  type DilutionMethod,
  type GlassType,
  type ServingIce,
  type SolverResult,
  type TargetProfileInput,
} from "@/types/api";

/** Nomi dei target come li restituisce il backend, tradotti per la lettura. */
const RESIDUAL_LABELS: Record<string, string> = {
  abv: "ABV",
  brix: "Brix",
  acidity: "Acidità",
  sugar_acid_ratio: "Zuccheri/acidi",
  final_volume_ml: "Volume finale",
};

interface TargetFields {
  abv: string;
  sugarAcidRatio: string;
  finalVolumeMl: string;
}

const EMPTY_TARGETS: TargetFields = { abv: "", sugarAcidRatio: "", finalVolumeMl: "" };

interface SolverPanelProps {
  doses: Dose[];
  method: DilutionMethod;
  servingIce: ServingIce;
  glass: GlassType | null;
  recipeName: string;
  onApply: (volumes: Record<string, number>) => void;
}

export function SolverPanel({
  doses,
  method,
  servingIce,
  glass,
  recipeName,
  onApply,
}: SolverPanelProps) {
  const [targets, setTargets] = useState<TargetFields>(EMPTY_TARGETS);
  const [result, setResult] = useState<SolverResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const hasTarget = Object.values(targets).some((value) => value.trim() !== "");
  const canRun = doses.length > 0 && hasTarget && !isRunning;

  async function run() {
    setIsRunning(true);
    setError(null);
    try {
      const target: TargetProfileInput = {};
      // L'ABV si digita in punti percentuali perché è così che si parla di
      // un drink; il contratto lo vuole in frazione.
      if (targets.abv.trim() !== "") target.abv = Number(targets.abv) / 100;
      if (targets.sugarAcidRatio.trim() !== "")
        target.sugar_acid_ratio = Number(targets.sugarAcidRatio);
      if (targets.finalVolumeMl.trim() !== "")
        target.final_volume_ml = Number(targets.finalVolumeMl);

      const outcome = await optimizeRecipe({
        recipe: {
          name: recipeName,
          dilution_method: method,
          serving_ice: servingIce,
          glass,
          ingredients: doses.map((dose) => ({
            ingredient_id: dose.ingredient.id,
            volume_ml: dose.volumeMl,
          })),
        },
        target,
      });
      setResult(outcome);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Ottimizzazione non riuscita");
      setResult(null);
    } finally {
      setIsRunning(false);
    }
  }

  function apply() {
    if (result === null) return;
    const volumes: Record<string, number> = {};
    for (const item of result.recipe.ingredients) {
      volumes[item.ingredient.id] = item.volume_ml;
    }
    onApply(volumes);
  }

  const isUsable = result !== null && USABLE_SOLVER_STATUSES.includes(result.status);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Solver</CardTitle>
        <span className="font-mono text-[0.62rem] text-muted">SLSQP</span>
      </CardHeader>

      <CardBody className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-2">
          <TargetField
            label="ABV"
            unit="%"
            placeholder="16"
            value={targets.abv}
            onChange={(abv) => setTargets((current) => ({ ...current, abv }))}
          />
          <TargetField
            label="Zucch./acidi"
            unit="ratio"
            placeholder="6.2"
            value={targets.sugarAcidRatio}
            onChange={(sugarAcidRatio) =>
              setTargets((current) => ({ ...current, sugarAcidRatio }))
            }
          />
          <TargetField
            label="Volume"
            unit="ml"
            placeholder="150"
            value={targets.finalVolumeMl}
            onChange={(finalVolumeMl) =>
              setTargets((current) => ({ ...current, finalVolumeMl }))
            }
          />
        </div>

        <p className="text-[0.68rem] leading-relaxed text-muted">
          I target si riferiscono al drink <strong>dopo</strong> la diluizione. Il
          volume è trattato come vincolo rigido, gli altri come obiettivi da
          avvicinare.
        </p>

        <Button variant="primary" onClick={run} disabled={!canRun}>
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          {isRunning ? "Ottimizzo…" : "Bilancia"}
        </Button>

        {error !== null && (
          <p className="rounded-md border border-alert/30 bg-alert-soft px-3 py-2 text-xs text-alert">
            {error}
          </p>
        )}

        {result !== null && (
          <div className="flex flex-col gap-3 border-t border-line-soft pt-3">
            <div className="flex items-center justify-between gap-2">
              <Badge tone={result.status === "CONVERGED" ? "good" : "alert"}>
                {SOLVER_STATUS_LABELS[result.status]}
              </Badge>
              <span className="tabular font-mono text-[0.68rem] text-muted">
                {result.iterations} iterazioni
                {result.max_relative_error !== null &&
                  ` · scarto max ${formatPercent(result.max_relative_error)}`}
              </span>
            </div>

            {!isUsable && (
              <p className="text-xs leading-relaxed text-muted">
                {result.status === "INFEASIBLE"
                  ? "Nessuna combinazione di volumi soddisfa il vincolo entro i limiti dei singoli ingredienti. Prova ad allentare il volume richiesto o ad aggiungere un ingrediente."
                  : result.message}
              </p>
            )}

            <ul className="flex flex-col gap-1">
              {result.residuals.map((residual) => (
                <li
                  key={residual.name}
                  className="flex items-baseline justify-between gap-2 text-xs"
                >
                  <span className="text-muted">
                    {RESIDUAL_LABELS[residual.name] ?? residual.name}
                  </span>
                  <span className="tabular font-mono">
                    {residual.achieved === null
                      ? "—"
                      : formatResidual(residual.name, residual.achieved)}
                    <span className="text-muted">
                      {" / "}
                      {formatResidual(residual.name, residual.target)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>

            {isUsable && (
              <>
                <ul className="flex flex-col gap-0.5 rounded-md bg-surface-2 px-3 py-2">
                  {result.recipe.ingredients.map((item) => (
                    <li
                      key={item.ingredient.id}
                      className="flex items-baseline justify-between gap-2 text-xs"
                    >
                      <span className="truncate">{item.ingredient.name}</span>
                      <span className="tabular font-mono text-accent">
                        {formatMl(item.volume_ml)} ml
                      </span>
                    </li>
                  ))}
                </ul>
                <Button variant="secondary" size="sm" onClick={apply}>
                  Applica alla ricetta
                </Button>
              </>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

/** L'ABV torna dal backend in frazione: va riportato in punti percentuali
    per essere confrontabile con quello digitato. */
function formatResidual(name: string, value: number): string {
  if (name === "abv") return `${(value * 100).toFixed(1)}%`;
  if (name === "final_volume_ml") return `${formatMl(value)} ml`;
  return value.toFixed(2);
}

function TargetField({
  label,
  unit,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  unit: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.1em] text-muted">
        {label}
      </span>
      <span className="relative block">
        <input
          type="number"
          inputMode="decimal"
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          className="tabular h-9 w-full rounded-md border border-line bg-surface-2 px-2 pr-8 font-mono text-sm placeholder:text-muted/60 focus:border-accent focus:outline-none"
        />
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 font-mono text-[0.6rem] text-muted">
          {unit}
        </span>
      </span>
    </label>
  );
}
