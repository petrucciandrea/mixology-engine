"""Layer applicativo: orchestrazione dei casi d'uso e solver numerico.

Dipende dal dominio, mai dal contrario. Conosce SciPy (il solver è qui,
non nel dominio) ma non conosce HTTP né SQL: parla con la persistenza
solo attraverso le porte dichiarate in `domain/repositories.py`.
"""
