"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, calculateBalance } from "@/lib/api";
import type {
  BalanceProfile,
  DilutionMethod,
  Ingredient,
  RecipeInput,
} from "@/types/api";

export interface Dose {
  ingredient: Ingredient;
  volumeMl: number;
}

/** Volume proposto quando si aggiunge un ingrediente, per categoria.

    Non è un valore unico: aggiungere uno sciroppo con la stessa dose di un
    distillato produce un punto di partenza assurdo, e costringe a muovere
    lo slider prima ancora di guardare il risultato. Questi sono i dosaggi
    tipici da cui un barman partirebbe. */
const DEFAULT_VOLUME_ML: Partial<Record<Ingredient["category"], number>> = {
  SPIRIT: 50,
  LIQUEUR: 20,
  FORTIFIED_WINE: 30,
  WINE: 60,
  BITTER: 20,
  AMARO: 25,
  JUICE: 25,
  SYRUP: 15,
  ACID_SOLUTION: 5,
  MIXER: 80,
  WATER: 20,
};

const FALLBACK_VOLUME_ML = 25;

/** Attesa prima di richiedere il profilo al backend, in millisecondi.

    Trascinare uno slider genera decine di eventi al secondo. Senza attesa
    ognuno diventerebbe una richiesta, e il risultato mostrato sarebbe
    quello dell'ultima risposta *arrivata*, non dell'ultima posizione — con
    numeri che rimbalzano mentre la mano è ancora ferma. */
const DEBOUNCE_MS = 180;

export interface UseRecipeResult {
  doses: Dose[];
  method: DilutionMethod;
  name: string;
  profile: BalanceProfile | null;
  error: string | null;
  isCalculating: boolean;
  setName: (name: string) => void;
  setMethod: (method: DilutionMethod) => void;
  addIngredient: (ingredient: Ingredient) => void;
  removeIngredient: (ingredientId: string) => void;
  setVolume: (ingredientId: string, volumeMl: number) => void;
  applyVolumes: (volumes: Record<string, number>) => void;
  reset: () => void;
}

export function useRecipe(initialName = "Ricetta senza nome"): UseRecipeResult {
  const [doses, setDoses] = useState<Dose[]>([]);
  const [method, setMethod] = useState<DilutionMethod>("SHAKEN");
  const [name, setName] = useState(initialName);

  const [profile, setProfile] = useState<BalanceProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);

  /** Identifica la richiesta più recente: le risposte possono arrivare
      fuori ordine, e senza questo contatore una risposta lenta relativa a
      una posizione vecchia sovrascriverebbe il risultato di una nuova. */
  const latestRequest = useRef(0);

  const recipeInput = useMemo<RecipeInput | null>(() => {
    if (doses.length === 0) return null;
    return {
      name,
      dilution_method: method,
      ingredients: doses.map((dose) => ({
        ingredient_id: dose.ingredient.id,
        volume_ml: dose.volumeMl,
      })),
    };
  }, [doses, method, name]);

  useEffect(() => {
    if (recipeInput === null) {
      setProfile(null);
      setError(null);
      setIsCalculating(false);
      return;
    }

    setIsCalculating(true);
    const requestId = ++latestRequest.current;

    const timer = setTimeout(() => {
      calculateBalance(recipeInput)
        .then((response) => {
          if (requestId !== latestRequest.current) return;
          setProfile(response.profile);
          setError(null);
        })
        .catch((cause: unknown) => {
          if (requestId !== latestRequest.current) return;
          setError(cause instanceof ApiError ? cause.message : "Calcolo non riuscito");
        })
        .finally(() => {
          if (requestId === latestRequest.current) setIsCalculating(false);
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [recipeInput]);

  const addIngredient = useCallback((ingredient: Ingredient) => {
    setDoses((current) => {
      // L'aggregate di dominio rifiuta gli ingredienti ripetuti: qui si
      // previene a monte, invece di lasciare che l'errore torni dal backend
      // dopo che l'utente ha già cliccato.
      if (current.some((dose) => dose.ingredient.id === ingredient.id)) return current;
      const volumeMl = DEFAULT_VOLUME_ML[ingredient.category] ?? FALLBACK_VOLUME_ML;
      return [...current, { ingredient, volumeMl }];
    });
  }, []);

  const removeIngredient = useCallback((ingredientId: string) => {
    setDoses((current) => current.filter((dose) => dose.ingredient.id !== ingredientId));
  }, []);

  const setVolume = useCallback((ingredientId: string, volumeMl: number) => {
    setDoses((current) =>
      current.map((dose) =>
        dose.ingredient.id === ingredientId ? { ...dose, volumeMl } : dose,
      ),
    );
  }, []);

  /** Sostituisce in blocco i volumi, per applicare l'esito del solver. */
  const applyVolumes = useCallback((volumes: Record<string, number>) => {
    setDoses((current) =>
      current.map((dose) => {
        const proposed = volumes[dose.ingredient.id];
        return proposed === undefined ? dose : { ...dose, volumeMl: proposed };
      }),
    );
  }, []);

  const reset = useCallback(() => {
    setDoses([]);
    setProfile(null);
    setError(null);
  }, []);

  return {
    doses,
    method,
    name,
    profile,
    error,
    isCalculating,
    setName,
    setMethod,
    addIngredient,
    removeIngredient,
    setVolume,
    applyVolumes,
    reset,
  };
}
