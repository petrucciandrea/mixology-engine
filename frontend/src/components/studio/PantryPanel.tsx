"use client";

import { useMemo, useState } from "react";

import { CATEGORY_COLORS } from "@/lib/categoryColors";
import { flavorLabel } from "@/lib/flavor";
import { cn } from "@/lib/utils";
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

interface PantryPanelProps {
  ingredients: Ingredient[];
  selectedIds: Set<string>;
  onAdd: (ingredient: Ingredient) => void;
  isLoading: boolean;
}

export function PantryPanel({ ingredients, selectedIds, onAdd, isLoading }: PantryPanelProps) {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<IngredientCategory>("SPIRIT");

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = ingredients.filter((ingredient) => {
      if (needle === "") return true;
      // Si cerca anche fra i descrittori dominanti, in italiano: "affumicato"
      // deve trovare il mezcal anche se la parola non è nel nome.
      const haystack = [
        ingredient.name,
        CATEGORY_LABELS[ingredient.category],
        ...ingredient.dominant_flavors.map(flavorLabel),
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
  const activeGroup = grouped.find((group) => group.category === activeCategory) ?? grouped[0];

  return (
    <div className="flex flex-col gap-2 p-1">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Nome, famiglia o aroma…"
        aria-label="Cerca un ingrediente"
        className="h-9 rounded-[7px] border border-line bg-surface-2 px-3 text-sm placeholder:text-muted focus:border-accent focus:outline-none"
      />

      {!isLoading && activeGroup !== undefined && (
        <label className="relative block">
          <span className="sr-only">Famiglia</span>
          <span
            className="pointer-events-none absolute left-2.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full"
            style={{ backgroundColor: CATEGORY_COLORS[activeGroup.category] }}
            aria-hidden
          />
          <select
            value={activeGroup.category}
            onChange={(event) => setActiveCategory(event.target.value as IngredientCategory)}
            className="h-[34px] w-full rounded-[7px] border border-line bg-surface-2 pl-7 pr-2.5 text-sm focus:border-accent focus:outline-none"
          >
            {grouped.map((group) => (
              <option key={group.category} value={group.category}>
                {CATEGORY_LABELS[group.category]} · {group.items.length}
              </option>
            ))}
          </select>
        </label>
      )}

      {isLoading ? (
        <p className="py-6 text-center text-sm text-muted">Carico la dispensa…</p>
      ) : activeGroup === undefined ? (
        <p className="py-6 text-center text-sm text-muted">
          {ingredients.length === 0
            ? "La dispensa è vuota."
            : `Nessun ingrediente corrisponde a «${query}».`}
        </p>
      ) : (
        <ul className="flex flex-col">
          {activeGroup.items.map((ingredient) => {
            const isUsed = selectedIds.has(ingredient.id);
            return (
              <li key={ingredient.id}>
                <button
                  type="button"
                  disabled={isUsed}
                  onClick={() => onAdd(ingredient)}
                  aria-label={
                    isUsed ? `${ingredient.name}, già in ricetta` : `Aggiungi ${ingredient.name}`
                  }
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-2 py-[7px] text-left transition-colors",
                    isUsed ? "cursor-default opacity-40" : "cursor-pointer hover:bg-hover",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm">{ingredient.name}</span>
                    {ingredient.dominant_flavors.length > 0 && (
                      <span className="block truncate text-xs text-muted">
                        {ingredient.dominant_flavors.slice(0, 3).map(flavorLabel).join(" · ")}
                      </span>
                    )}
                  </span>
                  <span className="tabular flex shrink-0 items-center gap-2.5 font-mono text-xs text-muted">
                    {ingredient.physical_profile.abv > 0 &&
                      `${Math.round(ingredient.physical_profile.abv * 100)}%`}
                    <span className="font-sans text-lg leading-none text-accent" aria-hidden>
                      +
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
