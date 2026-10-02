"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Dose } from "@/hooks/useRecipe";
import { ApiError, optimizeRecipe } from "@/lib/api";
import {
  USABLE_SOLVER_STATUSES,
  type RecipeInput,
  type SolverResult,
  type TargetProfileInput,
} from "@/types/api";

/**
 * - `idle`: nessun esito a schermo.
 * - `running`: richiesta in corso.
 * - `review`: l'esito è già applicato al dosaggio, si può tenerlo o tornare
 *   indietro.
 * - `settled`: l'esito resta a schermo ma non c'è più niente da decidere —
 *   tenuto, superato da una modifica a mano, o inutilizzabile.
 */
export type SolverPhase = "idle" | "running" | "review" | "settled";

/** I target come si digitano: stringhe, perché un campo vuoto significa
    "non vincolare" e non zero. */
export interface TargetFields {
  abv: string;
  sugarAcidRatio: string;
  finalVolumeMl: string;
}

const EMPTY_TARGETS: TargetFields = { abv: "", sugarAcidRatio: "", finalVolumeMl: "" };

/** Quanto resta acceso il bagliore sulle letture dopo un'ottimizzazione. */
const FLASH_MS = 700;

interface UseSolverOptions {
  recipeInput: RecipeInput | null;
  doses: Dose[];
  /** Scrive i volumi nel dosaggio. Non deve passare dalla notifica di
      modifica manuale, o l'esito appena applicato si chiuderebbe da solo. */
  onApply: (volumes: Record<string, number>) => void;
}

export interface UseSolverResult {
  targets: TargetFields;
  setTarget: (field: keyof TargetFields, value: string) => void;
  hasTarget: boolean;
  canRun: boolean;
  phase: SolverPhase;
  result: SolverResult | null;
  error: string | null;
  /** Le dosi prima dell'esito applicato: servono a ripristinarle e a
      segnare sul profilo aromatico da dove si è partiti. `null` se l'esito
      a schermo non è stato applicato. */
  before: Dose[] | null;
  /** Vero per un attimo dopo che un esito è stato applicato. */
  flash: boolean;
  run: () => void;
  keep: () => void;
  revert: () => void;
  /** Il dosaggio è cambiato a mano: un'ottimizzazione in corso riguarda
      una ricetta che non c'è più, e un esito in revisione non si può più
      ripristinare senza perdere quella modifica. */
  invalidate: () => void;
  /** Ricetta nuova o caricata: l'esito precedente non la riguarda. */
  clear: () => void;
}

function volumesOf(doses: { ingredient: { id: string }; volume_ml: number }[]) {
  return Object.fromEntries(doses.map((dose) => [dose.ingredient.id, dose.volume_ml]));
}

export function useSolver({ recipeInput, doses, onApply }: UseSolverOptions): UseSolverResult {
  const [targets, setTargets] = useState<TargetFields>(EMPTY_TARGETS);
  const [phase, setPhase] = useState<SolverPhase>("idle");
  const [result, setResult] = useState<SolverResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [before, setBefore] = useState<Dose[] | null>(null);
  const [flash, setFlash] = useState(false);

  /** Come in `useRecipe`: una risposta vale solo se nessuno, nel frattempo,
      ha cambiato la ricetta o avviato un'altra ottimizzazione. */
  const latestRun = useRef(0);

  useEffect(() => {
    if (!flash) return;
    const timer = setTimeout(() => setFlash(false), FLASH_MS);
    return () => clearTimeout(timer);
  }, [flash]);

  const hasTarget = Object.values(targets).some((value) => value.trim() !== "");
  const canRun = recipeInput !== null && hasTarget && phase !== "running";

  const setTarget = useCallback((field: keyof TargetFields, value: string) => {
    setTargets((current) => ({ ...current, [field]: value }));
  }, []);

  const run = useCallback(() => {
    if (!canRun || recipeInput === null) return;

    const target: TargetProfileInput = {};
    // L'ABV si digita in punti percentuali perché è così che si parla di
    // un drink; il contratto lo vuole in frazione.
    if (targets.abv.trim() !== "") target.abv = Number(targets.abv) / 100;
    if (targets.sugarAcidRatio.trim() !== "")
      target.sugar_acid_ratio = Number(targets.sugarAcidRatio);
    if (targets.finalVolumeMl.trim() !== "")
      target.final_volume_ml = Number(targets.finalVolumeMl);

    const runId = ++latestRun.current;
    const snapshot = doses;
    setPhase("running");
    setError(null);
    setResult(null);

    optimizeRecipe({ recipe: recipeInput, target })
      .then((outcome) => {
        if (runId !== latestRun.current) return;
        setResult(outcome);
        if (USABLE_SOLVER_STATUSES.includes(outcome.status)) {
          // L'esito si applica subito, con la via del ritorno aperta: è più
          // rapido giudicare un drink nel bicchiere che una tabella di
          // volumi proposti.
          setBefore(snapshot);
          onApply(volumesOf(outcome.recipe.ingredients));
          setFlash(true);
          setPhase("review");
        } else {
          setBefore(null);
          setPhase("settled");
        }
      })
      .catch((cause: unknown) => {
        if (runId !== latestRun.current) return;
        setError(cause instanceof ApiError ? cause.message : "Ottimizzazione non riuscita");
        setPhase("idle");
      });
  }, [canRun, recipeInput, targets, doses, onApply]);

  const keep = useCallback(() => {
    setPhase((current) => (current === "review" ? "settled" : current));
  }, []);

  const revert = useCallback(() => {
    if (phase !== "review" || before === null) return;
    onApply(
      Object.fromEntries(before.map((dose) => [dose.ingredient.id, dose.volumeMl])),
    );
    setBefore(null);
    setResult(null);
    setPhase("idle");
  }, [phase, before, onApply]);

  const invalidate = useCallback(() => {
    latestRun.current++;
    setPhase((current) =>
      current === "running" ? "idle" : current === "review" ? "settled" : current,
    );
  }, []);

  const clear = useCallback(() => {
    latestRun.current++;
    setPhase("idle");
    setResult(null);
    setBefore(null);
    setError(null);
  }, []);

  return {
    targets,
    setTarget,
    hasTarget,
    canRun,
    phase,
    result,
    error,
    before,
    flash,
    run,
    keep,
    revert,
    invalidate,
    clear,
  };
}
