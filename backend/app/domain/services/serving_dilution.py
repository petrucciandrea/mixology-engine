"""Diluizione dovuta al ghiaccio nel bicchiere di servizio.

Le curve di Arnold (`dilution.py`) descrivono la diluizione da
*preparazione*: ghiaccio scartato, drink filtrato. Il ghiaccio che resta nel
bicchiere continua a fondere, e per questo non esiste una regressione
pubblicata: il modello qui è un **bilancio termico a due nodi**, con le
ipotesi dichiarate nelle costanti (ADR-0012).

Il calore segue un percorso solo, ambiente → drink → ghiaccio:

- **Dal vetro al drink** entra `U·(T_a − T)`. Non è una potenza fissa: un
  drink più freddo ne richiama di più.
- **Dal drink al ghiaccio** passa `h·A·(T − T_f)`, dove `T_f` è il punto
  di congelamento della miscela *attuale* (all'interfaccia ghiaccio e
  soluzione coesistono lì) e `A` la superficie del ghiaccio, che cala con
  la fusione come `A₀·(m_ghiaccio/m₀)^(2/3)`: ogni pezzo si rimpicciolisce
  restando simile a se stesso. Quel calore fonde ghiaccio a 0 °C in acqua a
  `T_f`, al costo di `L − c_w·|T_f|` per grammo, e l'acqua si mescola al
  drink.

Per il drink: `C·dT/dt = U·(T_a − T) − h·A·(T − T_f) − ṁ·c_w·(T − T_f)`,
con `C = C₀ + m·c_w` che cresce con l'acqua di fusione. **Il tipo di
ghiaccio entra solo da `A`**, e il percorso unico ne fa vedere l'effetto
anche su un drink già freddo: a regime il calore del vetro deve
attraversare il ghiaccio, il drink si assesta a `U·(T_a − T)/(h·A)` sopra
`T_f`, e con poca superficie (un cubo grosso) resta più caldo e richiama
meno calore, quindi fonde meno. Un built, che parte a temperatura
ambiente, si raffredda con costante di tempo ~`C/(h·A)`: il tritato in
pochi secondi, il cubo grosso in un paio di minuti.

**Integrazione.** Su ogni passo i coefficienti si congelano e la
temperatura segue l'esponenziale esatto dell'equazione linearizzata: è
stabile per qualunque passo, anche quando `C/(h·A)` è di pochi secondi. La
fusione non si integra a parte: si ricava dalla conservazione
dell'entalpia, che con l'acqua liquida a 0 °C come riferimento vale

    (C₀ + m·c_w)·T + L·m = C₀·T_s + Q_amb

e così vale esattamente a ogni passo, invece di accumulare errore. I passi
stanno su una griglia fissa dall'istante del servizio: un campione della
curva e un profilo allo stesso minuto fanno gli stessi passi e coincidono.

**Il ghiaccio esaurito** smette di assorbire calore: il drink si scalda
verso l'ambiente attraverso il vetro, con `C·dT/dt = U·(T_a − T)`.

Limiti dichiarati: il ghiaccio di servizio è a 0 °C (ghiaccio da bar
"temperato") e non si raffredda fino a `T_f`; nessun ghiaccio si riforma
(la fusione non torna indietro); il ghiaccio sopra il livello del liquido
non scambia direttamente con l'aria; il punto di congelamento usa la legge
crioscopica ideale (accurata per le soluzioni da bar; oltre
`FREEZING_POINT_FLOOR_C` è fuori dal suo dominio e si satura).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ..balance import BalanceProfile, ServingProfile
from ..entities import Recipe
from ..enums import DilutionMethod, ServingIce
from ..errors import InvalidServingConditionsError
from ..serving_geometry import ICE_PIECES
from .balance_calculator import WATER_DENSITY_G_ML

#: Tempo di consumo assunto quando il chiamante non lo specifica, in minuti.
DEFAULT_CONSUMPTION_MINUTES = 10.0
MAX_CONSUMPTION_MINUTES = 60.0

# --- Proprietà fisiche (valori di letteratura) ---
LATENT_HEAT_FUSION_J_G = 334.0
CP_WATER_J_G_K = 4.18
CP_ETHANOL_J_G_K = 2.44
CP_SUGAR_J_G_K = 1.26
ETHANOL_DENSITY_G_ML = 0.789
ICE_DENSITY_G_ML = 0.917
#: Costante crioscopica dell'acqua, K·kg/mol.
CRYOSCOPIC_CONSTANT_K_KG_MOL = 1.86
ETHANOL_MOLAR_MASS_G_MOL = 46.07
#: Il Brix è espresso come saccarosio.
SUCROSE_MOLAR_MASS_G_MOL = 342.3
#: Oltre questa soluzione la legge crioscopica ideale non è più affidabile.
FREEZING_POINT_FLOOR_C = -40.0

# --- Ipotesi di servizio (non sono costanti fisiche: si tarano) ---
AMBIENT_TEMPERATURE_C = 20.0
#: Volume di ghiaccio per volume di drink, per il ghiaccio che riempie il
#: bicchiere (cubetti, tritato): un bicchiere ben pieno. Il pezzo unico
#: (cubo grosso, colonna) pesa quanto il pezzo, qualunque sia il drink.
ICE_VOLUME_PER_DRINK_VOLUME = 1.0
#: Coefficiente di scambio drink→ghiaccio, W/(m²·K), convezione naturale.
HEAT_TRANSFER_W_M2_K = 300.0
#: Conduttanza ambiente→drink attraverso il vetro, W/K: ~0.03 m² di
#: superficie bagnata per h ≈ 10 W/(m²·K). A 0 °C sono i 6 W del modello
#: precedente; un drink più freddo ne richiama di più.
GLASS_HEAT_TRANSFER_W_K = 0.3

#: Passo d'integrazione, in secondi. L'integratore è stabile per qualunque
#: passo; questo fissa l'accuratezza con cui coefficienti che cambiano (la
#: superficie che cala, il punto di congelamento che sale) sono seguiti.
INTEGRATION_STEP_S = 1.0

#: Tolleranza sul conteggio dei passi: `90.0 / 1.0` è 90 anche quando la
#: virgola mobile lo rappresenta come 89.999…
_STEP_TOLERANCE = 1e-9


def freezing_point_c(solute_mol: float, water_g: float) -> float:
    """T_f = −Kf · molalità, saturata a `FREEZING_POINT_FLOOR_C`."""
    if water_g <= 0.0:
        return FREEZING_POINT_FLOOR_C
    depression = CRYOSCOPIC_CONSTANT_K_KG_MOL * solute_mol / (water_g / 1000.0)
    return max(-depression, FREEZING_POINT_FLOOR_C)


@dataclass(frozen=True, slots=True)
class _DrinkOnIce:
    """Le grandezze che non cambiano durante il consumo."""

    balance: BalanceProfile
    #: Acqua del drink servito (acidi compresi), in grammi.
    water_g: float
    solute_mol: float
    #: Capacità termica del drink servito, C₀, in J/K.
    heat_capacity_j_k: float
    start_c: float
    ice_g: float
    ice_area_m2: float


@dataclass(frozen=True, slots=True)
class _State:
    temperature_c: float
    melt_g: float
    ambient_heat_j: float


def _drink_on_ice(recipe: Recipe, balance: BalanceProfile) -> _DrinkOnIce | None:
    if recipe.serving_ice is ServingIce.NONE:
        return None

    ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
    sugar_g = balance.sugar_mass_g
    # Gli acidi non pesano come soluto: nelle quantità da bar (< 1 % in
    # massa) il loro contributo crioscopico è sotto l'incertezza del modello.
    water_g = max(balance.final_mass_g - ethanol_g - sugar_g, 0.0)
    solute_mol = ethanol_g / ETHANOL_MOLAR_MASS_G_MOL + sugar_g / SUCROSE_MOLAR_MASS_G_MOL

    # Un drink shakerato o mescolato esce dalla preparazione all'equilibrio
    # con il proprio ghiaccio; un built nasce a temperatura ambiente.
    start_c = (
        AMBIENT_TEMPERATURE_C
        if recipe.dilution_method is DilutionMethod.BUILT
        else freezing_point_c(solute_mol, water_g)
    )

    piece = ICE_PIECES[recipe.serving_ice]
    ice_volume_ml = (
        piece.volume_ml
        if piece.is_single
        else ICE_VOLUME_PER_DRINK_VOLUME * balance.final_volume_ml
    )

    return _DrinkOnIce(
        balance=balance,
        water_g=water_g,
        solute_mol=solute_mol,
        heat_capacity_j_k=(
            ethanol_g * CP_ETHANOL_J_G_K + sugar_g * CP_SUGAR_J_G_K + water_g * CP_WATER_J_G_K
        ),
        start_c=start_c,
        ice_g=ice_volume_ml * ICE_DENSITY_G_ML,
        ice_area_m2=piece.specific_surface_m2_per_m3 * ice_volume_ml * 1e-6,
    )


def _step(drink: _DrinkOnIce, state: _State, seconds: float) -> _State:
    """Avanza di `seconds` con i coefficienti congelati all'inizio del passo."""
    temperature = state.temperature_c
    capacity = drink.heat_capacity_j_k + state.melt_g * CP_WATER_J_G_K
    ice_left_g = drink.ice_g - state.melt_g
    glass = GLASS_HEAT_TRANSFER_W_K

    if ice_left_g > 0.0:
        t_f = freezing_point_c(drink.solute_mol, drink.water_g + state.melt_g)
        area = drink.ice_area_m2 * (ice_left_g / drink.ice_g) ** (2.0 / 3.0)
        to_ice = HEAT_TRANSFER_W_M2_K * area
        # L'acqua di fusione entra a T_f e va portata alla temperatura del
        # drink: è una seconda conduttanza verso T_f, proporzionale alla
        # velocità di fusione.
        melt_rate = (
            to_ice
            * max(temperature - t_f, 0.0)
            / (LATENT_HEAT_FUSION_J_G - CP_WATER_J_G_K * abs(t_f))
        )
        to_melt = to_ice + melt_rate * CP_WATER_J_G_K
        conductance = glass + to_melt
        settles_at = (glass * AMBIENT_TEMPERATURE_C + to_melt * t_f) / conductance
    else:
        conductance = glass
        settles_at = AMBIENT_TEMPERATURE_C

    rate = conductance / capacity
    decay = math.exp(-rate * seconds)
    new_temperature = settles_at + (temperature - settles_at) * decay
    # ∫ U·(T_a − T) dt lungo lo stesso esponenziale, in forma chiusa.
    ambient_heat = state.ambient_heat_j + glass * (
        (AMBIENT_TEMPERATURE_C - settles_at) * seconds
        + (settles_at - temperature) * (1.0 - decay) / rate
    )

    enthalpy = drink.heat_capacity_j_k * drink.start_c + ambient_heat
    melt = (enthalpy - drink.heat_capacity_j_k * new_temperature) / (
        CP_WATER_J_G_K * new_temperature + LATENT_HEAT_FUSION_J_G
    )
    # La fusione non torna indietro e non supera il ghiaccio: se il passo
    # la spingerebbe fuori, la si ferma al limite e la temperatura si
    # ricava dalla stessa entalpia, che resta così conservata.
    bounded = min(max(melt, state.melt_g), drink.ice_g)
    if bounded != melt:
        melt = bounded
        new_temperature = (enthalpy - LATENT_HEAT_FUSION_J_G * melt) / (
            drink.heat_capacity_j_k + melt * CP_WATER_J_G_K
        )
    return _State(temperature_c=new_temperature, melt_g=melt, ambient_heat_j=ambient_heat)


