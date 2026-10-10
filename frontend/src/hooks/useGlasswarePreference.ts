"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DEFAULT_GLASSWARE, type Glassware } from "@/types/api";

const STORAGE_KEY = "mixology.glassware";
const KNOWN: readonly Glassware[] = ["GENERIC", "LUIGI_BORMIOLI", "SCHOTT_ZWIESEL", "NUDE"];

/**
 * Il catalogo di bicchieri con cui si aprono le bozze nuove.
 *
 * È una comodità di chi usa lo studio, non un dato della ricetta (quello
 * la ricetta lo salva da sé): resta nel browser. Si legge dopo il primo
 * render, perché sul server non c'è `localStorage` e un valore diverso al
 * primo disegno romperebbe l'idratazione. Lettura e scrittura possono
 * fallire (navigazione privata, dati bloccati): in quel caso vale il
 * generico, e lo studio funziona lo stesso.
 *
 * `onRestore` riceve la preferenza letta all'avvio, una volta sola: è il
 * momento in cui la bozza iniziale, ancora vuota, deve adottarla.
 */
export function useGlasswarePreference(
  onRestore: (glassware: Glassware) => void,
): [Glassware, (next: Glassware) => void] {
  const [glassware, setGlassware] = useState<Glassware>(DEFAULT_GLASSWARE);
  const restore = useRef(onRestore);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored !== null && (KNOWN as readonly string[]).includes(stored)) {
        setGlassware(stored as Glassware);
        restore.current(stored as Glassware);
      }
    } catch {
      // Nessuna preferenza leggibile: resta il generico.
    }
  }, []);

  const choose = useCallback((next: Glassware) => {
    setGlassware(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Non memorizzata: varrà solo per questa sessione.
    }
  }, []);

  return [glassware, choose];
}
