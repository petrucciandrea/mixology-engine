import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Compone classi Tailwind risolvendo i conflitti.
 *
 * `clsx` gestisce le classi condizionali, `tailwind-merge` decide chi vince
 * quando due classi toccano la stessa proprietà: senza, `cn("p-2", "p-4")`
 * lascerebbe entrambe nel DOM e il risultato dipenderebbe dall'ordine nel
 * foglio di stile, non da quello nel codice.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** ABV come si legge su un'etichetta: 0.1602 → "16.0%". */
export function formatAbv(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`;
}

/** Volumi al decimo di ml, senza decimali inutili: 60 → "60", 22.5 → "22.5". */
export function formatMl(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function formatBrix(value: number): string {
  return `${value.toFixed(1)}`;
}

export function formatAcidity(value: number): string {
  return `${value.toFixed(2)}%`;
}

/**
 * Il rapporto zuccheri/acidi non esiste quando non ci sono acidi: si mostra
 * un trattino, non uno zero o un infinito, perché il drink non si giudica
 * su quest'asse invece di giudicarlo male.
 */
export function formatRatio(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** Riporta un valore dentro un intervallo. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
