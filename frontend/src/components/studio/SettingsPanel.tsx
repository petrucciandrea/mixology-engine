"use client";

import { cn } from "@/lib/utils";
import {
  GLASS_LABELS,
  GLASS_TYPES,
  type Glassware,
  type GlasswareCatalogue,
} from "@/types/api";

interface SettingsPanelProps {
  /** `null` finché i cataloghi non arrivano (o se non arrivano). */
  catalogues: readonly GlasswareCatalogue[] | null;
  /** Il catalogo delle bozze nuove, dalle impostazioni. */
  preferred: Glassware;
  /** Il catalogo della ricetta sul banco: può differire, se si è aperta
      una ricetta salvata con un'altra linea. */
  current: Glassware;
  onSelect: (glassware: Glassware) => void;
}

/**
 * Le impostazioni dello studio: per ora, la linea di bicchieri.
 *
 * Scegliere un catalogo lo applica subito alla ricetta sul banco e alle
 * bozze nuove. Le ricette salvate restano con il loro: il catalogo è un
 * dato della ricetta, e i suoi calcoli non devono cambiare alle spalle di
 * chi l'ha bilanciata.
 */
export function SettingsPanel({ catalogues, preferred, current, onSelect }: SettingsPanelProps) {
  if (catalogues === null) {
    return <p className="px-2 py-6 text-center text-sm text-muted">Carico i cataloghi…</p>;
  }

  return (
    <div className="flex flex-col gap-2 p-1">
      <h2 className="px-1.5 pt-1 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
        Linea di bicchieri
      </h2>
      <div role="radiogroup" aria-label="Linea di bicchieri" className="flex flex-col gap-1">
        {catalogues.map((catalogue) => {
          const isOn = catalogue.glassware === preferred;
          const made = new Set(catalogue.glasses.map((model) => model.glass));
          const missing = GLASS_TYPES.filter((glass) => glass !== "OTHER" && !made.has(glass));
          return (
            <button
              key={catalogue.glassware}
              type="button"
              role="radio"
              aria-checked={isOn}
              onClick={() => onSelect(catalogue.glassware)}
              className={cn(
                "flex cursor-pointer flex-col gap-1 rounded-lg border px-3 py-2.5 text-left transition-colors",
                isOn
                  ? "border-accent-line bg-accent-soft"
                  : "border-transparent hover:bg-hover",
              )}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className={cn("text-sm", isOn && "font-semibold text-accent-strong")}>
                  {catalogue.name}
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {catalogue.glasses.length} bicchieri
                </span>
              </span>
              {catalogue.maker !== "—" && (
                <span className="text-xs text-soft">{catalogue.maker}</span>
              )}
              <span className="text-[12.5px] leading-snug text-muted">{catalogue.description}</span>
              {missing.length > 0 && (
                <span className="text-xs text-muted">
                  Non produce: {missing.map((glass) => GLASS_LABELS[glass]).join(", ")}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {current !== preferred && (
        <p className="px-1.5 text-xs text-soft">
          La ricetta aperta usa un&apos;altra linea: sceglierne una qui la cambia anche per
          lei.
        </p>
      )}

      <p className="px-1.5 pb-1 text-xs leading-normal text-muted">
        Misure dalle schede dei distributori (capienza, altezza, diametro). La profondità della
        coppa si ricava dalla capienza dichiarata; le linee di marca includono solo i bicchieri
        che producono davvero.
      </p>
    </div>
  );
}
