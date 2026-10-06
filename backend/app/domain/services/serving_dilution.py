"""Diluizione dovuta al ghiaccio nel bicchiere di servizio.

Le curve di Arnold (`dilution.py`) descrivono la diluizione da
*preparazione*: ghiaccio scartato, drink filtrato. Il ghiaccio che resta nel
bicchiere continua a fondere, e per questo non esiste una regressione
pubblicata: il modello qui è un **bilancio termico**, con le ipotesi
dichiarate nelle costanti.

Due contributi si sommano:

1. **Raffreddamento fino all'equilibrio.** Il drink parte da una temperatura
   `T_s` e il ghiaccio a 0 °C lo porta al punto di congelamento della
   miscela `T_f`. Il calore ceduto dal drink fonde ghiaccio, e l'acqua di
   fusione, raffreddandosi da 0 a `T_f`, restituisce calore:

       m · (L − c_w·|T_f|) = M · c_p · (T_s − T_f)

   `T_f` dipende a sua volta dall'acqua aggiunta `m` (la diluizione alza il
   punto di congelamento), quindi `m` si trova per bisezione. Per un
   drink già raffreddato in preparazione (shaken, stirred) `T_s = T_f` e
   questo termine è nullo; per un built, che parte a temperatura ambiente,
   è quello dominante.
2. **Calore dall'ambiente.** Un flusso costante `P` attraverso il vetro
   fonde `P·t / L` di ghiaccio nel tempo `t` di consumo.

**Il tipo di ghiaccio agisce sulla velocità del primo termine**, non sul suo
valore di equilibrio: la superficie di scambio è `S/V · V_ghiaccio`, e la
costante di tempo del raffreddamento è `τ = M·c_p / (h·A)`, quindi il
termine di raffreddamento realizzato in `t` è `m_eq · (1 − e^(−t/τ))`.
Il ghiaccio tritato, con molta superficie, raggiunge l'equilibrio in
pochi secondi; un cubo grosso ci mette di più. Su tempi di consumo lunghi
la differenza fra i tipi si riduce: è una conseguenza del modello, non un
difetto.

**La temperatura** discende dalle stesse due ipotesi. Il modello a capacità
concentrata che dà `m_eq · (1 − e^(−t/τ))` fa decadere lo scarto
dall'equilibrio con la stessa costante di tempo, e l'equilibrio intanto si
sposta, perché l'acqua di fusione ambiente diluisce la miscela e ne alza il
punto di congelamento:

    T(t) = T_f(m_w + m_eq + m_amb(t)) + (T_s − T_eq) · e^(−t/τ)

A `t = 0` vale `T_s`. Per un drink già raffreddato (shaken, stirred) il
transitorio è nullo e resta la deriva: il drink si scalda lentamente pur
stando sul ghiaccio, di quanto la diluizione gli concede.

Limiti dichiarati: la superficie del ghiaccio non si riduce mentre fonde, il
ghiaccio di servizio è a 0 °C (ghiaccio da bar "temperato"), il punto di
congelamento usa la legge crioscopica ideale (accurata per le soluzioni da
bar; oltre `FREEZING_POINT_FLOOR_C` è fuori dal suo dominio e si satura).
Esaurito il ghiaccio, la temperatura resta quella dell'ultimo equilibrio: il
riscaldamento del drink verso l'ambiente non è modellato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..balance import BalanceProfile, ServingProfile
from ..entities import Recipe
from ..enums import DilutionMethod, ServingIce
from ..errors import InvalidServingConditionsError
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
#: Volume di ghiaccio per volume di drink: un bicchiere ben pieno.
ICE_VOLUME_PER_DRINK_VOLUME = 1.0
#: Coefficiente di scambio drink→ghiaccio, W/(m²·K), convezione naturale.
HEAT_TRANSFER_W_M2_K = 300.0
#: Calore che entra dall'ambiente attraverso il vetro, in W (~0.03 m² di
#: superficie, h ≈ 10 W/m²K, ΔT ≈ 20 K).
AMBIENT_HEAT_GAIN_W = 6.0

#: Superficie specifica S/V, m²/m³, per un solido di dimensione
#: caratteristica `a`: 6/a. Cubetti da 25 mm, cubo grosso da 50 mm,
#: tritato con frammenti equivalenti a ~6 mm.
SPECIFIC_SURFACE_M2_PER_M3: dict[ServingIce, float] = {
    ServingIce.CUBES: 6.0 / 0.025,
    ServingIce.LARGE_CUBE: 6.0 / 0.050,
    ServingIce.CRUSHED: 6.0 / 0.006,
}

_BISECTION_STEPS = 60


def freezing_point_c(solute_mol: float, water_g: float) -> float:
    """T_f = −Kf · molalità, saturata a `FREEZING_POINT_FLOOR_C`."""
    if water_g <= 0.0:
        return FREEZING_POINT_FLOOR_C
    depression = CRYOSCOPIC_CONSTANT_K_KG_MOL * solute_mol / (water_g / 1000.0)
    return max(-depression, FREEZING_POINT_FLOOR_C)


def _specific_heat(ethanol_g: float, sugar_g: float, water_g: float) -> float:
    """c_p della miscela, media pesata sulle masse, J/(g·K)."""
    total = ethanol_g + sugar_g + water_g
    return (
        ethanol_g * CP_ETHANOL_J_G_K + sugar_g * CP_SUGAR_J_G_K + water_g * CP_WATER_J_G_K
    ) / total


def _equilibrium_melt_g(
    *,
    drink_mass_g: float,
    cp: float,
    start_temperature_c: float,
    solute_mol: float,
    water_g: float,
    ice_available_g: float,
) -> float:
    """Acqua di fusione che porta il drink all'equilibrio, in grammi."""

    def imbalance(melt_g: float) -> float:
        t_final = freezing_point_c(solute_mol, water_g + melt_g)
        released = drink_mass_g * cp * (start_temperature_c - t_final)
        absorbed = melt_g * (LATENT_HEAT_FUSION_J_G - CP_WATER_J_G_K * abs(t_final))
        return absorbed - released

    if imbalance(0.0) >= 0.0:
        return 0.0
    if imbalance(ice_available_g) < 0.0:
        return ice_available_g

    low, high = 0.0, ice_available_g
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        if imbalance(middle) < 0.0:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


