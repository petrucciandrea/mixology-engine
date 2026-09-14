"""Layer di dominio.

Contiene le regole del bilanciamento e nient'altro: nessun import di
Pydantic, SQLAlchemy, FastAPI o SciPy. È la regola di dipendenza di Clean
Architecture presa alla lettera, ed è verificabile — `tests/unit/` gira
senza database, senza Redis e senza variabili d'ambiente.
"""
