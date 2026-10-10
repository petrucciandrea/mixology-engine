"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CommandStrip } from "@/components/studio/CommandStrip";
import { DilutionCurve } from "@/components/studio/DilutionCurve";
import { DosePanel } from "@/components/studio/DosePanel";
import { FlavorBars } from "@/components/studio/FlavorBars";
import { GlassStage } from "@/components/studio/GlassStage";
import { MatcherPanel } from "@/components/studio/MatcherPanel";
import { PanelDock, type DockPanel } from "@/components/studio/PanelDock";
import { PantryPanel } from "@/components/studio/PantryPanel";
import { RecipeBookPanel } from "@/components/studio/RecipeBookPanel";
import { SettingsPanel } from "@/components/studio/SettingsPanel";
import { StudioHeader } from "@/components/studio/StudioHeader";
import { useGlasswarePreference } from "@/hooks/useGlasswarePreference";
import { useRecipe } from "@/hooks/useRecipe";
import { useRecipeBook } from "@/hooks/useRecipeBook";
import { useSolver } from "@/hooks/useSolver";
import { ApiError, listGlassware, listIngredients } from "@/lib/api";
import {
  allowedIce,
  fallbackIce,
  isGlassAvailable,
  modelFor,
  toIndex,
  type GlasswareIndex,
} from "@/lib/serving";
import type {
  DilutionMethod,
  GlassType,
  Glassware,
  GlasswareCatalogue,
  Ingredient,
  Recipe,
  ServingIce,
} from "@/types/api";

