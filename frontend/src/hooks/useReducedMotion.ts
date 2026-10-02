"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/**
 * Preferenza di sistema per il movimento ridotto.
 *
 * Le animazioni CSS si spengono già dal foglio di stile globale; questa
 * serve a quelle guidate da `requestAnimationFrame`, che il CSS non vede.
 * Sul server vale `false`: il primo disegno è comunque statico.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
