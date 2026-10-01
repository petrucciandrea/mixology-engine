"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatMl } from "@/lib/utils";
import {
  DILUTION_METHOD_LABELS,
  DILUTION_METHODS,
  GLASS_LABELS,
  SERVING_ICE_LABELS,
  type DilutionMethod,
  type Recipe,
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
  // null = tutte. Il filtro per metodo è l'unica tipologia che il ricettario
  // conosce: è anche quella già mostrata come badge su ogni riga.
  const [method, setMethod] = useState<DilutionMethod | null>(null);
  const visible =
    method === null
      ? recipes
      : recipes.filter((r) => r.dilution_method === method);

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
            <div
              role="tablist"
              aria-label="Tipologia"
              className="mb-2 flex flex-wrap gap-1.5"
            >
              {[null, ...DILUTION_METHODS].map((option) => {
                const inOption =
                  option === null
                    ? recipes
                    : recipes.filter((r) => r.dilution_method === option);
                if (
                  option !== null &&
                  inOption.length === 0 &&
                  option !== method
                )
                  return null;
                const isSelected = option === method;
                const hasActive = inOption.some((r) => r.id === activeId);
                return (
                  <button
                    key={option ?? "ALL"}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => setMethod(option)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                      isSelected
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-line bg-surface-2 text-muted hover:text-foreground",
                    )}
                  >
                    {option === null ? "Tutti" : DILUTION_METHOD_LABELS[option]}
                    <Badge
                      tone={hasActive ? "accent" : "neutral"}
                      className="tabular px-1 py-0"
                      aria-label={
                        hasActive
                          ? `${inOption.length}, con la ricetta aperta`
                          : undefined
                      }
                    >
                      {inOption.length}
                    </Badge>
                  </button>
                );
              })}
            </div>
            {visible.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted">
                Nessuna ricetta di questa tipologia.
              </p>
            ) : (
              <ul role="tabpanel" className="flex flex-col">
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
                        <span className="flex shrink-0 flex-col items-end gap-1">
                          <Badge>{DILUTION_METHOD_LABELS[recipe.dilution_method]}</Badge>
                          <span className="text-[0.65rem] text-muted">
                            {recipe.glass !== null && `${GLASS_LABELS[recipe.glass]} · `}
                            {SERVING_ICE_LABELS[recipe.serving_ice]}
                          </span>
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
