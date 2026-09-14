"use client";

import { AlertTriangle, ArrowLeftRight, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import type { Dose } from "@/hooks/useRecipe";
import { findSubstitutes, suggestPairings } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
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

interface MatcherPanelProps {
  doses: Dose[];
  onAdd: (ingredient: Ingredient) => void;
}

export function MatcherPanel({ doses, onAdd }: MatcherPanelProps) {
  const [tab, setTab] = useState<Tab>("pairings");
  const [focusId, setFocusId] = useState<string | null>(null);

  const focus = doses.find((dose) => dose.ingredient.id === focusId) ?? doses[0];

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>Matcher</CardTitle>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant={tab === "pairings" ? "primary" : "ghost"}
            onClick={() => setTab("pairings")}
          >
            Abbinamenti
          </Button>
          <Button
            size="sm"
            variant={tab === "substitutes" ? "primary" : "ghost"}
            onClick={() => setTab("substitutes")}
          >
            Sostituti
          </Button>
        </div>
      </CardHeader>

      <CardBody>
        {doses.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">
            Aggiungi un ingrediente per vedere cosa gli sta bene accanto.
          </p>
        ) : tab === "pairings" ? (
          <Pairings doses={doses} onAdd={onAdd} />
        ) : (
          <Substitutes
            doses={doses}
            focusId={focus?.ingredient.id ?? null}
            onFocus={setFocusId}
          />
        )}
      </CardBody>
    </Card>
  );
}

function Pairings({
  doses,
  onAdd,
}: {
  doses: Dose[];
  onAdd: (ingredient: Ingredient) => void;
}) {
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

  if (isLoading) {
    return <p className="py-6 text-center text-sm text-muted">Consulto il grafo…</p>;
  }

  if (suggestions.length === 0) {
    return (
      <p className="py-6 text-center text-sm leading-relaxed text-muted">
        Nessun abbinamento proposto: gli ingredienti scelti non hanno legami
        nel grafo, o sono tutti privi di profilo organolettico.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2.5">
      {suggestions.map((suggestion) => (
        <li key={suggestion.ingredient.id} className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <span className="block truncate text-sm">
              {suggestion.ingredient.name}
            </span>
            <span className="block text-[0.68rem] leading-relaxed text-muted">
              {suggestion.rationale}
            </span>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onAdd(suggestion.ingredient)}
            aria-label={`Aggiungi ${suggestion.ingredient.name}`}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </Button>
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
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1">
        {doses.map((dose) => (
          <Button
            key={dose.ingredient.id}
            size="sm"
            variant={dose.ingredient.id === focusId ? "primary" : "secondary"}
            onClick={() => onFocus(dose.ingredient.id)}
          >
            {dose.ingredient.name}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <p className="py-6 text-center text-sm text-muted">Cerco sostituti…</p>
      ) : candidates.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">
          Nessun candidato: l&apos;ingrediente non ha un profilo organolettico.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {candidates.map((candidate) => (
            <li key={candidate.ingredient.id} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-sm">{candidate.ingredient.name}</span>
                <Badge tone={candidate.overall >= 0.5 ? "good" : "neutral"}>
                  {formatPercent(candidate.overall, 0)}
                </Badge>
              </div>

              {/* I due assi restano separati anche visivamente: il
                  punteggio complessivo dice *quanto*, le due barre dicono
                  *perché* — ed è il perché a decidere se usarlo. */}
              <div className="flex gap-3">
                <AxisBar
                  label="aroma"
                  value={candidate.flavor_similarity}
                  icon={<ArrowLeftRight className="h-2.5 w-2.5" aria-hidden />}
                />
                <AxisBar label="fisica" value={candidate.physical_compatibility} />
              </div>

              {candidate.warnings.length > 0 && (
                <ul className="flex flex-col gap-0.5">
                  {candidate.warnings.map((warning) => (
                    <li
                      key={warning}
                      className="flex gap-1.5 text-[0.68rem] leading-relaxed text-muted"
                    >
                      <AlertTriangle
                        className="mt-0.5 h-3 w-3 shrink-0 text-alert"
                        aria-hidden
                      />
                      <span>{warning}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AxisBar({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="flex items-center gap-1 font-mono text-[0.58rem] uppercase tracking-[0.1em] text-muted">
        {icon}
        {label}
        <span className="tabular ml-auto">{formatPercent(value, 0)}</span>
      </span>
      <div className="h-1 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
    </div>
  );
}
