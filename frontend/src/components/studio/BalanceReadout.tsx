"use client";

import { Badge } from "@/components/ui/badge";
import { formatAcidity, formatBrix, formatMl, formatRatio } from "@/lib/utils";
import type { BalanceProfile } from "@/types/api";

/** Finestra di riferimento del rapporto zuccheri/acidi per un sour
    equilibrato. Stessi valori del dominio; qui servono solo a disegnare la
    barra, la valutazione arriva dal backend (`is_balanced_sour`). */
const SOUR_MIN = 5.5;
const SOUR_MAX = 7.0;

interface BalanceReadoutProps {
  profile: BalanceProfile | null;
  isCalculating: boolean;
}

export function BalanceReadout({ profile, isCalculating }: BalanceReadoutProps) {
  if (profile === null) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        Il profilo compare appena la ricetta ha un ingrediente.
      </p>
    );
  }

  return (
    <div
      className="flex flex-col gap-5"
      // Durante il ricalcolo i numeri restano leggibili ma si smorzano: la
      // sensazione giusta è "si sta aggiornando", non "è sparito".
      style={{ opacity: isCalculating ? 0.65 : 1, transition: "opacity 120ms" }}
      aria-busy={isCalculating}
    >
      {/* L'ABV finale è il numero per cui si guarda questo pannello: prende
          la misura che merita, gli altri restano di supporto. */}
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col">
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted">
            ABV nel bicchiere
          </span>
          <span className="tabular font-display text-5xl leading-none text-accent">
            {profile.abv_post_percent.toFixed(1)}
            <span className="ml-1 text-2xl">%</span>
          </span>
          <span className="tabular mt-1 font-mono text-[0.68rem] text-muted">
            da {(profile.abv_pre * 100).toFixed(1)}% pre-diluizione
          </span>
        </div>

        <div className="flex flex-col items-end gap-1">
          <span className="tabular font-mono text-sm">
            {formatMl(profile.final_volume_ml)} ml
          </span>
          <span className="tabular font-mono text-[0.68rem] text-muted">
            +{formatMl(profile.dilution_water_ml)} ml d&apos;acqua
          </span>
          <Badge tone="neutral">
            diluizione {(profile.dilution_factor * 100).toFixed(0)}%
          </Badge>
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-px overflow-hidden rounded-md border border-line bg-line">
        <Measure label="Brix" value={formatBrix(profile.brix_post)} unit="°Bx" />
        <Measure label="Acidità" value={formatAcidity(profile.acidity_post)} unit="w/v" />
        <Measure
          label="Alcol puro"
          value={formatMl(profile.pure_alcohol_ml)}
          unit="ml"
        />
      </dl>

      <SugarAcidGauge
        ratio={profile.sugar_acid_ratio}
        isBalanced={profile.is_balanced_sour}
      />
    </div>
  );
}

function Measure({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 bg-surface px-3 py-2.5">
      <dt className="font-mono text-[0.6rem] uppercase tracking-[0.12em] text-muted">
        {label}
      </dt>
      <dd className="tabular font-mono text-base">
        {value}
        <span className="ml-1 text-[0.65rem] text-muted">{unit}</span>
      </dd>
    </div>
  );
}

/**
 * Il rapporto zuccheri/acidi su una scala, non come numero isolato.
 *
 * Il numero da solo non dice nulla a chi non ha in testa la finestra dei
 * sour: la posizione rispetto alla banda verde sì, e si legge in un colpo
 * d'occhio mentre si muove uno slider.
 */
function SugarAcidGauge({
  ratio,
  isBalanced,
}: {
  ratio: number | null;
  isBalanced: boolean;
}) {
  const SCALE_MAX = 14;

  if (ratio === null) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted">
            Zuccheri / acidi
          </span>
          <span className="font-mono text-sm text-muted">—</span>
        </div>
        <p className="text-xs leading-relaxed text-muted">
          Senza acidi il rapporto non esiste: è un drink che non si giudica su
          quest&apos;asse, come un Negroni.
        </p>
      </div>
    );
  }

  const position = Math.min(ratio / SCALE_MAX, 1) * 100;
  const windowStart = (SOUR_MIN / SCALE_MAX) * 100;
  const windowWidth = ((SOUR_MAX - SOUR_MIN) / SCALE_MAX) * 100;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted">
          Zuccheri / acidi
        </span>
        <span className="flex items-baseline gap-2">
          <span className="tabular font-mono text-sm">{formatRatio(ratio)}</span>
          <Badge tone={isBalanced ? "good" : "alert"}>
            {isBalanced ? "in finestra" : ratio > SOUR_MAX ? "dolce" : "aspro"}
          </Badge>
        </span>
      </div>

      <div className="relative h-2 w-full rounded-full bg-surface-2">
        <div
          className="absolute inset-y-0 rounded-full bg-good/25"
          style={{ left: `${windowStart}%`, width: `${windowWidth}%` }}
          aria-hidden
        />
        <div
          className="absolute top-1/2 h-3.5 w-[3px] -translate-y-1/2 rounded-full bg-foreground"
          style={{ left: `calc(${position}% - 1.5px)` }}
          aria-hidden
        />
      </div>

      <div className="tabular flex justify-between font-mono text-[0.6rem] text-muted">
        <span>0</span>
        <span>{SOUR_MIN}–{SOUR_MAX} equilibrato</span>
        <span>{SCALE_MAX}+</span>
      </div>
    </div>
  );
}
