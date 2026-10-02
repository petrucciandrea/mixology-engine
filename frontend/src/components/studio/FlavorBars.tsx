"use client";

import { useMemo } from "react";

import { Card, CardHeader, CardMeta, CardTitle } from "@/components/ui/card";
import type { Dose } from "@/hooks/useRecipe";
import { useTweenedVolumes } from "@/hooks/useTweenedVolumes";
import { blendFlavor, dominantFlavors } from "@/lib/flavor";

interface FlavorBarsProps {
  doses: Dose[];
  /** Il dosaggio prima dell'ultima ottimizzazione applicata, se c'è: le
      sue intensità restano segnate come tacche, per vedere cosa il solver
      ha spostato nel sapore oltre che nei numeri. */
  before: Dose[] | null;
}

/**
 * Il profilo aromatico come barre su una scala fissa 0–1.
 *
 * Un radar a otto punte si legge come forma; le barre si leggono come
 * misure, ed è quello che serve accanto a un dosaggio. La scala non si
 * adatta ai dati: se lo facesse, due drink di intensità molto diversa
 * disegnerebbero le stesse barre e il confronto perderebbe senso.
 */
export function FlavorBars({ doses, before }: FlavorBarsProps) {
  const target: Record<string, number> = {};
  for (const dose of doses) target[dose.ingredient.id] = dose.volumeMl;
  const shown = useTweenedVolumes(target);

  const readings = dominantFlavors(
    blendFlavor(
      doses.map((dose) => ({
        ingredient: dose.ingredient,
        volumeMl: shown[dose.ingredient.id] ?? dose.volumeMl,
      })),
    ),
  );
  const ghost = useMemo(() => (before === null ? null : blendFlavor(before)), [before]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profilo aromatico</CardTitle>
        <CardMeta className="text-xs">0 – 1</CardMeta>
      </CardHeader>

      {readings.length === 0 ? (
        <p className="px-4 py-6 text-center text-[13px] text-muted">
          {doses.length === 0
            ? "Il profilo aromatico compare con il primo ingrediente."
            : "Nessuno degli ingredienti scelti ha un profilo organolettico."}
        </p>
      ) : (
        <ul className="flex flex-col gap-[9px] px-4 py-3.5">
          {readings.map((reading) => {
            const previous = ghost?.get(reading.descriptor) ?? null;
            return (
              <li
                key={reading.descriptor}
                className="grid grid-cols-[96px_minmax(0,1fr)_40px] items-center gap-2.5"
              >
                <span className="text-sm">{reading.label}</span>
                <span className="relative h-2.5 rounded-[3px] bg-surface-2">
                  <span
                    className="absolute inset-y-0 left-0 rounded-[3px] bg-accent opacity-90"
                    style={{ width: `${Math.min(100, reading.intensity * 100)}%` }}
                  />
                  {ghost !== null && (
                    <span
                      className="absolute -inset-y-[3px] w-0.5 bg-foreground opacity-60"
                      style={{ left: `${Math.min(100, (previous ?? 0) * 100)}%` }}
                      title={`Prima del solver: ${(previous ?? 0).toFixed(2)}`}
                    />
                  )}
                </span>
                <span className="tabular text-right font-mono text-[13px] text-accent-light">
                  {reading.intensity.toFixed(2)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <p className="px-4 pb-3.5 text-xs leading-normal text-muted">
        Media pesata sulla quota di volume: un&apos;aggregazione di sola
        visualizzazione. Dopo il solver, la tacca chiara segna il valore
        precedente.
      </p>
    </Card>
  );
}
