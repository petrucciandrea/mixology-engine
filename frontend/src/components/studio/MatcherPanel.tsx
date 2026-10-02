"use client";

import { useEffect, useState } from "react";

import type { Dose } from "@/hooks/useRecipe";
import { findSubstitutes, suggestPairings } from "@/lib/api";
import { CATEGORY_COLORS } from "@/lib/categoryColors";
import { cn, formatPercent } from "@/lib/utils";
import type { Ingredient, PairingSuggestion, Substitution } from "@/types/api";

/**
 * Il matcher, con le sue due domande tenute visibilmente separate.
 *
 * "Cosa aggiungo" e "con cosa sostituisco" sono meccanismi diversi nel
 * backend — affinità sul grafo contro similarità vettoriale — e mostrarli
 * come un unico elenco di "ingredienti consigliati" cancellerebbe proprio
 * la distinzione che rende il sistema corretto.
 */
type Tab = "pairings" | "substitutes";

/** Sopra questa soglia un sostituto è credibile su entrambi gli assi. */
const GOOD_SUBSTITUTE = 0.5;

interface MatcherPanelProps {
  doses: Dose[];
  onAdd: (ingredient: Ingredient) => void;
}

export function MatcherPanel({ doses, onAdd }: MatcherPanelProps) {
  const [tab, setTab] = useState<Tab>("pairings");
  const [focusId, setFocusId] = useState<string | null>(null);

  const focus = doses.find((dose) => dose.ingredient.id === focusId) ?? doses[0];

  return (
    <div className="flex flex-col">
      <div className="flex gap-1 px-1 pb-2 pt-1">
        <Chip isOn={tab === "pairings"} onClick={() => setTab("pairings")}>
          Abbinamenti
        </Chip>
        <Chip isOn={tab === "substitutes"} onClick={() => setTab("substitutes")}>
          Sostituti
        </Chip>
      </div>

      {doses.length === 0 ? (
        <Note>Aggiungi un ingrediente per vedere cosa gli sta bene accanto.</Note>
      ) : tab === "pairings" ? (
        <Pairings doses={doses} onAdd={onAdd} />
      ) : (
        <Substitutes doses={doses} focusId={focus?.ingredient.id ?? null} onFocus={setFocusId} />
      )}
    </div>
  );
}

function Pairings({ doses, onAdd }: { doses: Dose[]; onAdd: (ingredient: Ingredient) => void }) {
  const [suggestions, setSuggestions] = useState<PairingSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // La chiave è la lista ordinata degli id: i suggerimenti dipendono da
  // *quali* ingredienti ci sono, non da quanto ce n'è. Legare l'effetto ai
  // volumi lo farebbe ripartire a ogni movimento di slider, per un
  // risultato che non cambierebbe.
  const seedKey = doses
    .map((dose) => dose.ingredient.id)
    .sort()
    .join(",");

  useEffect(() => {
    if (seedKey === "") {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    suggestPairings(seedKey.split(","), 5)
      .then((found) => {
        if (!cancelled) setSuggestions(found);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seedKey]);

  if (isLoading) return <Note>Consulto il grafo…</Note>;
  if (suggestions.length === 0)
    return (
      <Note>
        Nessun abbinamento proposto: gli ingredienti scelti non hanno legami nel grafo, o sono
        tutti privi di profilo organolettico.
      </Note>
    );

  return (
    <ul className="flex flex-col">
      {suggestions.map(({ ingredient, rationale }) => (
        <li key={ingredient.id} className="flex items-start gap-2 px-1.5 py-[7px]">
          <span
            className="mt-1.5 h-2 w-2 shrink-0 rounded-sm"
            style={{ backgroundColor: CATEGORY_COLORS[ingredient.category] }}
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block text-sm">{ingredient.name}</span>
            <span className="block text-xs leading-[1.45] text-muted">{rationale}</span>
          </span>
          <button
            type="button"
            onClick={() => onAdd(ingredient)}
            aria-label={`Aggiungi ${ingredient.name}`}
            className="h-[30px] w-[30px] shrink-0 cursor-pointer rounded-md border border-line text-lg leading-none text-accent hover:bg-hover"
          >
            +
          </button>
        </li>
      ))}
    </ul>
  );
}

function Substitutes({
  doses,
  focusId,
  onFocus,
}: {
  doses: Dose[];
  focusId: string | null;
  onFocus: (id: string) => void;
}) {
  const [candidates, setCandidates] = useState<Substitution[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (focusId === null) {
      setCandidates([]);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    findSubstitutes(focusId, 4)
      .then((found) => {
        if (!cancelled) setCandidates(found);
      })
      .catch(() => {
        if (!cancelled) setCandidates([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [focusId]);

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap gap-1 px-1 pb-2" role="group" aria-label="Ingrediente da sostituire">
        {doses.map((dose) => (
          <Chip
            key={dose.ingredient.id}
            isOn={dose.ingredient.id === focusId}
            onClick={() => onFocus(dose.ingredient.id)}
            className="text-[12.5px]"
          >
            {dose.ingredient.name}
          </Chip>
        ))}
      </div>

      {isLoading ? (
        <Note>Cerco sostituti…</Note>
      ) : candidates.length === 0 ? (
        <Note>Nessun candidato: l&apos;ingrediente non ha un profilo organolettico.</Note>
      ) : (
        <ul className="flex flex-col">
          {candidates.map((candidate) => {
            const isGood = candidate.overall >= GOOD_SUBSTITUTE;
            return (
              <li key={candidate.ingredient.id} className="flex flex-col gap-[5px] px-1.5 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm">{candidate.ingredient.name}</span>
                  <span
                    className={cn(
                      "tabular rounded px-1.5 py-0.5 font-mono text-[11.5px] font-medium",
                      isGood ? "bg-good-soft text-good" : "bg-surface-2 text-soft",
                    )}
                  >
                    {formatPercent(candidate.overall, 0)}
                  </span>
                </div>
                {/* I due assi restano separati: il punteggio complessivo dice
                    *quanto*, i due assi dicono *perché* — ed è il perché a
                    decidere se usarlo. */}
                <div className="tabular font-mono text-xs text-muted">
                  aroma {formatPercent(candidate.flavor_similarity, 0)} · fisica{" "}
                  {formatPercent(candidate.physical_compatibility, 0)}
                </div>
                {candidate.warnings.map((warning) => (
                  <span key={warning} className="text-xs leading-normal text-warn">
                    ! {warning}
                  </span>
                ))}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Chip({
  isOn,
  onClick,
  className,
  children,
}: {
  isOn: boolean;
  onClick: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isOn}
      className={cn(
        "h-7 cursor-pointer rounded-md border px-2.5 text-[13px] font-medium transition-colors",
        isOn
          ? "border-accent-line bg-accent-soft text-accent-strong"
          : "border-transparent text-soft hover:bg-surface-2",
        className,
      )}
    >
      {children}
    </button>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="px-2 py-6 text-center text-sm leading-relaxed text-muted">{children}</p>;
}