@dataclass(frozen=True, slots=True)
class _ServingModel:
    """Le grandezze del bilancio che non dipendono dal tempo di consumo.

    Separate dal campionamento perché una curva interroga lo stesso drink
    decine di volte: l'equilibrio, che richiede la bisezione, si risolve
    una volta sola.
    """

    balance: BalanceProfile
    water_g: float
    solute_mol: float
    start_c: float
    equilibrium_c: float
    equilibrium_melt_g: float
    ice_g: float
    time_constant_s: float

    def at(self, minutes: float) -> ServingProfile:
        balance = self.balance
        seconds = minutes * 60.0
        decay = math.exp(-seconds / self.time_constant_s)
        cooling_melt_g = self.equilibrium_melt_g * (1.0 - decay)

        ambient_melt_g = AMBIENT_HEAT_GAIN_W * seconds / LATENT_HEAT_FUSION_J_G
        # Non può fondere più ghiaccio di quanto ce ne sia nel bicchiere.
        ambient_melt_g = min(ambient_melt_g, max(self.ice_g - cooling_melt_g, 0.0))

        melt_g = cooling_melt_g + ambient_melt_g
        melt_ml = melt_g / WATER_DENSITY_G_ML
        final_volume = balance.final_volume_ml + melt_ml
        final_mass = balance.final_mass_g + melt_g

        # L'equilibrio raggiunto dal raffreddamento, spostato dalla diluizione
        # ambiente, più lo scarto che il transitorio non ha ancora smaltito.
        temperature_c = (
            freezing_point_c(
                self.solute_mol, self.water_g + self.equilibrium_melt_g + ambient_melt_g
            )
            + (self.start_c - self.equilibrium_c) * decay
        )

        return ServingProfile(
            consumption_minutes=minutes,
            initial_temperature_c=self.start_c,
            equilibrium_temperature_c=self.equilibrium_c,
            temperature_c=temperature_c,
            cooling_melt_water_ml=cooling_melt_g / WATER_DENSITY_G_ML,
            ambient_melt_water_ml=ambient_melt_g / WATER_DENSITY_G_ML,
            melt_water_ml=melt_ml,
            ice_mass_g=self.ice_g,
            # Il `max` assorbe solo l'arrotondamento: per costruzione la
            # fusione non supera il ghiaccio disponibile.
            remaining_ice_g=max(self.ice_g - melt_g, 0.0),
            final_volume_ml=final_volume,
            final_mass_g=final_mass,
            total_dilution_factor=(final_volume - balance.total_volume_ml)
            / balance.total_volume_ml,
            abv=balance.pure_alcohol_ml / final_volume,
            brix=balance.sugar_mass_g / final_mass * 100.0,
            acidity=balance.acid_mass_g / final_volume * 100.0,
        )


