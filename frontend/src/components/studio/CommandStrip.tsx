"use client";

import type { CSSProperties, ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TargetFields, UseSolverResult } from "@/hooks/useSolver";
import { cn, formatMl, formatPercent } from "@/lib/utils";
import {
  SOLVER_STATUS_LABELS,
  USABLE_SOLVER_STATUSES,
  type BalanceProfile,
  type GlassFit,
  type SolverResult,
} from "@/types/api";

/** Finestra di riferimento del rapporto zuccheri/acidi per un sour
    equilibrato, su una scala da 0 a 14. Stessi valori del dominio; qui
    servono solo a disegnare la barra, la valutazione arriva dal backend
    (`is_balanced_sour`). */
const SOUR_MIN = 5.5;
const SOUR_MAX = 7.0;
const RATIO_SCALE_MAX = 14;

/** Sotto questo scarto relativo un target si considera raggiunto: è
    l'ordine dell'errore che introduce da solo l'arrotondamento dei volumi
    al passo del dosatore (2.5 ml su un centinaio). */
const TARGET_TOLERANCE = 0.03;

const FLASH_SHADOW = "0 0 0 1px #e8812b, 0 0 24px rgba(232,129,43,.25)";

interface CommandStripProps {
  profile: BalanceProfile | null;
  glassFit: GlassFit | null;
  isCalculating: boolean;
  solver: UseSolverResult;
}

/**
 * Le quattro letture che decidono se un drink è giusto, accanto al comando
 * che lo corregge. Stanno sulla stessa striscia perché si usano insieme:
 * si legge, si fissa un target, si preme, si rilegge.
 */
export function CommandStrip({ profile, glassFit, isCalculating, solver }: CommandStripProps) {
  const flash: CSSProperties = {
    boxShadow: solver.flash ? FLASH_SHADOW : "0 0 0 1px transparent",
    transition: "box-shadow .35s",
  };
  const ratio = profile?.sugar_acid_ratio ?? null;
  const totalPre = profile?.total_volume_ml ?? 0;

  return (
    <section
      aria-label="Letture chiave e solver"
      className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line-soft md:grid-cols-4 xl:grid-cols-[repeat(4,minmax(0,1fr))_minmax(440px,1.5fr)]"
    >
      <div
        className="contents"
        // Durante il ricalcolo i numeri restano leggibili ma si smorzano: la
        // sensazione giusta è "si sta aggiornando", non "è sparito".
        aria-busy={isCalculating}
      >
        <Readout label="ABV nel bicchiere" style={flash} dimmed={isCalculating}>
          <Figure className="text-accent-strong">
            {profile === null ? (
              "—"
            ) : (
              <>
                {profile.abv_post_percent.toFixed(1)}
                <span className="text-xl text-accent">%</span>
              </>
            )}
          </Figure>
          <Footnote>
            {profile === null ? "nessun ingrediente" : `pre ${(profile.abv_pre * 100).toFixed(1)}%`}
            {solver.targets.abv.trim() !== "" && ` · target ${solver.targets.abv}%`}
          </Footnote>
        </Readout>

        <Readout
          label="Zuccheri / acidi"
          style={flash}
          dimmed={isCalculating}
          badge={
            ratio === null ? null : (
              <Badge tone={profile?.is_balanced_sour ? "good" : "alert"}>
                {profile?.is_balanced_sour ? "in finestra" : ratio > SOUR_MAX ? "dolce" : "aspro"}
              </Badge>
            )
          }
        >
          <Figure>{ratio === null ? "—" : ratio.toFixed(1)}</Figure>
          <div className="relative mt-3 h-1.5 rounded-full bg-surface-2" aria-hidden>
            <div
              className="absolute inset-y-0 rounded-full bg-good/35"
              style={{
                left: `${(SOUR_MIN / RATIO_SCALE_MAX) * 100}%`,
                width: `${((SOUR_MAX - SOUR_MIN) / RATIO_SCALE_MAX) * 100}%`,
              }}
            />
            {ratio !== null && (
              <div
                className="absolute -top-1 -ml-[1.5px] h-3.5 w-[3px] rounded-sm bg-foreground transition-[left] duration-200"
                style={{ left: `${Math.min(ratio / RATIO_SCALE_MAX, 1) * 100}%` }}
              />
            )}
          </div>
          {ratio === null && profile !== null && (
            <Footnote>senza acidi il rapporto non esiste</Footnote>
          )}
        </Readout>

        <Readout label="Volume servito" dimmed={isCalculating}>
          <Figure>
            {profile === null ? (
              "—"
            ) : (
              <>
                {profile.final_volume_ml.toFixed(0)}
                <span className="ml-1 text-lg text-soft">ml</span>
              </>
            )}
          </Figure>
          <Footnote>
            {formatMl(totalPre)} versati · +{formatMl(profile?.dilution_water_ml ?? 0)} acqua
          </Footnote>
        </Readout>

        <Readout
          label="Riempimento"
          dimmed={isCalculating}
          badge={
            glassFit === null ? null : (
              <Badge tone={glassFit.overflows ? "alert" : "good"}>
                {glassFit.overflows ? "trabocca" : "ci sta"}
              </Badge>
            )
          }
        >
          <Figure>
            {glassFit === null ? (
              "—"
            ) : (
              <>
                {Math.round(glassFit.fill_ratio * 100)}
                <span className="text-lg text-soft">%</span>
              </>
            )}
          </Figure>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <div
              className={cn(
                "h-full transition-[width] duration-200",
                glassFit?.overflows ? "bg-alert" : "bg-good/60",
              )}
              style={{ width: `${Math.min(1, glassFit?.fill_ratio ?? 0) * 100}%` }}
            />
          </div>
          {glassFit !== null && (
            <Footnote>
              {formatMl(glassFit.volume_ml)} di {formatMl(glassFit.max_volume_ml)} ml ammessi
            </Footnote>
          )}
        </Readout>
      </div>

      <SolverConsole solver={solver} />
    </section>
  );
}

