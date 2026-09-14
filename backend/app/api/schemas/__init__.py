"""DTO Pydantic: il contratto pubblico dell'API.

Sono separati dalle entità di dominio di proposito. Il dominio modella le
regole del bilanciamento; questi schemi modellano ciò che un client HTTP
può inviare e ricevere. Tenerli distinti significa che una rifattorizzazione
interna non diventa un breaking change per chi consuma l'API, e che
l'output non espone mai per sbaglio un campo interno.
"""
