"use client";

import { useEffect, useMemo, useState } from "react";

import { BalanceReadout } from "@/components/studio/BalanceReadout";
import { DrinkCanvas } from "@/components/studio/DrinkCanvas";
import { FlavorRadar } from "@/components/studio/FlavorRadar";
import { IngredientPicker } from "@/components/studio/IngredientPicker";
import { MatcherPanel } from "@/components/studio/MatcherPanel";
import { RecipeBuilder } from "@/components/studio/RecipeBuilder";
import { SolverPanel } from "@/components/studio/SolverPanel";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useRecipe } from "@/hooks/useRecipe";
import { ApiError, listIngredients } from "@/lib/api";
import type { Ingredient } from "@/types/api";

export default function StudioPage() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [pantryError, setPantryError] = useState<string | null>(null);
  const [isLoadingPantry, setIsLoadingPantry] = useState(true);

  const recipe = useRecipe("Ricetta senza nome");

  useEffect(() => {
    listIngredients({ limit: 200 })
      .then((page) => setIngredients(page.items))
      .catch((cause: unknown) => {
        setPantryError(
          cause instanceof ApiError
            ? cause.message
            : "Impossibile caricare la dispensa",
        );
      })
      .finally(() => setIsLoadingPantry(false));
  }, []);

  const selectedIds = useMemo(
    () => new Set(recipe.doses.map((dose) => dose.ingredient.id)),
    [recipe.doses],
  );

  const totalVolumeMl = recipe.doses.reduce((sum, dose) => sum + dose.volumeMl, 0);

  return (
    <div className="mx-auto flex min-h-screen max-w-[1500px] flex-col gap-6 px-4 py-6 lg:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-accent">
            Mixology Engine
          </span>
          <h1 className="font-display text-2xl leading-tight sm:text-3xl">
            Studio di bilanciamento
          </h1>
        </div>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.12em] text-muted">
            Nome della ricetta
          </span>
          <input
            value={recipe.name}
            onChange={(event) => recipe.setName(event.target.value)}
            className="h-9 w-56 rounded-md border border-line bg-surface-2 px-3 text-sm focus:border-accent focus:outline-none"
          />
        </label>
      </header>

      {pantryError !== null && (
        <p className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert">
          {pantryError}. Verifica che lo stack sia avviato (<code>make up</code>) e
          che la dispensa sia popolata (<code>make seed</code>).
        </p>
      )}

      {recipe.error !== null && (
        <p className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert">
          {recipe.error}
        </p>
      )}

      {/* Tre colonne: si compone a sinistra, si legge il risultato al
          centro, si chiede aiuto alla macchina a destra. È l'ordine in cui
          si lavora davvero, e sotto i 1024px diventa una colonna sola. */}
      <main className="grid flex-1 grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(260px,0.9fr)_minmax(320px,1.1fr)_minmax(280px,1fr)]">
        <div className="flex max-h-[calc(100vh-11rem)] flex-col gap-5 lg:sticky lg:top-6">
          <IngredientPicker
            ingredients={ingredients}
            selectedIds={selectedIds}
            onAdd={recipe.addIngredient}
            isLoading={isLoadingPantry}
          />
        </div>

        <div className="flex flex-col gap-5">
          <RecipeBuilder
            doses={recipe.doses}
            method={recipe.method}
            totalVolumeMl={totalVolumeMl}
            onMethodChange={recipe.setMethod}
            onVolumeChange={recipe.setVolume}
            onRemove={recipe.removeIngredient}
          />

          <Card>
            <CardHeader>
              <CardTitle>Nel bicchiere</CardTitle>
            </CardHeader>
            <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-[auto_1fr]">
              <div className="w-full sm:w-[220px]">
                <DrinkCanvas doses={recipe.doses} profile={recipe.profile} />
              </div>
              <BalanceReadout
                profile={recipe.profile}
                isCalculating={recipe.isCalculating}
              />
            </CardBody>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          <SolverPanel
            doses={recipe.doses}
            method={recipe.method}
            recipeName={recipe.name}
            onApply={recipe.applyVolumes}
          />

          <Card>
            <CardHeader>
              <CardTitle>Profilo aromatico</CardTitle>
            </CardHeader>
            <CardBody>
              <FlavorRadar doses={recipe.doses} />
            </CardBody>
          </Card>

          <MatcherPanel doses={recipe.doses} onAdd={recipe.addIngredient} />
        </div>
      </main>
    </div>
  );
}
