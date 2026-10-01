"use client";

import { ChevronDown, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatMl } from "@/lib/utils";
import {
  DILUTION_METHOD_LABELS,
  GLASS_LABELS,
  RECIPE_FAMILIES,
  RECIPE_FAMILY_LABELS,
  type Recipe,
  type RecipeFamily,
} from "@/types/api";

interface RecipeBookProps {
  recipes: Recipe[];
  /** La ricetta aperta sul banco, se deriva da una salvata. */
  activeId: string | null;
  isLoading: boolean;
  onLoad: (recipe: Recipe) => void;
  onDelete: (recipe: Recipe) => void;
}

export function RecipeBook({
  recipes,
  activeId,
  isLoading,
  onLoad,
  onDelete,
}: RecipeBookProps) {
  // null = tutte. Le ricette senza famiglia compaiono solo qui: il filtro
  // non ha una voce "non classificate" perché sarebbe un residuo, non una
  // categoria.
  const [family, setFamily] = useState<RecipeFamily | null>(null);
  const visible =
    family === null ? recipes : recipes.filter((r) => r.family === family);

  return (
    <Card className="flex max-h-[18rem] min-h-0 shrink-0 flex-col">
      <CardHeader>
        <CardTitle>Ricettario</CardTitle>
        <span className="tabular font-mono text-xs text-muted">
          {recipes.length}
        </span>
      </CardHeader>

      <CardBody className="scrollbar-slim min-h-0 flex-1 overflow-y-auto py-2">
        {isLoading ? (
          <p className="py-4 text-center text-sm text-muted">
            Carico il ricettario…
          </p>
        ) : recipes.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted">
            Nessuna ricetta salvata. Componi un drink e premi «Salva».
          </p>
        ) : (
          <>
            <label className="relative mb-2 block">
              <span className="sr-only">Famiglia</span>
              <select
                value={family ?? ""}
                onChange={(event) =>
                  setFamily(
                    event.target.value === ""
                      ? null
                      : (event.target.value as RecipeFamily),
                  )
                }
                className="h-8 w-full appearance-none rounded-md border border-line bg-surface-2 pl-2.5 pr-8 text-sm focus:border-accent focus:outline-none"
              >
                <option value="">Tutte le famiglie · {recipes.length}</option>
                {RECIPE_FAMILIES.map((option) => {
                  const count = recipes.filter(
                    (r) => r.family === option,
                  ).length;
                  if (count === 0 && option !== family) return null;
                  return (
                    <option key={option} value={option}>
                      {RECIPE_FAMILY_LABELS[option]} · {count}
                    </option>
                  );
                })}
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
                aria-hidden
              />
            </label>
            {visible.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted">
                Nessuna ricetta di questa famiglia.
              </p>
            ) : (
              <ul className="flex flex-col">
                {visible.map((recipe) => {
                  const isActive = recipe.id === activeId;
                  // Il volume pre-diluizione: è quello che si versa, e basta a
                  // distinguere a colpo d'occhio uno short da un long drink.
                  const totalMl = recipe.ingredients.reduce(
                    (sum, item) => sum + item.volume_ml,
                    0,
                  );
                  return (
                    <li
                      key={recipe.id}
                      className="group flex items-center gap-1"
                    >
                      <button
                        type="button"
                        onClick={() => onLoad(recipe)}
                        aria-current={isActive ? "true" : undefined}
                        className={cn(
                          "flex min-w-0 flex-1 items-baseline justify-between gap-2 rounded px-2 py-1.5 text-left transition-colors",
                          isActive ? "bg-accent-soft" : "hover:bg-surface-2",
                        )}
                      >
                        <span className="min-w-0">
                          <span
                            className={cn(
                              "block truncate text-sm",
                              isActive && "font-medium text-accent",
                            )}
                          >
                            {recipe.name}
                          </span>
                          <span className="block truncate text-[0.68rem] text-muted">
                            {recipe.ingredients.length} ingredienti ·{" "}
                            {formatMl(totalMl)} ml
                          </span>
                        </span>
                        <span className="shrink-0 text-right text-[0.65rem] text-muted">
                          {DILUTION_METHOD_LABELS[recipe.dilution_method]}
                          {recipe.glass !== null && ` · ${GLASS_LABELS[recipe.glass]}`}
                        </span>
                      </button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => onDelete(recipe)}
                        aria-label={`Cancella ${recipe.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}