def _simulate(drink: _DrinkOnIce, sample_seconds: Sequence[float]) -> list[_State]:
    """Lo stato del drink a ciascun istante richiesto, in ordine crescente.

    Si avanza sulla griglia fissa `k·INTEGRATION_STEP_S`; un istante che
    cade fra due nodi si raggiunge con un passo parziale che non diventa
    il punto di partenza dei successivi. Così il risultato in un istante
    non dipende da quali altri istanti si chiedono.
    """
    state = _State(temperature_c=drink.start_c, melt_g=0.0, ambient_heat_j=0.0)
    steps_done = 0
    samples = []
    for seconds in sample_seconds:
        whole_steps = math.floor(seconds / INTEGRATION_STEP_S + _STEP_TOLERANCE)
        while steps_done < whole_steps:
            state = _step(drink, state, INTEGRATION_STEP_S)
            steps_done += 1
        remainder = seconds - whole_steps * INTEGRATION_STEP_S
        samples.append(_step(drink, state, remainder) if remainder > _STEP_TOLERANCE else state)
    return samples


def _profile(drink: _DrinkOnIce, minutes: float, state: _State) -> ServingProfile:
    balance = drink.balance
    melt_g = state.melt_g
    melt_ml = melt_g / WATER_DENSITY_G_ML
    final_volume = balance.final_volume_ml + melt_ml
    final_mass = balance.final_mass_g + melt_g
    return ServingProfile(
        consumption_minutes=minutes,
        initial_temperature_c=drink.start_c,
        temperature_c=state.temperature_c,
        freezing_point_c=freezing_point_c(drink.solute_mol, drink.water_g + melt_g),
        ambient_heat_j=state.ambient_heat_j,
        melt_water_ml=melt_ml,
        ice_mass_g=drink.ice_g,
        # Il `max` assorbe solo l'arrotondamento: per costruzione la
        # fusione non supera il ghiaccio disponibile.
        remaining_ice_g=max(drink.ice_g - melt_g, 0.0),
        final_volume_ml=final_volume,
        final_mass_g=final_mass,
        total_dilution_factor=(final_volume - balance.total_volume_ml) / balance.total_volume_ml,
        abv=balance.pure_alcohol_ml / final_volume,
        brix=balance.sugar_mass_g / final_mass * 100.0,
        acidity=balance.acid_mass_g / final_volume * 100.0,
    )


