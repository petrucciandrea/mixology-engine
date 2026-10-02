"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";

/** Sotto questo scarto, in ml, il valore mostrato si aggancia al vero. */
const SNAP_ML = 0.03;

/** Un fotogramma lento (scheda in background) non deve far saltare la
    curva: oltre questo intervallo si avanza come se fosse passato questo. */
const MAX_FRAME_MS = 48;

/**
 * Volumi da disegnare che inseguono quelli veri.
 *
 * È solo rappresentazione: i numeri del drink arrivano dal backend sui
 * volumi veri, qui si decide come il bicchiere passa da uno stato al
 * successivo. Un avvicinamento esponenziale (non una durata fissa) regge
 * bene i cambi che arrivano mentre il precedente è ancora in corso, come
 * trascinare uno slider. Le chiavi nuove partono da zero — l'ingrediente
 * si versa — quelle tolte spariscono subito.
 */
export function useTweenedVolumes(
  target: Readonly<Record<string, number>>,
  timeConstantMs = 90,
): Record<string, number> {
  const reducedMotion = useReducedMotion();

  // Il chiamante costruisce l'oggetto a ogni render: l'effetto deve
  // ripartire quando cambiano i valori, non quando cambia l'identità.
  const signature = Object.entries(target)
    .map(([key, value]) => `${key}:${value}`)
    .join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableTarget = useMemo(() => target, [signature]);

  const [shown, setShown] = useState<Record<string, number>>(stableTarget);
  const shownRef = useRef(shown);

  useEffect(() => {
    if (reducedMotion) {
      shownRef.current = stableTarget;
      setShown(stableTarget);
      return;
    }

    let frame = 0;
    let last = 0;
    const step = (now: number) => {
      const elapsed = last === 0 ? 16 : Math.min(MAX_FRAME_MS, now - last);
      last = now;
      const pull = 1 - Math.exp(-elapsed / timeConstantMs);

      let moving = false;
      const next: Record<string, number> = {};
      for (const [key, goal] of Object.entries(stableTarget)) {
        const from = shownRef.current[key] ?? 0;
        const gap = goal - from;
        if (Math.abs(gap) < SNAP_ML) {
          next[key] = goal;
        } else {
          next[key] = from + gap * pull;
          moving = true;
        }
      }
      shownRef.current = next;
      setShown(next);
      if (moving) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [stableTarget, timeConstantMs, reducedMotion]);

  return shown;
}
