"use client";

import { useState } from "react";

import { cn, formatMl } from "@/lib/utils";
import {
  DILUTION_METHOD_LABELS,
  GLASS_LABELS,
  RECIPE_FAMILIES,
  RECIPE_FAMILY_LABELS,
  type Recipe,
  type RecipeFamily,
} from "@/types/api";

interface RecipeBookPanelProps {
  recipes: Recipe[];
  /** La ricetta aperta sul banco, se deriva da una salvata. */
  activeId: string | null;
  isLoading: boolean;
  onLoad: (recipe: Recipe) => void;
  onDelete: (recipe: Recipe) => void;
}

export function RecipeBookPanel({
  recipes,
  activeId,
  isLoading,
  onLoad,
  onDelete,
}: RecipeBookPanelProps) {
  // null = tutte. Le ricette senza famiglia compaiono solo qui: il filtro
  // non ha una voce "non classificate" perché sarebbe un residuo, non una
  // categoria.
  const [family, setFamily] = useState<RecipeFamily | null>(null);
  const visible = family === null ? recipes : recipes.filter((r) => r.family === family);

  if (isLoading) return <Note>Carico il ricettario…</Note>;
  if (recipes.length === 0)
    return <Note>Nessuna ricetta salvata. Componi un drink e premi «Salva».</Note>;

  return (
    <div className="flex flex-col gap-1">
      <label className="block p-1 pb-1.5">
        <span className="sr-only">Famiglia</span>
        <select
          value={family ?? ""}
          onChange={(event) =>
            setFamily(event.target.value === "" ? null : (event.target.value as RecipeFamily))
          }
          className="h-[34px] w-full rounded-[7px] border border-line bg-surface-2 px-2.5 text-sm focus:border-accent focus:outline-none"
        >
          <option value="">Tutte le famiglie · {recipes.length}</option>
          {RECIPE_FAMILIES.map((option) => {
            const count = recipes.filter((r) => r.family === option).length;
            if (count === 0 && option !== family) return null;
            return (
              <option key={option} value={option}>
                {RECIPE_FAMILY_LABELS[option]} · {count}
              </option>
            );
          })}
        </select>
      </label>

      {visible.length === 0 ? (
        <Note>Nessuna ricetta di questa famiglia.</Note>
      ) : (
        <ul className="flex flex-col">
          {visible.map((recipe) => {
            const isActive = recipe.id === activeId;
            // Il volume pre-diluizione: è quello che si versa, e basta a
            // distinguere a colpo d'occhio uno short da un long drink.
            const totalMl = recipe.ingredients.reduce((sum, item) => sum + item.volume_ml, 0);
            return (
              <li key={recipe.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onLoad(recipe)}
                  aria-current={isActive ? "true" : undefined}
                  className={cn(
                    "flex w-full cursor-pointer items-baseline justify-between gap-2 rounded-md py-2 pl-2.5 pr-9 text-left transition-colors",
                    isActive ? "bg-accent-soft" : "hover:bg-hover",
                  )}
                >
                  <span className="min-w-0">
                    <span
                      className={cn(
                        "block truncate text-sm",
                        isActive && "font-semibold text-accent-strong",
                      )}
                    >
                      {recipe.name}
                    </span>
                    <span className="block text-xs text-muted">
                      {recipe.ingredients.length} ingredienti · {formatMl(totalMl)} ml
                    </span>
                  </span>
                  <span className="shrink-0 whitespace-nowrap text-xs text-muted">
                    {DILUTION_METHOD_LABELS[recipe.dilution_method]}
                    {recipe.glass !== null && ` · ${GLASS_LABELS[recipe.glass]}`}
                  </span>
                </button>
                {/* La cancellazione resta a portata ma non in vista: è
                    l'azione meno frequente e l'unica irreversibile. */}
                <button
                  type="button"
                  onClick={() => onDelete(recipe)}
                  aria-label={`Cancella ${recipe.name}`}
                  className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 cursor-pointer rounded-md text-[17px] leading-none text-muted opacity-0 transition-opacity hover:text-alert focus-visible:opacity-100 group-hover:opacity-100"
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="px-2 py-6 text-center text-sm text-muted">{children}</p>;
}
