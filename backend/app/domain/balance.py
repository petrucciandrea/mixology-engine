"""Il risultato del calcolo di bilanciamento.

Value object immutabile: fotografa una ricetta prima e dopo la
diluizione da ghiaccio. Contiene anche le grandezze intermedie (masse,
alcol puro, fattore di diluizione) perché sono ciò che rende il calcolo
verificabile: chi legge il risultato può rifare i conti a mano, e i test
possono ancorare ogni passaggio invece del solo numero finale.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Intervallo di riferimento del rapporto zuccheri/acidi per un sour
#: equilibrato (Brix/Acidity). Sotto è percepito aspro, sopra stucchevole.
#: Valori dal domain model; sono una guida di degustazione, non un vincolo.
SOUR_RATIO_LOWER_BOUND = 5.5
SOUR_RATIO_UPPER_BOUND = 7.0


@dataclass(frozen=True, slots=True)
class BalanceProfile:
    """Profilo calcolato di una ricetta, pre e post diluizione."""

    # --- Grandezze estensive pre-diluizione ---
    total_volume_ml: float
    pure_alcohol_ml: float
    total_mass_g: float
    sugar_mass_g: float
    acid_mass_g: float

    # --- Grandezze intensive pre-diluizione ---
    abv_pre: float
    brix_pre: float
    acidity_pre: float
    sugar_acid_ratio: float | None

    # --- Diluizione ---
    dilution_factor: float
    dilution_water_ml: float
    final_volume_ml: float
    final_mass_g: float

    # --- Grandezze intensive post-diluizione (il drink servito) ---
    abv_post: float
    brix_post: float
    acidity_post: float

    @property
    def abv_post_percent(self) -> float:
        """ABV finale in punti percentuali, come si legge su un'etichetta."""
        return self.abv_post * 100.0

    @property
    def is_balanced_sour(self) -> bool:
        """True se il rapporto zuccheri/acidi cade nella finestra dei sour.

        Il rapporto è calcolato pre-diluizione perché l'acqua abbassa Brix
        e acidità nella stessa proporzione: il rapporto è invariante sotto
        diluizione, ed è proprio questo a renderlo l'indicatore stabile
        dell'equilibrio di una ricetta.
        """
        if self.sugar_acid_ratio is None:
            return False
        return SOUR_RATIO_LOWER_BOUND <= self.sugar_acid_ratio <= SOUR_RATIO_UPPER_BOUND


@dataclass(frozen=True, slots=True)
class ServingProfile:
    """Il drink dopo la diluizione dovuta al ghiaccio nel bicchiere.

    È un profilo **separato** dal `BalanceProfile`: quello descrive il
    drink appena servito (ed è su di esso che lavora il solver), questo lo
    stesso drink dopo `consumption_minutes` di contatto con il ghiaccio di
    servizio. Tenerli distinti evita che un'ipotesi sul tempo di consumo
    sposti i target di bilanciamento.

    Le grandezze intermedie (temperatura, acqua da raffreddamento e da
    calore ambiente) ci sono per lo stesso motivo del `BalanceProfile`:
    rendere il calcolo verificabile a mano.
    """

    consumption_minutes: float

    # --- Termodinamica ---
    initial_temperature_c: float
    equilibrium_temperature_c: float
    #: Temperatura del drink a `consumption_minutes`.
    temperature_c: float

    # --- Acqua di fusione aggiunta dal ghiaccio di servizio ---
    cooling_melt_water_ml: float
    ambient_melt_water_ml: float
    melt_water_ml: float

    # --- Ghiaccio nel bicchiere ---
    ice_mass_g: float
    remaining_ice_g: float

    # --- Il drink a fine consumo ---
    final_volume_ml: float
    final_mass_g: float
    total_dilution_factor: float
    abv: float
    brix: float
    acidity: float

    @property
    def abv_percent(self) -> float:
        return self.abv * 100.0
