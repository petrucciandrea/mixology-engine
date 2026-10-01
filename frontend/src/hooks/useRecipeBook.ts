"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, createRecipe, deleteRecipe, listRecipes, updateRecipe } from "@/lib/api";
import type { Recipe, RecipeInput } from "@/types/api";

export interface UseRecipeBookResult {
  recipes: Recipe[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  /** Crea la ricetta se `recipeId` è `null`, altrimenti la aggiorna.
      Restituisce la ricetta salvata, o `null` se il backend l'ha rifiutata
      (il motivo finisce in `error`). */
  save: (input: RecipeInput, recipeId: string | null) => Promise<Recipe | null>;
  /** Restituisce `true` se la ricetta è stata cancellata. */
  remove: (recipeId: string) => Promise<boolean>;
}

/** Stesso ordine dell'elenco del backend (`ORDER BY name`): una ricetta
    appena salvata compare dove comparirà al prossimo caricamento, invece
    di saltare in fondo e poi spostarsi. */
function byName(left: Recipe, right: Recipe): number {
  return left.name.localeCompare(right.name, "it");
}

function describe(cause: unknown, fallback: string): string {
  return cause instanceof ApiError ? cause.message : fallback;
}

/**
 * Le ricette salvate sul backend.
 *
 * È separato da `useRecipe` di proposito: quello governa la bozza sul banco,
 * questo l'archivio. Una bozza esiste anche senza archivio, e l'archivio
 * non sa quale ricetta si sta modificando.
 */
export function useRecipeBook(): UseRecipeBookResult {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRecipes()
      .then((page) => setRecipes([...page.items].sort(byName)))
      .catch((cause: unknown) => setError(describe(cause, "Impossibile caricare il ricettario")))
      .finally(() => setIsLoading(false));
  }, []);

  const save = useCallback(
    async (input: RecipeInput, recipeId: string | null): Promise<Recipe | null> => {
      setIsSaving(true);
      try {
        const saved =
          recipeId === null ? await createRecipe(input) : await updateRecipe(recipeId, input);
        setRecipes((current) =>
          [...current.filter((recipe) => recipe.id !== saved.id), saved].sort(byName),
        );
        setError(null);
        return saved;
      } catch (cause: unknown) {
        setError(describe(cause, "Salvataggio non riuscito"));
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [],
  );

  const remove = useCallback(async (recipeId: string): Promise<boolean> => {
    try {
      await deleteRecipe(recipeId);
      setRecipes((current) => current.filter((recipe) => recipe.id !== recipeId));
      setError(null);
      return true;
    } catch (cause: unknown) {
      setError(describe(cause, "Cancellazione non riuscita"));
      return false;
    }
  }, []);

  return { recipes, isLoading, isSaving, error, save, remove };
}
