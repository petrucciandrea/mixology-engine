"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface SegmentedOption<T> {
  value: T;
  label: React.ReactNode;
  /** Obbligatorio quando `label` non è testo, come per le icone. */
  ariaLabel?: string;
  title?: string;
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
  // Senza selezione il gruppo deve comunque essere raggiungibile.
  const tabStop = selected === -1 ? 0 : selected;

  function move(event: React.KeyboardEvent, from: number) {
    const last = options.length - 1;
    const target =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? from === last
          ? 0
          : from + 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? from === 0
            ? last
            : from - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
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
            tabIndex={index === tabStop ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => move(event, index)}
            className={cn(
              "cursor-pointer border transition-colors",
              isOn
                ? "border-accent-line bg-accent-soft text-accent-strong"
                : "border-transparent text-soft hover:bg-surface-2",
              optionClassName,
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