def _serving_model(recipe: Recipe, balance: BalanceProfile) -> _ServingModel | None:
    if recipe.serving_ice is ServingIce.NONE:
        return None

    mass_g = balance.final_mass_g
    ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
    sugar_g = balance.sugar_mass_g
    # Gli acidi non pesano come soluto: nelle quantità da bar (< 1 % in
    # massa) il loro contributo crioscopico è sotto l'incertezza del modello.
    water_g = max(mass_g - ethanol_g - sugar_g, 0.0)
    solute_mol = ethanol_g / ETHANOL_MOLAR_MASS_G_MOL + sugar_g / SUCROSE_MOLAR_MASS_G_MOL

    cp = _specific_heat(ethanol_g, sugar_g, water_g)
    initial_freezing_c = freezing_point_c(solute_mol, water_g)

    # Un drink shakerato o mescolato esce dalla preparazione all'equilibrio
    # con il proprio ghiaccio; un built nasce a temperatura ambiente.
    start_c = (
        AMBIENT_TEMPERATURE_C
        if recipe.dilution_method is DilutionMethod.BUILT
        else initial_freezing_c
    )

    ice_volume_ml = ICE_VOLUME_PER_DRINK_VOLUME * balance.final_volume_ml
    ice_available_g = ice_volume_ml * ICE_DENSITY_G_ML

    equilibrium_melt_g = _equilibrium_melt_g(
        drink_mass_g=mass_g,
        cp=cp,
        start_temperature_c=start_c,
        solute_mol=solute_mol,
        water_g=water_g,
        ice_available_g=ice_available_g,
    )

    exchange_area_m2 = SPECIFIC_SURFACE_M2_PER_M3[recipe.serving_ice] * ice_volume_ml * 1e-6

    return _ServingModel(
        balance=balance,
        water_g=water_g,
        solute_mol=solute_mol,
        start_c=start_c,
        equilibrium_c=freezing_point_c(solute_mol, water_g + equilibrium_melt_g),
        equilibrium_melt_g=equilibrium_melt_g,
        ice_g=ice_available_g,
        time_constant_s=mass_g * cp / (HEAT_TRANSFER_W_M2_K * exchange_area_m2),
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
    model = _serving_model(recipe, balance)
    return None if model is None else model.at(consumption_minutes)


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
    model = _serving_model(recipe, balance)
    if model is None:
        return None
    # La tolleranza evita di perdere l'ultimo campione quando `span / step`
    # è un intero che la virgola mobile rappresenta come 29.999…
    samples = math.floor(span_minutes / step_minutes + 1e-9)
    return tuple(model.at(index * step_minutes) for index in range(samples + 1))
