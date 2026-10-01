"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, calculateBalance } from "@/lib/api";
import type {
  BalanceProfile,
  GlassFit,
  GlassType,
  ServingProfile,
  DilutionMethod,
  ServingIce,
  Ingredient,
  Recipe,
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
  servingIce: ServingIce;
  /** Bicchiere di servizio; `null` = non dichiarato, nessun tetto di volume. */
  glass: GlassType | null;
  name: string;
  /** Id della ricetta salvata da cui deriva la bozza; `null` se non è mai
      stata salvata. Decide se "Salva" crea una ricetta o aggiorna quella. */
  recipeId: string | null;
  /** Il payload pronto per il backend; `null` finché non c'è una dose. */
  recipeInput: RecipeInput | null;
  profile: BalanceProfile | null;
  /** Il drink dopo il ghiaccio di servizio; `null` se servito senza. */
  servingProfile: ServingProfile | null;
  /** Riempimento del bicchiere; `null` senza bicchiere o senza capienza. */
  glassFit: GlassFit | null;
  error: string | null;
  isCalculating: boolean;
  setName: (name: string) => void;
  setMethod: (method: DilutionMethod) => void;
  setServingIce: (servingIce: ServingIce) => void;
  setGlass: (glass: GlassType | null) => void;
  addIngredient: (ingredient: Ingredient) => void;
  removeIngredient: (ingredientId: string) => void;
  setVolume: (ingredientId: string, volumeMl: number) => void;
  applyVolumes: (volumes: Record<string, number>) => void;
  loadRecipe: (recipe: Recipe) => void;
  markSaved: (recipe: Recipe) => void;
  forgetRecipeId: () => void;
  reset: () => void;
}

export function useRecipe(initialName = "Ricetta senza nome"): UseRecipeResult {
  const [doses, setDoses] = useState<Dose[]>([]);
  const [method, setMethod] = useState<DilutionMethod>("SHAKEN");
  const [servingIce, setServingIce] = useState<ServingIce>("NONE");
  const [glass, setGlass] = useState<GlassType | null>(null);
  const [name, setName] = useState(initialName);
  const [recipeId, setRecipeId] = useState<string | null>(null);

  const [profile, setProfile] = useState<BalanceProfile | null>(null);
  const [servingProfile, setServingProfile] = useState<ServingProfile | null>(null);
  const [glassFit, setGlassFit] = useState<GlassFit | null>(null);
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
      serving_ice: servingIce,
      glass,
      ingredients: doses.map((dose) => ({
        ingredient_id: dose.ingredient.id,
        volume_ml: dose.volumeMl,
      })),
    };
  }, [doses, method, servingIce, glass, name]);

  useEffect(() => {
    if (recipeInput === null) {
      setProfile(null);
      setServingProfile(null);
      setGlassFit(null);
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
          setServingProfile(response.serving_profile);
          setGlassFit(response.glass_fit);
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

  /** Apre una ricetta salvata come bozza di lavoro.

      L'ordine delle dosi è quello salvato, cioè l'ordine di versamento: è
      informazione reale, e il solver assegna i volumi per posizione. */
  const loadRecipe = useCallback((recipe: Recipe) => {
    setDoses(
      recipe.ingredients.map((item) => ({
        ingredient: item.ingredient,
        volumeMl: item.volume_ml,
      })),
    );
    setMethod(recipe.dilution_method);
    setServingIce(recipe.serving_ice);
    setGlass(recipe.glass);
    setName(recipe.name);
    setRecipeId(recipe.id);
  }, []);

  /** Lega la bozza alla ricetta appena salvata: il prossimo salvataggio
      aggiornerà quella invece di crearne un'altra. */
  const markSaved = useCallback((recipe: Recipe) => {
    setRecipeId(recipe.id);
  }, []);

  /** Scollega la bozza da una ricetta che non esiste più, senza toccare
      il dosaggio a schermo: chi l'ha cancellata può ancora risalvarla. */
  const forgetRecipeId = useCallback(() => {
    setRecipeId(null);
  }, []);

  const reset = useCallback(() => {
    setDoses([]);
    setServingIce("NONE");
    setGlass(null);
    setName(initialName);
    setRecipeId(null);
    setProfile(null);
    setServingProfile(null);
    setGlassFit(null);
    setError(null);
  }, [initialName]);

  return {
    doses,
    method,
    servingIce,
    glass,
    name,
    recipeId,
    servingProfile,
    glassFit,
    recipeInput,
    profile,
    error,
    isCalculating,
    setName,
    setMethod,
    setServingIce,
    setGlass,
    addIngredient,
    removeIngredient,
    setVolume,
    applyVolumes,
    loadRecipe,
    markSaved,
    forgetRecipeId,
    reset,
  };
}
