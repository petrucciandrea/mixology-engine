"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface SegmentedOption<T> {
  value: T;
  label: React.ReactNode;
  /** Obbligatorio quando `label` non è testo, come per le icone. */
  ariaLabel?: string;
  title?: string;
  /** Visibile ma non selezionabile: le frecce la saltano. */
  disabled?: boolean;
  /** Classi della singola opzione, oltre a `optionClassName`. */
  className?: string;
}

interface SegmentedProps<T> {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
  optionClassName?: string;
}

/**
 * Scelta esclusiva fra poche opzioni sempre visibili.
 *
 * È un `radiogroup` vero, con il comportamento da tastiera che ci si
 * aspetta: un solo punto di tabulazione per gruppo, frecce per scorrere
 * (e selezionare) le opzioni, Home/End per gli estremi. Una fila di bottoni
 * con `aria-pressed` costringerebbe a tabulare su ognuno dei sedici
 * bicchieri per arrivare al dosaggio.
 *
 * Un'opzione `disabled` resta al suo posto, perché sparire farebbe saltare
 * la griglia e nasconderebbe che la scelta esiste: è solo non disponibile
 * in questo momento.
 */
export function Segmented<T>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
  optionClassName,
}: SegmentedProps<T>) {
  const refs = React.useRef<(HTMLButtonElement | null)[]>([]);
  const selected = options.findIndex((option) => Object.is(option.value, value));
  // Senza selezione il gruppo deve comunque essere raggiungibile, e mai
  // da un'opzione che non si può scegliere.
  const tabStop =
    selected !== -1 && !options[selected]!.disabled
      ? selected
      : Math.max(0, options.findIndex((option) => !option.disabled));

  /** La prima opzione abilitata da `start` in direzione `step`, con giro. */
  function nextEnabled(start: number, step: 1 | -1): number | null {
    for (let k = 0; k < options.length; k++) {
      const index = (start + step * k + options.length * 2) % options.length;
      if (!options[index]!.disabled) return index;
    }
    return null;
  }

  function move(event: React.KeyboardEvent, from: number) {
    const last = options.length - 1;
    const target =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? nextEnabled(from + 1, 1)
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? nextEnabled(from - 1, -1)
          : event.key === "Home"
            ? nextEnabled(0, 1)
            : event.key === "End"
              ? nextEnabled(last, -1)
              : null;
    if (target === null) return;
    event.preventDefault();
    onChange(options[target]!.value);
    refs.current[target]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={ariaLabel} className={className}>
      {options.map((option, index) => {
        const isOn = index === selected;
        return (
          <button
            key={index}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={isOn}
            aria-label={option.ariaLabel}
            title={option.title}
            aria-disabled={option.disabled || undefined}
            disabled={option.disabled}
            tabIndex={index === tabStop ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => move(event, index)}
            className={cn(
              "border transition-colors",
              option.disabled
                ? "cursor-not-allowed border-transparent text-muted opacity-45"
                : "cursor-pointer",
              !option.disabled &&
                (isOn
                  ? "border-accent-line bg-accent-soft text-accent-strong"
                  : "border-transparent text-soft hover:bg-surface-2"),
              optionClassName,
              option.className,
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