def calculate_serving_profile(
    recipe: Recipe,
    balance: BalanceProfile,
    consumption_minutes: float = DEFAULT_CONSUMPTION_MINUTES,
) -> ServingProfile | None:
    """Il drink dopo `consumption_minutes` sul ghiaccio di servizio.

    Restituisce `None` per una ricetta servita senza ghiaccio: non c'è nulla
    da calcolare, e un profilo identico al `BalanceProfile` direbbe il falso
    ("diluizione da servizio: 0") invece di "non applicabile".
    """
    if not math.isfinite(consumption_minutes) or not (
        0.0 < consumption_minutes <= MAX_CONSUMPTION_MINUTES
    ):
        raise InvalidServingConditionsError(
            f"consumption_minutes must be within (0, {MAX_CONSUMPTION_MINUTES}], "
            f"got {consumption_minutes!r}"
        )
    drink = _drink_on_ice(recipe, balance)
    if drink is None:
        return None
    [state] = _simulate(drink, [consumption_minutes * 60.0])
    return _profile(drink, consumption_minutes, state)


def calculate_serving_curve(
    recipe: Recipe,
    balance: BalanceProfile,
    *,
    span_minutes: float,
    step_minutes: float,
) -> tuple[ServingProfile, ...] | None:
    """Il drink sul ghiaccio di servizio, campionato ogni `step_minutes`.

    Il primo punto è `t = 0`, il drink appena servito: senza di esso la
    curva partirebbe già diluita, e il tratto più ripido — quello di un
    built che si raffredda — mancherebbe proprio dove conta. `None`, come
    per il profilo singolo, se la ricetta è servita senza ghiaccio.
    """
    if not (math.isfinite(span_minutes) and math.isfinite(step_minutes)) or not (
        0.0 < step_minutes <= span_minutes <= MAX_CONSUMPTION_MINUTES
    ):
        raise InvalidServingConditionsError(
            f"the serving curve needs 0 < step <= span <= {MAX_CONSUMPTION_MINUTES} minutes, "
            f"got step={step_minutes!r}, span={span_minutes!r}"
        )
    drink = _drink_on_ice(recipe, balance)
    if drink is None:
        return None
    # La tolleranza evita di perdere l'ultimo campione quando `span / step`
    # è un intero che la virgola mobile rappresenta come 29.999…
    samples = math.floor(span_minutes / step_minutes + _STEP_TOLERANCE)
    minutes = [index * step_minutes for index in range(samples + 1)]
    states = _simulate(drink, [minute * 60.0 for minute in minutes])
    return tuple(
        _profile(drink, minute, state) for minute, state in zip(minutes, states, strict=True)
    )
