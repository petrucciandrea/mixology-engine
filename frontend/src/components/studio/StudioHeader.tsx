"use client";

import { Button } from "@/components/ui/button";

interface StudioHeaderProps {
  name: string;
  onNameChange: (name: string) => void;
  /** La bozza deriva da una ricetta salvata: "Salva" la aggiorna. */
  isStored: boolean;
  canSave: boolean;
  onSave: (asNew: boolean) => void;
  onReset: () => void;
}

export function StudioHeader({
  name,
  onNameChange,
  isStored,
  canSave,
  onSave,
  onReset,
}: StudioHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-baseline gap-3.5">
        <span className="font-mono text-[11px] font-medium uppercase leading-none tracking-[0.18em] text-accent">
          Mixology Engine
        </span>
        <h1 className="font-display text-2xl leading-tight">Studio di bilanciamento</h1>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2.5">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
            Nome della ricetta
          </span>
          <input
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            className="h-9 w-[220px] rounded-[7px] border border-line bg-surface-2 px-3 text-sm focus:border-accent focus:outline-none"
          />
        </label>
        <Button disabled={!canSave} onClick={() => onSave(false)}>
          {isStored ? "Aggiorna" : "Salva"}
        </Button>
        {isStored && (
          <Button variant="outline" disabled={!canSave} onClick={() => onSave(true)}>
            Salva come nuova
          </Button>
        )}
        <Button variant="ghost" className="px-3" onClick={onReset}>
          Nuova
        </Button>
      </div>
    </header>
  );
}
