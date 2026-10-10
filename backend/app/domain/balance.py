"""Il risultato del calcolo di bilanciamento.

Value object immutabile: fotografa una ricetta prima e dopo la
diluizione da ghiaccio. Contiene anche le grandezze intermedie (masse,
alcol puro, fattore di diluizione) perché sono ciò che rende il calcolo
verificabile: chi legge il risultato può rifare i conti a mano, e i test
possono ancorare ogni passaggio invece del solo numero finale.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .enums import RecipeFamily

#: Acidità minima (% p/v, pre-diluizione) perché il rapporto zuccheri/acidi
#: abbia senso. Sotto, l'acido è una traccia — il 0.1 % della tonica, lo 0.3 %
#: di vermouth e Campari — e il drink non ha un carattere acido da
#: bilanciare: dividere gli zuccheri per quella traccia dà numeri come 44 o
#: 85, matematicamente esatti e privi di significato. Un sour vero sta oltre
#: l'1 % (i classici del seed vanno da 1.1 a 1.9). La soglia è volutamente
#: più bassa, 0.5 %: esclude le tracce senza togliere il rapporto a un sour
#: leggero o a un highball agrumato, e senza farlo sparire a un solver che
#: sta cercando di aggiungere acido. Come ogni soglia sensoriale è una
#: taratura, non una costante fisica.
SUGAR_ACID_MIN_ACIDITY = 0.5

#: Finestra del rapporto zuccheri/acidi (grammi di zucchero per grammo di
#: acido) entro cui un **sour** è equilibrato. Sotto è aspro, sopra dolce.
#:
#: È tarata sui classici del seed (`tests/unit/test_sour_balance.py`): sui
#: 20 sour giudicabili il rapporto va da 3.8 (Margarita) a 10.7 (Penicillin),
#: e la finestra li contiene tutti tranne l'Amaretto Sour (16.2), dolce per
#: costruzione perché poggia su un liquore a 40 °Bx. La vecchia finestra
#: 5.5–7.0 era più stretta del campo dei sour tradizionali — un Whiskey Sour
#: vale 9.4, un Last Word 10.0 — e li marcava dolci. Il Gimlet resta fuori
#: dal giudizio perché il cordial al lime porta troppo poco acido.
SOUR_RATIO_LOWER_BOUND = 3.5
SOUR_RATIO_UPPER_BOUND = 12.0


class SourBalance(str, Enum):
    """Giudizio sul rapporto zuccheri/acidi di un sour."""

    TOO_TART = "TOO_TART"
    BALANCED = "BALANCED"
    TOO_SWEET = "TOO_SWEET"


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
    # Brix in % peso, acidità in % p/v (g di acido ogni 100 ml di drink).
    abv_pre: float
    brix_pre: float
    acidity_pre: float
    #: Grammi di zucchero per grammo di acido; `None` se l'acidità è sotto
    #: `SUGAR_ACID_MIN_ACIDITY`. Non dipende dalla diluizione.
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


def assess_sour_balance(family: RecipeFamily | None, profile: BalanceProfile) -> SourBalance | None:
    """Il giudizio sul rapporto zuccheri/acidi, solo per i sour.

    `None` quando non si può o non si deve giudicare: la ricetta non è un
    sour (la finestra descrive il loro equilibrio, non quello di uno
    Spritz o di uno Screwdriver) oppure il rapporto non esiste perché gli
    acidi sono in tracce. `None` e non `BALANCED`: "non applicabile" non è
    un'approvazione.

    Il rapporto è un quoziente di masse, quindi non dipende dalla
    diluizione: lo stesso giudizio vale prima e dopo il ghiaccio.
    """
    if family is not RecipeFamily.SOUR or profile.sugar_acid_ratio is None:
        return None
    if profile.sugar_acid_ratio < SOUR_RATIO_LOWER_BOUND:
        return SourBalance.TOO_TART
    if profile.sugar_acid_ratio > SOUR_RATIO_UPPER_BOUND:
        return SourBalance.TOO_SWEET
    return SourBalance.BALANCED


@dataclass(frozen=True, slots=True)
class ServingProfile:
    """Il drink dopo la diluizione dovuta al ghiaccio nel bicchiere.

    È un profilo **separato** dal `BalanceProfile`: quello descrive il
    drink appena servito (ed è su di esso che lavora il solver), questo lo
    stesso drink dopo `consumption_minutes` di contatto con il ghiaccio di
    servizio. Tenerli distinti evita che un'ipotesi sul tempo di consumo
    sposti i target di bilanciamento.

    Le grandezze intermedie (temperature, calore entrato dall'ambiente) ci
    sono per lo stesso motivo del `BalanceProfile`: rendere il calcolo
    verificabile a mano. Con queste la legge di conservazione del modello,
    `(C₀ + m·c_w)·T + L·m − C₀·T_s = Q_amb`, si controlla da fuori.
    """

    consumption_minutes: float

    # --- Termodinamica ---
    #: Temperatura di servizio: il punto di congelamento per shaken e
    #: stirred, l'ambiente per un built.
    initial_temperature_c: float
    #: Temperatura del drink a `consumption_minutes`.
    temperature_c: float
    #: Punto di congelamento della miscela diluita: la temperatura verso cui
    #: il ghiaccio spinge il drink finché ce n'è.
    freezing_point_c: float
    #: Calore entrato dall'ambiente attraverso il vetro, cumulato.
    ambient_heat_j: float

    # --- Acqua di fusione aggiunta dal ghiaccio di servizio ---
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
