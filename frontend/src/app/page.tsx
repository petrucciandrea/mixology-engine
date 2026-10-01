"use client";

import { useEffect, useMemo, useState } from "react";

import { BalanceReadout } from "@/components/studio/BalanceReadout";
import { DrinkCanvas } from "@/components/studio/DrinkCanvas";
import { FlavorRadar } from "@/components/studio/FlavorRadar";
import { IngredientPicker } from "@/components/studio/IngredientPicker";
import { MatcherPanel } from "@/components/studio/MatcherPanel";
import { RecipeBook } from "@/components/studio/RecipeBook";
import { RecipeBuilder } from "@/components/studio/RecipeBuilder";
import { SolverPanel } from "@/components/studio/SolverPanel";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useRecipe } from "@/hooks/useRecipe";
import { useRecipeBook } from "@/hooks/useRecipeBook";
import { ApiError, listIngredients } from "@/lib/api";
import type { Ingredient, Recipe } from "@/types/api";

export default function StudioPage() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [pantryError, setPantryError] = useState<string | null>(null);
  const [isLoadingPantry, setIsLoadingPantry] = useState(true);

  const recipe = useRecipe("Ricetta senza nome");
  const book = useRecipeBook();

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

  // Il nome vuoto lo rifiuterebbe comunque il dominio: disabilitare il
  // pulsante evita un giro al backend solo per sentirselo dire.
  const canSave = recipe.recipeInput !== null && recipe.name.trim() !== "" && !book.isSaving;

  async function saveRecipe(asNew: boolean) {
    if (recipe.recipeInput === null) return;
    const saved = await book.save(recipe.recipeInput, asNew ? null : recipe.recipeId);
    if (saved !== null) recipe.markSaved(saved);
  }

  async function deleteRecipe(target: Recipe) {
    // La cancellazione non si annulla: una conferma costa un clic, una
    // ricetta persa costa il lavoro di bilanciarla di nuovo.
    if (!window.confirm(`Cancellare «${target.name}» dal ricettario?`)) return;
    const deleted = await book.remove(target.id);
    if (deleted && target.id === recipe.recipeId) recipe.forgetRecipeId();
  }

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

        <div className="flex flex-wrap items-end gap-2">
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
          <Button variant="primary" disabled={!canSave} onClick={() => void saveRecipe(false)}>
            {recipe.recipeId === null ? "Salva" : "Aggiorna"}
          </Button>
          {recipe.recipeId !== null && (
            <Button disabled={!canSave} onClick={() => void saveRecipe(true)}>
              Salva come nuova
            </Button>
          )}
          <Button variant="ghost" onClick={recipe.reset}>
            Nuova
          </Button>
        </div>
      </header>

      {pantryError !== null && (
        <p className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert">
          {pantryError}. Verifica che lo stack sia avviato (<code>make up</code>) e
          che la dispensa sia popolata (<code>make seed</code>).
        </p>
      )}

      {book.error !== null && (
        <p className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert">
          {book.error}
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
          <RecipeBook
            recipes={book.recipes}
            activeId={recipe.recipeId}
            isLoading={book.isLoading}
            onLoad={recipe.loadRecipe}
            onDelete={(target) => void deleteRecipe(target)}
          />
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
            servingIce={recipe.servingIce}
            glass={recipe.glass}
            totalVolumeMl={totalVolumeMl}
            onMethodChange={recipe.setMethod}
            onServingIceChange={recipe.setServingIce}
            onGlassChange={recipe.setGlass}
            onVolumeChange={recipe.setVolume}
            onRemove={recipe.removeIngredient}
          />

          <Card>
            <CardHeader>
              <CardTitle>Nel bicchiere</CardTitle>
            </CardHeader>
            <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-[auto_1fr]">
              <div className="w-full sm:w-[220px]">
                <DrinkCanvas
                  doses={recipe.doses}
                  profile={recipe.profile}
                  glass={recipe.glass}
                  glassFit={recipe.glassFit}
                />
              </div>
              <BalanceReadout
                profile={recipe.profile}
                servingProfile={recipe.servingProfile}
                glassFit={recipe.glassFit}
                isCalculating={recipe.isCalculating}
              />
            </CardBody>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          <SolverPanel
            doses={recipe.doses}
            method={recipe.method}
            servingIce={recipe.servingIce}
            glass={recipe.glass}
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
