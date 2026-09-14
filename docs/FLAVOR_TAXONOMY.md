# Tassonomia organolettica

I 32 descrittori che compongono il profilo di sapore di un ingrediente.
Sono il contratto della colonna `ingredients.flavor_vector` (`vector(32)`)
e la sorgente di verità è `backend/app/domain/flavor.py`: questo documento
la spiega, non la duplica.

Ogni componente è un'**intensità in [0, 1]**: 0 significa assente, 1
significa descrittore dominante dell'ingrediente. Non è una scala assoluta
fra ingredienti diversi ma un profilo relativo al singolo prodotto — è la
*direzione* del vettore a contare, perché la similarità usata dal matcher
è il coseno, che ignora la magnitudine complessiva.

L'**ordine è significativo** e corrisponde alle posizioni nella colonna del
database. Aggiungere, togliere o riordinare un descrittore richiede una
migrazione (vedi [ADR-0005](adr/0005-vettore-di-sapore-a-descrittori.md)).

## Gusti fondamentali (posizioni 0-4)

Ciò che percepiscono le papille, non il naso.

| # | Descrittore | Significato |
|---|-------------|-------------|
| 0 | `sweet` | Dolcezza percepita |
| 1 | `sour` | Acidità percepita |
| 2 | `bitter` | Amaro |
| 3 | `salty` | Sapidità |
| 4 | `umami` | Sapidità glutammica (sherry, alcuni fermentati) |

## Sensazioni trigeminali e tattili (posizioni 5-8)

Non sono gusti né aromi: sono stimolazioni del nervo trigemino e sensazioni
di consistenza. Contano perché determinano quanto due ingredienti siano
davvero intercambiabili **in bocca**, che è ciò che serve al matcher per
proporre una sostituzione.

| # | Descrittore | Significato |
|---|-------------|-------------|
| 5 | `alcohol_heat` | Calore alcolico, "bruciore" |
| 6 | `astringency` | Astringenza, secchezza tannica |
| 7 | `cooling` | Freschezza da mentolo, canfora |
| 8 | `pungency` | Pungenza: pepe, zenzero, effervescenza |

## Famiglie aromatiche (posizioni 9-31)

L'asse olfattivo e retrolfattivo, dove si gioca gran parte della
somiglianza fra prodotti.

| # | Descrittore | Esempi tipici |
|---|-------------|---------------|
| 9 | `citrus` | Scorza e succo di agrumi, triple sec |
| 10 | `orchard_fruit` | Mela, pera |
| 11 | `stone_fruit` | Pesca, albicocca, ciliegia (maraschino) |
| 12 | `berry` | Frutti di bosco, cassis |
| 13 | `tropical_fruit` | Ananas, banana, frutto della passione |
| 14 | `dried_fruit` | Uvetta, fico, prugna secca (vermouth, cognac) |
| 15 | `floral` | Fiori d'arancio, violetta, sambuco |
| 16 | `herbaceous` | Erbe aromatiche e note vegetali (chartreuse, tequila) |
| 17 | `mint` | Menta, mentolo |
| 18 | `anise` | Anice, finocchio, assenzio |
| 19 | `resinous` | Ginepro, pino, resina |
| 20 | `pepper` | Pepe nero, note piccanti secche (rye) |
| 21 | `warm_spice` | Cannella, chiodi di garofano, noce moscata |
| 22 | `earthy` | Terra, radici, agave cotta |
| 23 | `woody` | Legno, quercia, cedro |
| 24 | `vanilla` | Vaniglia, cocco da botte |
| 25 | `caramel` | Caramello, zucchero bruciato, melassa |
| 26 | `smoke` | Affumicato, torba (mezcal) |
| 27 | `roasted` | Caffè, cacao, tostato |
| 28 | `nutty` | Mandorla (orgeat), nocciola, sherry ossidativo |
| 29 | `honey` | Miele |
| 30 | `funky` | Fermentato, *hogo* dei rum, lattico |
| 31 | `medicinal` | Fenolico, genziana, chinino |

## Come si compila un profilo

Nominando solo i descrittori non nulli:

```python
FlavorProfile.from_descriptors(sour=0.95, citrus=0.9, herbaceous=0.2)
```

Un nome non riconosciuto solleva `InvalidFlavorProfileError`, invece di
essere ignorato in silenzio: in un vocabolario di 32 termini il refuso è il
rischio reale, e un profilo silenziosamente vuoto verrebbe scoperto solo
quando il matcher inizia a restituire risultati insensati.

L'API espone il vocabolario su `GET /api/v1/ingredients/flavor-descriptors`,
così nessun client deve conoscerlo a memoria.

## Nota sulla precisione

La colonna `vector` di pgvector è a **singola precisione**: 0.8 scritto in
colonna torna 0.800000011920929. I mapper arrotondano in lettura alla sesta
cifra decimale, perché le intensità sono valori compilati a mano con due o
tre decimali e quelle cifre in più sono rumore di rappresentazione, non
informazione.
