"use client";

import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatAbv } from "@/lib/utils";
import { CATEGORY_LABELS, type Ingredient, type IngredientCategory } from "@/types/api";

/** Ordine in cui le famiglie compaiono fra i filtri.

    Non è alfabetico: segue l'ordine in cui si compone un drink — prima la
    base alcolica, poi i modificatori, poi la parte acida e dolce. */
const CATEGORY_ORDER: IngredientCategory[] = [
  "SPIRIT",
  "LIQUEUR",
  "FORTIFIED_WINE",
  "WINE",
  "BITTER",
  "AMARO",
  "JUICE",
  "ACID_SOLUTION",
  "SYRUP",
  "MIXER",
  "WATER",
  "OTHER",
];

interface IngredientPickerProps {
  ingredients: Ingredient[];
  selectedIds: Set<string>;
  onAdd: (ingredient: Ingredient) => void;
  isLoading: boolean;
}

export function IngredientPicker({
  ingredients,
  selectedIds,
  onAdd,
  isLoading,
}: IngredientPickerProps) {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<IngredientCategory>("SPIRIT");

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = ingredients.filter((ingredient) => {
      if (needle === "") return true;
      // Si cerca anche fra i descrittori dominanti: "affumicato" deve
      // trovare il mezcal anche se la parola non è nel nome.
      const haystack = [
        ingredient.name,
        CATEGORY_LABELS[ingredient.category],
        ...ingredient.dominant_flavors,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });

    return CATEGORY_ORDER.map((category) => ({
      category,
      items: matching.filter((ingredient) => ingredient.category === category),
    })).filter((group) => group.items.length > 0);
  }, [ingredients, query]);

  // Se la famiglia scelta non ha risultati (es. dopo una ricerca) si ripiega
  // sulla prima che ne ha, senza perdere la scelta quando la ricerca si svuota.
  const activeGroup =
    grouped.find((group) => group.category === activeCategory) ?? grouped[0];

  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader>
        <CardTitle>Dispensa</CardTitle>
        <span className="tabular font-mono text-xs text-muted">
          {ingredients.length}
        </span>
      </CardHeader>

      <CardBody className="flex min-h-0 flex-col gap-3 pb-2">
        <label className="relative block">
          <span className="sr-only">Cerca un ingrediente</span>
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
            aria-hidden
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nome, famiglia o aroma…"
            className="h-9 w-full rounded-md border border-line bg-surface-2 pl-8 pr-3 text-sm placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </label>

        {!isLoading && grouped.length > 0 && (
          <div role="tablist" aria-label="Famiglia" className="flex flex-wrap gap-1.5">
            {grouped.map((group) => {
              const isActive = group.category === activeGroup?.category;
              const selectedCount = group.items.filter((item) =>
                selectedIds.has(item.id),
              ).length;
              return (
                <button
                  key={group.category}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveCategory(group.category)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                    isActive
                      ? "border-accent bg-accent-soft text-accent"
                      : "border-line bg-surface-2 text-muted hover:text-foreground",
                  )}
                >
                  {CATEGORY_LABELS[group.category]}
                  {selectedCount > 0 && (
                    <Badge
                      tone="accent"
                      className="tabular px-1 py-0"
                      aria-label={`${selectedCount} in ricetta`}
                    >
                      {selectedCount}
                    </Badge>
                  )}
                </button>
              );
            })}
          </div>
        )}

        <div className="scrollbar-slim -mr-2 min-h-0 flex-1 overflow-y-auto pr-2">
          {isLoading ? (
            <p className="py-6 text-center text-sm text-muted">Carico la dispensa…</p>
          ) : activeGroup === undefined ? (
            <p className="py-6 text-center text-sm text-muted">
              Nessun ingrediente corrisponde a «{query}».
            </p>
          ) : (
            <ul role="tabpanel" className="flex flex-col">
              {activeGroup.items.map((ingredient) => {
                const alreadyUsed = selectedIds.has(ingredient.id);
                return (
                  <li key={ingredient.id}>
                    <button
                      type="button"
                      disabled={alreadyUsed}
                      onClick={() => onAdd(ingredient)}
                      className={cn(
                        "group flex w-full items-baseline justify-between gap-2 rounded px-2 py-1.5 text-left transition-colors",
                        alreadyUsed ? "cursor-default opacity-40" : "hover:bg-surface-2",
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm">{ingredient.name}</span>
                        {ingredient.dominant_flavors.length > 0 && (
                          <span className="block truncate text-[0.68rem] text-muted">
                            {ingredient.dominant_flavors.slice(0, 3).join(" · ")}
                          </span>
                        )}
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        {ingredient.physical_profile.abv > 0 && (
                          <span className="tabular font-mono text-[0.68rem] text-muted">
                            {formatAbv(ingredient.physical_profile.abv)}
                          </span>
                        )}
                        {!alreadyUsed && (
                          <Plus
                            className="h-3.5 w-3.5 text-muted group-hover:text-accent"
                            aria-hidden
                          />
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
