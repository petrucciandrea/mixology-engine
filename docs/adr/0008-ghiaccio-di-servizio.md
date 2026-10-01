# ADR-0008 — Il ghiaccio di servizio è un attributo della ricetta, separato dalla tecnica

**Stato:** accettata

## Contesto

`DilutionMethod` (shaken / stirred / built) descrive *come si prepara* un
drink e seleziona la curva di diluizione di Arnold. Non dice nulla su *come
si serve*: un Daiquiri e un Whiskey Sour sono entrambi shakerati, ma il
primo va in coppetta senza ghiaccio e il secondo su cubetti. Il ghiaccio
usato per raffreddare nel shaker viene scartato; quello nel bicchiere resta.

Serve quindi una seconda informazione per ricetta: se c'è ghiaccio nel
bicchiere e di che tipo.

## Decisione

`Recipe.serving_ice` è un `ServingIce` (`NONE`, `CUBES`, `LARGE_CUBE`,
`CRUSHED`), **obbligatorio e senza default**, indipendente da
`dilution_method`.

Assenza e tipo stanno in un solo enum e non in due campi: "senza ghiaccio"
più "cubetti" sarebbe uno stato illegale, che così non si può costruire.

Nessun default, né nel dominio né nel DTO né nello schema: ometterlo è un
errore (422), perché un default `NONE` farebbe passare per "senza ghiaccio"
una ricetta che non ha dichiarato il servizio. La migrazione usa `NONE`
solo per riempire le righe esistenti e poi lo toglie; il seed riallinea i
classici già presenti.

## Aggiornamento: il tipo di ghiaccio entra nel calcolo

Il primo passo registrava solo il dato. Ora `serving_ice` alimenta un
secondo profilo, `ServingProfile`, calcolato con un bilancio termico
(`docs/DOMAIN_MODEL_AND_MATH.md`, sezione 4) invece di coefficienti
empirici per tipo, che non hanno una fonte pubblicata.

- **Separato dal `BalanceProfile`**: quello resta il drink appena servito e
  l'unico su cui lavora il solver; il profilo da servizio dipende dal tempo
  di consumo (parametro `consumption_minutes`, default 10) e non sposta i
  target. Per `NONE` vale `null`, non una diluizione nulla.
- **Il tipo di ghiaccio determina la superficie di scambio**, quindi la
  velocità con cui un drink caldo (built) raggiunge l'equilibrio, non
  l'equilibrio stesso. Conseguenza dichiarata: oltre il primo minuto o due
  i tipi convergono, e la differenza finale fra cubetti e tritato è
  piccola. Un effetto più marcato richiederebbe dati misurati (fusione
  della superficie, mescolamento, impacchettamento) che il progetto non ha.
- Le ipotesi (coefficiente di scambio, calore ambiente, volume di ghiaccio,
  dimensioni dei pezzi) sono costanti nominate e documentate, da tarare.

## Conseguenze

Il modello di diluizione da preparazione non cambia. Tipi più fini (sfera,
colonna per il Collins, nugget) si aggiungono come nuovi valori
dell'enum, con una migrazione e una superficie specifica.
