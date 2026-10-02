import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Non tutto è una card: bordo e sfondo dicono "oggetto separato", e
 * spenderli su ogni blocco appiattisce la gerarchia invece di costruirla.
 * Qui delimitano i pannelli dello strumento, che sono davvero unità
 * indipendenti — si leggono e si usano una alla volta.
 */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn("min-w-0 rounded-xl border border-line bg-surface", className)}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-b border-line-soft px-4 py-3",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn(
        "font-mono text-[11.5px] font-medium uppercase leading-none tracking-[0.14em] text-title",
        className,
      )}
      {...props}
    />
  );
}

/** Nota di intestazione: l'unità o il totale che dà contesto al titolo. */
export function CardMeta({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("tabular font-mono text-[12.5px] text-muted", className)}
      {...props}
    />
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3.5", className)} {...props} />;
}