export default function StudioPage() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [pantryError, setPantryError] = useState<string | null>(null);
  const [isLoadingPantry, setIsLoadingPantry] = useState(true);
  const [panel, setPanel] = useState<DockPanel | null>(null);
  /** Il minuto scelto sulla curva di servizio: 0 = appena servito. */
  const [minutes, setMinutes] = useState(0);

  const recipe = useRecipe("Ricetta senza nome");
  const book = useRecipeBook();
  const solver = useSolver({
    recipeInput: recipe.recipeInput,
    doses: recipe.doses,
    onApply: recipe.applyVolumes,
  });

  // I cataloghi di bicchieri danno misure, sagome e ghiacci ammessi. Se
  // non arrivano non si blocca nulla: l'editor resta usabile, il bicchiere
  // si disegna stilizzato, e una coppia impossibile la rifiuta il backend
  // con un errore leggibile.
  const [catalogues, setCatalogues] = useState<GlasswareCatalogue[] | null>(null);
  const index = useMemo<GlasswareIndex | null>(
    () => (catalogues === null ? null : toIndex(catalogues)),
    [catalogues],
  );
  useEffect(() => {
    listGlassware()
      .then(setCatalogues)
      .catch(() => setCatalogues(null));
  }, []);
  // La bozza iniziale è vuota: adotta la linea salvata nelle impostazioni
  // appena il browser la restituisce.
  const [preferredGlassware, setPreferredGlassware] = useGlasswarePreference(
    recipe.setGlassware,
  );

  useEffect(() => {
    listIngredients({ limit: 200 })
      .then((page) => setIngredients(page.items))
      .catch((cause: unknown) => {
        setPantryError(
          cause instanceof ApiError ? cause.message : "Impossibile caricare la dispensa",
        );
      })
      .finally(() => setIsLoadingPantry(false));
  }, []);

  const selectedIds = useMemo(
    () => new Set(recipe.doses.map((dose) => dose.ingredient.id)),
    [recipe.doses],
  );

  // Ogni modifica che cambia il problema da ottimizzare passa di qui: il
  // solver deve sapere che un esito in corso o in revisione non descrive
  // più la ricetta sul banco. Nome e famiglia non entrano nel calcolo.
  const { invalidate, clear } = solver;
  const {
    setVolume,
    addIngredient,
    removeIngredient,
    setMethod,
    setServingIce,
    setGlass,
    setGlassware,
  } = recipe;

  const editVolume = useCallback(
    (ingredientId: string, volumeMl: number) => {
      invalidate();
      setVolume(ingredientId, volumeMl);
    },
    [invalidate, setVolume],
  );
  const addToRecipe = useCallback(
    (ingredient: Ingredient) => {
      invalidate();
      addIngredient(ingredient);
      setPanel(null);
    },
    [invalidate, addIngredient],
  );
  const removeFromRecipe = useCallback(
    (ingredientId: string) => {
      invalidate();
      removeIngredient(ingredientId);
    },
    [invalidate, removeIngredient],
  );
  const changeMethod = useCallback(
    (method: DilutionMethod) => {
      invalidate();
      setMethod(method);
    },
    [invalidate, setMethod],
  );
  const changeServingIce = useCallback(
    (ice: ServingIce) => {
      invalidate();
      setServingIce(ice);
    },
    [invalidate, setServingIce],
  );
  // Cambiare bicchiere può lasciare un ghiaccio che non ci entra (il cubo
  // grosso passando al Collins): lo si sostituisce subito, invece di
  // mandare al backend una ricetta che rifiuterebbe.
  const currentIce = recipe.servingIce;
  const currentGlass = recipe.glass;
  const currentGlassware = recipe.glassware;
  const changeGlass = useCallback(
    (glass: GlassType | null) => {
      invalidate();
      const allowed = allowedIce(index, currentGlassware, glass);
      if (!allowed.includes(currentIce)) setServingIce(fallbackIce(allowed));
      setGlass(glass);
    },
    [invalidate, setGlass, setServingIce, index, currentGlassware, currentIce],
  );
  // Cambiare linea può togliere il bicchiere (Schott Zwiesel non fa tiki)
  // o restringerne le misure (il cubo grosso non entra più): si sistema
  // la bozza subito, con gli stessi ripieghi del cambio di bicchiere.
  const changeGlassware = useCallback(
    (glassware: Glassware) => {
      invalidate();
      setGlassware(glassware);
      if (currentGlass !== null && !isGlassAvailable(index, glassware, currentGlass)) {
        setGlass(null);
        return;
      }
      const allowed = allowedIce(index, glassware, currentGlass);
      if (!allowed.includes(currentIce)) setServingIce(fallbackIce(allowed));
    },
    [invalidate, setGlassware, setGlass, setServingIce, index, currentGlass, currentIce],
  );


  function selectGlassware(glassware: Glassware) {
    setPreferredGlassware(glassware);
    changeGlassware(glassware);
  }

  function loadRecipe(target: Recipe) {
    clear();
    recipe.loadRecipe(target);
    setMinutes(0);
    setPanel(null);
  }

  function resetRecipe() {
    clear();
    recipe.reset(preferredGlassware);
    setMinutes(0);
  }

  const glassModel = modelFor(index, recipe.glassware, recipe.glass);

  // Il nome vuoto lo rifiuterebbe comunque il dominio: disabilitare il
  // pulsante evita un giro al backend solo per sentirselo dire.
  const canSave = recipe.recipeInput !== null && recipe.name.trim() !== "" && !book.isSaving;

  async function saveRecipe(asNew: boolean) {
    if (recipe.recipeInput === null) return;
    const saved = await book.save(recipe.recipeInput, asNew ? null : recipe.recipeId);
    if (saved !== null) recipe.markSaved(saved);
  }

  async function deleteRecipe(target: Recipe) {
    // La cancellazione non si annulla: una conferma costa un clic, una
    // ricetta persa costa il lavoro di bilanciarla di nuovo.
    if (!window.confirm(`Cancellare «${target.name}» dal ricettario?`)) return;
    const deleted = await book.remove(target.id);
    if (deleted && target.id === recipe.recipeId) recipe.forgetRecipeId();
  }

  // Il minuto scelto vale finché la curva lo contiene; senza ghiaccio non
  // c'è un "dopo" da mostrare e il bicchiere torna al drink appena servito.
  const curve = recipe.servingCurve;
  const moment =
    curve !== null && minutes > 0
      ? (curve.find((point) => point.consumption_minutes === minutes) ?? null)
      : null;

  // Con il backend spento dispensa e ricettario falliscono con lo stesso
  // messaggio: si mostra una volta sola, con la chiave della sua fonte.
  const errors = (
    [
      ["pantry", pantryError],
      ["book", book.error],
      ["recipe", recipe.error],
    ] as const
  ).filter(
    ([, message], index, all): boolean =>
      message !== null && all.findIndex(([, other]) => other === message) === index,
  );

  return (
    <div className="tabular mx-auto flex min-h-screen max-w-[1500px] flex-col gap-4 px-4 pb-7 pt-5 lg:px-6">
      <StudioHeader
        name={recipe.name}
        onNameChange={recipe.setName}
        isStored={recipe.recipeId !== null}
        canSave={canSave}
        onSave={(asNew) => void saveRecipe(asNew)}
        onReset={resetRecipe}
      />

      {errors.map(([source, message]) => (
        <p
          key={source}
          role="alert"
          className="rounded-lg border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert"
        >
          {message}
          {source === "pantry" && (
            <>
              . Verifica che lo stack sia avviato (<code>make up</code>) e che la dispensa sia
              popolata (<code>make seed</code>).
            </>
          )}
        </p>
      ))}

      <CommandStrip
        profile={recipe.profile}
        glassFit={recipe.glassFit}
        isCalculating={recipe.isCalculating}
        solver={solver}
      />

      {/* Quattro colonne nell'ordine in cui si lavora: si sceglie dal
          cassetto, si dosa, si guarda il bicchiere, si legge cosa succede
          nel tempo e nel sapore. Sotto i 1280px le ultime due si
          affiancano sotto le prime, sotto i 1024px tutto va in colonna. */}
      <main className="relative grid grid-cols-1 items-start gap-4 lg:grid-cols-2 xl:grid-cols-[52px_minmax(340px,410px)_minmax(340px,1fr)_minmax(320px,380px)]">
        <PanelDock
          open={panel}
          onOpenChange={setPanel}
          counts={{ book: book.recipes.length, pantry: ingredients.length }}
          renderPanel={(open) =>
            open === "book" ? (
              <RecipeBookPanel
                recipes={book.recipes}
                activeId={recipe.recipeId}
                isLoading={book.isLoading}
                onLoad={loadRecipe}
                onDelete={(target) => void deleteRecipe(target)}
              />
            ) : open === "settings" ? (
              <SettingsPanel
                catalogues={catalogues}
                preferred={preferredGlassware}
                current={recipe.glassware}
                onSelect={selectGlassware}
              />
            ) : open === "pantry" ? (
              <PantryPanel
                ingredients={ingredients}
                selectedIds={selectedIds}
                onAdd={addToRecipe}
                isLoading={isLoadingPantry}
              />
            ) : (
              <MatcherPanel doses={recipe.doses} onAdd={addToRecipe} />
            )
          }
        />

        <DosePanel
          doses={recipe.doses}
          method={recipe.method}
          servingIce={recipe.servingIce}
          allowedIce={allowedIce(index, recipe.glassware, recipe.glass)}
          glass={recipe.glass}
          glassModel={glassModel}
          catalogueName={index?.get(recipe.glassware)?.catalogue.name ?? "questo catalogo"}
          isGlassAvailable={(glass) => isGlassAvailable(index, recipe.glassware, glass)}
          family={recipe.family}
          glassFit={recipe.glassFit}
          onMethodChange={changeMethod}
          onServingIceChange={changeServingIce}
          onGlassChange={changeGlass}
          onFamilyChange={recipe.setFamily}
          onVolumeChange={editVolume}
          onRemove={removeFromRecipe}
          onOpenPantry={() => setPanel("pantry")}
        />

        <GlassStage
          doses={recipe.doses}
          profile={recipe.profile}
          glass={recipe.glass}
          model={glassModel}
          glassFit={recipe.glassFit}
          servingIce={recipe.servingIce}
          family={recipe.family}
          moment={moment}
        />

        <div className="grid min-w-0 items-start gap-4 lg:col-span-2 lg:grid-cols-2 xl:col-span-1 xl:grid-cols-1">
          <DilutionCurve
            curve={curve}
            reference={recipe.servingProfile}
            minutes={minutes}
            onMinutesChange={setMinutes}
            hasDoses={recipe.doses.length > 0}
          />
          <FlavorBars
            doses={recipe.doses}
            before={solver.result !== null ? solver.before : null}
          />
        </div>
      </main>
    </div>
  );
}
