"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export type DockPanel = "book" | "pantry" | "match";

const PANELS: readonly DockPanel[] = ["book", "pantry", "match"];

const TITLES: Record<DockPanel, string> = {
  book: "Ricettario",
  pantry: "Dispensa",
  match: "Matcher",
};

const DRAWER_ID = "studio-drawer";

interface PanelDockProps {
  open: DockPanel | null;
  onOpenChange: (panel: DockPanel | null) => void;
  counts: Partial<Record<DockPanel, number>>;
  renderPanel: (panel: DockPanel) => ReactNode;
}

/**
 * Ricettario, dispensa e matcher in un cassetto, non in colonne fisse.
 *
 * Si consultano per scegliere — una ricetta da cui partire, un ingrediente
 * da aggiungere — e poi si torna al banco: tenerli sempre aperti ruberebbe
 * spazio al dosaggio e al bicchiere, che sono ciò che si guarda mentre si
 * lavora. Il cassetto si sovrappone alla colonna del dosaggio invece di
 * spingerla, così il bicchiere non si sposta mentre lo si apre.
 */
export function PanelDock({ open, onOpenChange, counts, renderPanel }: PanelDockProps) {
  const railRefs = useRef<Partial<Record<DockPanel, HTMLButtonElement | null>>>({});
  const drawerRef = useRef<HTMLElement>(null);

  // Il contenuto resta quello dell'ultimo pannello aperto anche mentre il
  // cassetto si chiude: svuotarlo subito lo farebbe sfumare vuoto.
  const [shown, setShown] = useState<DockPanel | null>(open);
  if (open !== null && open !== shown) setShown(open);

  useEffect(() => {
    if (open === null) {
      // Il cassetto diventa `inert` e il fuoco che conteneva si perde: si
      // riporta sul pulsante che l'aveva aperto, ma solo se nessun altro
      // elemento l'ha già preso (un clic sul banco non va scavalcato).
      const active = document.activeElement;
      const wasInside =
        active === null || active === document.body || drawerRef.current?.contains(active);
      if (shown !== null && wasInside) railRefs.current[shown]?.focus();
      return;
    }

    // All'apertura si va dove si scrive (la ricerca della dispensa), o
    // almeno dentro il cassetto, così la tastiera prosegue da lì.
    const field = drawerRef.current?.querySelector<HTMLElement>("input");
    (field ?? drawerRef.current)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
    // `shown` è letto solo per sapere dove tornare: non deve riattivare l'effetto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, onOpenChange]);

  return (
    <>
      <nav
        aria-label="Pannelli"
        className="flex gap-1.5 lg:col-span-2 xl:sticky xl:top-4 xl:col-span-1 xl:flex-col"
      >
        {PANELS.map((panel) => {
          const isOpen = open === panel;
          const count = counts[panel];
          return (
            <button
              key={panel}
              ref={(node) => {
                railRefs.current[panel] = node;
              }}
              type="button"
              aria-expanded={isOpen}
              aria-controls={DRAWER_ID}
              onClick={() => onOpenChange(isOpen ? null : panel)}
              className={cn(
                "h-9 flex-1 cursor-pointer rounded-[9px] border border-line px-3 text-[13px] font-medium tracking-[0.02em] transition-colors",
                // In scrittura verticale `px-*`/`py-*` (padding-inline/-block)
                // scambiano asse: il respiro lungo il testo va dato con i
                // padding fisici, che restano sopra/sotto/ai lati.
                "xl:h-auto xl:w-[52px] xl:flex-none xl:rotate-180 xl:p-0 xl:pb-4 xl:pt-4 xl:[writing-mode:vertical-rl]",
                isOpen
                  ? "bg-accent-soft text-accent-strong"
                  : "bg-transparent text-soft hover:bg-surface-2",
              )}
            >
              {TITLES[panel]}
              {count !== undefined && <span className="tabular"> · {count}</span>}
            </button>
          );
        })}
      </nav>

      <aside
        ref={drawerRef}
        id={DRAWER_ID}
        aria-label={shown === null ? undefined : TITLES[shown]}
        tabIndex={-1}
        inert={open === null}
        className={cn(
          "absolute left-0 top-11 z-10 w-full max-w-[370px] rounded-xl border border-drawer-line bg-drawer shadow-[0_24px_48px_-12px_rgba(0,0,0,.7)] outline-none",
          "transition-[opacity,transform] duration-200 ease-[cubic-bezier(.2,.8,.2,1)] xl:left-[68px] xl:top-0 xl:w-[370px]",
          open === null ? "pointer-events-none -translate-x-6 opacity-0" : "translate-x-0 opacity-100",
        )}
      >
        <div className="flex items-center justify-between border-b border-line py-2.5 pl-4 pr-2.5">
          <span className="font-mono text-[11.5px] font-medium uppercase tracking-[0.14em] text-title">
            {shown === null ? "" : TITLES[shown]}
          </span>
          <button
            type="button"
            onClick={() => onOpenChange(null)}
            aria-label="Chiudi"
            className="h-[30px] w-[30px] cursor-pointer rounded-md text-lg leading-none text-soft hover:bg-line"
          >
            ×
          </button>
        </div>
        <div className="scrollbar-slim max-h-[620px] overflow-y-auto p-2">
          {shown !== null && renderPanel(shown)}
        </div>
      </aside>
    </>
  );
}
