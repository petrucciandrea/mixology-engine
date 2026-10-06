"""Calcolo del profilo di bilanciamento di una ricetta.

Servizio di dominio puro: funzioni senza stato che trasformano una
`Recipe` in un `BalanceProfile`. Nessun I/O, nessuna dipendenza esterna,
nessuna libreria numerica — il che rende ogni singola formula
ispezionabile e testabile in isolamento, e permette al solver di
invocarlo migliaia di volte senza costi nascosti.

Riferimento: `docs/DOMAIN_MODEL_AND_MATH.md`, sezioni 2 e 3.

Nota sulle unità, che è la sorgente di errore più comune in questo
dominio: **ABV e acidità lavorano sui volumi, il Brix sulle masse**.
L'ABV è % vol e l'acidità è % p/v (grammi di acido ogni 100 ml, come la
dichiara l'etichetta di un succo): entrambi si sommano per volume, senza
densità. Il Brix è una concentrazione in percentuale di peso, quindi ogni
grandezza zuccherina passa per la densità prima di essere sommata.
Confondere gli assi produce risultati plausibili ma sbagliati del 3-20%,
cioè la differenza fra un drink equilibrato e uno no.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..balance import SUGAR_ACID_MIN_ACIDITY, BalanceProfile
from ..entities import Recipe, RecipeIngredient
from . import dilution

#: Densità dell'acqua di fusione del ghiaccio, in g/ml. Serve a convertire
#: in massa il volume d'acqua aggiunto, perché il Brix post-diluizione è un
#: rapporto di massa.
WATER_DENSITY_G_ML = 1.0


def total_volume_ml(items: Sequence[RecipeIngredient]) -> float:
    """V_tot = Σ V_i"""
    return sum(item.volume_ml for item in items)


def pure_alcohol_ml(items: Sequence[RecipeIngredient]) -> float:
    """V_alc = Σ (V_i · ABV_i)"""
    return sum(item.volume_ml * item.ingredient.physical_profile.abv for item in items)


def total_mass_g(items: Sequence[RecipeIngredient]) -> float:
    """M_tot = Σ (V_i · densità_i)"""
    return sum(item.volume_ml * item.ingredient.physical_profile.density_g_ml for item in items)


def sugar_mass_g(items: Sequence[RecipeIngredient]) -> float:
    """M_sugar = Σ (V_i · densità_i · Brix_i / 100)"""
    return sum(
        item.volume_ml
        * item.ingredient.physical_profile.density_g_ml
        * (item.ingredient.physical_profile.brix / 100.0)
        for item in items
    )


def acid_mass_g(items: Sequence[RecipeIngredient]) -> float:
    """M_acid = Σ (V_i · acidity_i / 100)

    Senza densità: l'acidità è già in g per 100 ml, quindi moltiplicarla per
    il volume dà direttamente i grammi. Passare per la densità (come per gli
    zuccheri) gonfierebbe di 3-5% l'acido dei succhi.
    """
    return sum(
        item.volume_ml * (item.ingredient.physical_profile.acidity / 100.0) for item in items
    )


def _ratio(numerator: float, denominator: float) -> float:
    """Divisione protetta: un denominatore nullo significa "grandezza assente"."""
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def sugar_acid_ratio(sugar_mass_g: float, acid_mass_g: float, acidity_pre: float) -> float | None:
    """Grammi di zucchero per grammo di acido, o `None` se non ha significato.

    `None` e non 0 o infinito: un drink senza acidi percepibili non ha un
    rapporto zuccheri/acidi *alto*, semplicemente non ne ha uno. Un Negroni
    non è "44 volte più dolce che acido", è un drink che non si giudica su
    quest'asse. La soglia è `SUGAR_ACID_MIN_ACIDITY` (% p/v): oltre a
    escludere le tracce, tiene lontana la divisione da denominatori
    denormali che la facevano traboccare (caso trovato da Hypothesis).

    È un quoziente di masse e non Brix/acidità: i due sono in basi diverse
    (% peso e % p/v), il loro rapporto dipenderebbe dalla densità del drink.
    """
    if acid_mass_g <= 0.0 or acidity_pre < SUGAR_ACID_MIN_ACIDITY:
        return None
    return sugar_mass_g / acid_mass_g


def calculate_balance(recipe: Recipe) -> BalanceProfile:
    """Profilo completo della ricetta, pre e post diluizione."""
    items = recipe.ingredients

    volume = total_volume_ml(items)
    alcohol = pure_alcohol_ml(items)
    mass = total_mass_g(items)
    sugar = sugar_mass_g(items)
    acid = acid_mass_g(items)

    abv_pre = _ratio(alcohol, volume)
    brix_pre = _ratio(sugar, mass) * 100.0
    acidity_pre = _ratio(acid, volume) * 100.0

    factor = dilution.dilution_factor(recipe.dilution_method, abv_pre)
    water_ml = volume * factor
    final_volume = volume + water_ml
    final_mass = mass + (water_ml * WATER_DENSITY_G_ML)

    return BalanceProfile(
        total_volume_ml=volume,
        pure_alcohol_ml=alcohol,
        total_mass_g=mass,
        sugar_mass_g=sugar,
        acid_mass_g=acid,
        abv_pre=abv_pre,
        brix_pre=brix_pre,
        acidity_pre=acidity_pre,
        sugar_acid_ratio=sugar_acid_ratio(sugar, acid, acidity_pre),
        dilution_factor=factor,
        dilution_water_ml=water_ml,
        final_volume_ml=final_volume,
        final_mass_g=final_mass,
        abv_post=_ratio(alcohol, final_volume),
        brix_post=_ratio(sugar, final_mass) * 100.0,
        acidity_post=_ratio(acid, final_volume) * 100.0,
    )