function Readout({
  label,
  badge,
  dimmed,
  style,
  children,
}: {
  label: string;
  badge?: ReactNode;
  dimmed: boolean;
  style?: CSSProperties;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 bg-surface px-[18px] py-4" style={style}>
      <div className="flex min-h-[19px] items-center justify-between gap-2">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
          {label}
        </span>
        {badge}
      </div>
      <div style={{ opacity: dimmed ? 0.65 : 1, transition: "opacity 120ms" }}>{children}</div>
    </div>
  );
}

function Figure({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "tabular mt-3 whitespace-nowrap font-mono text-[38px] font-medium leading-none tracking-[-0.02em] sm:text-[46px]",
        className,
      )}
    >
      {children}
    </div>
  );
}

function Footnote({ children }: { children: ReactNode }) {
  return <div className="tabular mt-2 font-mono text-[12.5px] text-muted">{children}</div>;
}

const TARGET_FIELDS: { field: keyof TargetFields; label: string; placeholder: string }[] = [
  { field: "abv", label: "ABV %", placeholder: "16" },
  { field: "sugarAcidRatio", label: "Zucch./ac.", placeholder: "6.2" },
  { field: "finalVolumeMl", label: "Vol. ml", placeholder: "150" },
];

function SolverConsole({ solver }: { solver: UseSolverResult }) {
  const { phase, result } = solver;
  const isRunning = phase === "running";

  return (
    <form
      className="col-span-2 flex flex-col gap-2.5 bg-solver px-4 py-3.5 md:col-span-4 xl:col-span-1"
      onSubmit={(event) => {
        event.preventDefault();
        solver.run();
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-accent-light">
          Solver · SLSQP
        </span>
        <span className="text-xs text-muted">target dopo la diluizione · volume = vincolo</span>
      </div>

      <div className="grid grid-cols-3 items-end gap-2 sm:grid-cols-[repeat(3,minmax(60px,1fr))_minmax(120px,auto)]">
        {TARGET_FIELDS.map(({ field, label, placeholder }) => (
          <label key={field} className="flex min-w-0 flex-col gap-1">
            <span className="whitespace-nowrap font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-muted">
              {label}
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              placeholder={placeholder}
              value={solver.targets[field]}
              onChange={(event) => solver.setTarget(field, event.target.value)}
              className="tabular h-11 w-full rounded-[7px] border border-solver-line bg-solver-field px-2.5 font-mono text-base placeholder:text-muted/50 focus:border-accent focus:outline-none"
            />
          </label>
        ))}
        <button
          type="submit"
          disabled={!solver.canRun}
          className="relative col-span-3 h-11 cursor-pointer overflow-hidden whitespace-nowrap rounded-lg sm:col-span-1 bg-accent px-4 text-base font-semibold text-ink transition-[background-color,transform] hover:bg-accent-strong active:scale-[0.98] disabled:cursor-default disabled:opacity-45 disabled:hover:bg-accent"
        >
          {isRunning ? "Ottimizzo…" : result !== null ? "Bilancia di nuovo" : "Bilancia"}
          {isRunning && (
            <span
              aria-hidden
              className="mx-loop absolute bottom-0 left-0 h-[3px] w-2/5 bg-ink opacity-35"
              style={{ animation: "mx-sweep 1.1s ease-in-out infinite" }}
            />
          )}
        </button>
      </div>

      {/* Due righe riservate anche quando ne basta una: l'esito arriva con
          stato e comandi, e se la striscia crescesse in quel momento tutta
          la pagina sotto scivolerebbe proprio mentre la si guarda. */}
      <div
        className="flex min-h-[52px] flex-wrap content-start items-center gap-x-2.5 gap-y-1.5 text-[12.5px]"
        aria-live="polite"
      >
        {isRunning && (
          <span className="font-mono text-accent-light">
            ottimizzazione multi-start in corso · il dosaggio si muoverà verso i target
          </span>
        )}
        {!solver.hasTarget && !isRunning && result === null && solver.error === null && (
          <span className="text-muted">Imposta almeno un target per bilanciare.</span>
        )}
        {result !== null && <Outcome result={result} />}
        {phase === "review" && (
          <span className="ml-auto flex gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="border-outline bg-surface-2 font-medium"
              onClick={solver.keep}
            >
              Mantieni
            </Button>
            <Button size="sm" variant="ghost" onClick={solver.revert}>
              Ripristina
            </Button>
          </span>
        )}
        {solver.error !== null && <span className="text-alert">{solver.error}</span>}
      </div>
    </form>
  );
}

/** Lo stato di convergenza detto per quello che significa per il drink:
    "convergente" con target mancati è un compromesso, non un successo. */
function Outcome({ result }: { result: SolverResult }) {
  const isUsable = USABLE_SOLVER_STATUSES.includes(result.status);
  const maxError = result.max_relative_error;

  if (!isUsable) {
    return (
      <>
        <Badge tone="alert">{SOLVER_STATUS_LABELS[result.status]}</Badge>
        <span className="basis-full leading-normal text-muted">
          {result.status === "INFEASIBLE"
            ? "Nessuna combinazione di volumi soddisfa i vincoli entro i limiti dei singoli ingredienti. Allenta il volume richiesto o aggiungi un ingrediente."
            : result.message}
        </span>
      </>
    );
  }

  const isOnTarget =
    result.status === "CONVERGED" && (maxError === null || maxError < TARGET_TOLERANCE);
  const label = isOnTarget
    ? SOLVER_STATUS_LABELS.CONVERGED
    : result.status === "MAX_ITERATIONS"
      ? SOLVER_STATUS_LABELS.MAX_ITERATIONS
      : "Compromesso: target non tutti raggiungibili";

  return (
    <>
      <Badge tone={isOnTarget ? "good" : "accent"}>{label}</Badge>
      <span className="tabular font-mono text-muted">
        {result.iterations} it
        {maxError !== null && ` · scarto max ${formatPercent(maxError)}`}
      </span>
    </>
  );
}
