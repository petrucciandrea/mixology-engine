"""Endpoint del matcher, end-to-end sullo stack completo."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from .conftest import API, create_ingredient, daiquiri_payload

pytestmark = pytest.mark.api


class TestSubstitutes:
    async def test_a_close_citrus_outranks_a_distant_spirit(
        self, client: AsyncClient, lime_id: str
    ) -> None:
        """Il confronto è fra due ingredienti creati dal test, non con la
        prima posizione assoluta: il database di sviluppo contiene già una
        dispensa, e pretendere un vincitore assoluto legherebbe il test a
        dati che non gli appartengono.
        """
        lemon_id = await create_ingredient(
            client,
            name="Succo di Limone",
            category="JUICE",
            abv=0.0,
            brix=2.5,
            acidity=5.5,
            density_g_ml=1.02,
            flavor={"sour": 0.9, "citrus": 0.95, "floral": 0.15},
        )
        mezcal_id = await create_ingredient(
            client,
            name="Mezcal",
            category="SPIRIT",
            abv=0.45,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.94,
            flavor={"smoke": 0.9, "earthy": 0.6, "alcohol_heat": 0.7},
        )

        response = await client.get(f"{API}/match/substitutes/{lime_id}", params={"limit": 50})
        body = response.json()
        ranked = [item["ingredient"]["id"] for item in body]

        assert response.status_code == 200
        assert lemon_id in ranked
        assert lime_id not in ranked, "un ingrediente non sostituisce se stesso"
        assert mezcal_id not in ranked or ranked.index(lemon_id) < ranked.index(mezcal_id)

        lemon = next(item for item in body if item["ingredient"]["id"] == lemon_id)
        assert lemon["flavor_similarity"] > 0.9

    async def test_physical_incompatibility_demotes_a_perfect_aromatic_match(
        self, client: AsyncClient, lime_id: str
    ) -> None:
        """Uno sciroppo al lime sa di lime ma non si comporta come il lime.

        È il caso che giustifica l'intero punteggio a due assi: la
        similarità organolettica da sola lo metterebbe in cima.
        """
        # Profilo organolettico *identico* a quello della fixture del lime:
        # è ciò che rende il caso netto, perché la similarità vale
        # esattamente 1 e a distinguere i due resta solo la fisica.
        syrup_id = await create_ingredient(
            client,
            name="Sciroppo al Lime",
            category="SYRUP",
            abv=0.0,
            brix=55.0,
            acidity=0.5,
            density_g_ml=1.26,
            flavor={"sour": 0.95, "citrus": 0.9},
        )

        body = (await client.get(f"{API}/match/substitutes/{lime_id}", params={"limit": 50})).json()
        syrup = next(item for item in body if item["ingredient"]["id"] == syrup_id)

        assert syrup["flavor_similarity"] == pytest.approx(1.0, abs=1e-4)
        assert syrup["physical_compatibility"] < 0.2
        assert syrup["overall"] < 0.2
        assert syrup["warnings"], "la differenza fisica va detta, non solo pesata"

    async def test_results_are_ordered_by_overall_score(
        self, client: AsyncClient, lime_id: str
    ) -> None:
        body = (await client.get(f"{API}/match/substitutes/{lime_id}", params={"limit": 10})).json()
        scores = [item["overall"] for item in body]
        assert scores == sorted(scores, reverse=True)

    async def test_the_category_filter_is_honoured(self, client: AsyncClient, lime_id: str) -> None:
        body = (
            await client.get(
                f"{API}/match/substitutes/{lime_id}",
                params={"limit": 10, "same_category_only": True},
            )
        ).json()

        assert all(item["ingredient"]["category"] == "JUICE" for item in body)

    async def test_an_unprofiled_ingredient_yields_no_candidates(self, client: AsyncClient) -> None:
        """ "Non lo so" è una risposta migliore di una lista a caso."""
        anonymous_id = await create_ingredient(
            client,
            name="Distillato Anonimo",
            category="SPIRIT",
            abv=0.40,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.95,
            flavor=None,
        )

        response = await client.get(f"{API}/match/substitutes/{anonymous_id}")

        assert response.status_code == 200
        assert response.json() == []

    async def test_an_unknown_ingredient_is_a_404(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/match/substitutes/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "EntityNotFoundError"


class TestPairings:
    async def test_suggestions_come_with_a_rationale(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        # Una ricetta salvata alimenta il segnale di co-occorrenza.
        await client.post(
            f"{API}/recipes", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
        )

        response = await client.post(
            f"{API}/match/pairings", json={"ingredient_ids": [rum_id], "limit": 3}
        )
        body = response.json()

        assert response.status_code == 200
        assert body
        assert all(item["rationale"] for item in body)
        assert all(item["affinity"] > 0 for item in body)

    async def test_never_suggests_what_is_already_in_the_glass(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        await client.post(
            f"{API}/recipes", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
        )

        body = (
            await client.post(
                f"{API}/match/pairings",
                json={"ingredient_ids": [rum_id, lime_id, syrup_id], "limit": 10},
            )
        ).json()

        suggested = {item["ingredient"]["id"] for item in body}
        assert suggested.isdisjoint({rum_id, lime_id, syrup_id})

    async def test_an_unknown_seed_yields_an_empty_list(self, client: AsyncClient) -> None:
        """Un id inesistente non è un errore qui: è semplicemente un nodo
        che il grafo non contiene, e la risposta onesta è "nessun
        suggerimento" invece di un 404 su una risorsa che il chiamante non
        stava chiedendo."""
        response = await client.post(
            f"{API}/match/pairings", json={"ingredient_ids": [str(uuid.uuid4())]}
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_an_empty_seed_list_is_rejected(self, client: AsyncClient) -> None:
        response = await client.post(f"{API}/match/pairings", json={"ingredient_ids": []})
        assert response.status_code == 422


class TestBridge:
    async def test_finds_a_path_between_two_distant_ingredients(
        self, client: AsyncClient, rum_id: str, lime_id: str
    ) -> None:
        response = await client.get(
            f"{API}/match/bridge", params={"source_id": rum_id, "target_id": lime_id}
        )

        # Il percorso può esistere o no a seconda della dispensa presente,
        # ma la risposta deve essere sempre una delle due forme previste.
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            body = response.json()
            assert body["path"][0]["id"] == rum_id
            assert body["path"][-1]["id"] == lime_id
            assert body["steps"] == len(body["path"]) - 1
            assert 0.0 < body["strength"] <= 1.0

    async def test_an_unknown_ingredient_is_a_404(self, client: AsyncClient, rum_id: str) -> None:
        response = await client.get(
            f"{API}/match/bridge",
            params={"source_id": rum_id, "target_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    async def test_two_unconnected_ingredients_report_422_not_404(
        self, client: AsyncClient
    ) -> None:
        """A mancare non è una risorsa, è una relazione fra due risorse esistenti."""
        lonely_one = await create_ingredient(
            client,
            name="Isolato Uno",
            category="OTHER",
            abv=0.0,
            brix=0.0,
            acidity=0.0,
            density_g_ml=1.0,
            flavor={"umami": 1.0},
        )
        lonely_two = await create_ingredient(
            client,
            name="Isolato Due",
            category="OTHER",
            abv=0.0,
            brix=0.0,
            acidity=0.0,
            density_g_ml=1.0,
            flavor={"salty": 1.0},
        )

        response = await client.get(
            f"{API}/match/bridge",
            params={"source_id": lonely_one, "target_id": lonely_two},
        )

        assert response.status_code == 422
        assert "affinità" in response.json()["detail"]


class TestGraphOverview:
    async def test_reports_the_shape_of_the_graph(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.get(f"{API}/match/graph")
        body = response.json()

        assert response.status_code == 200
        assert body["stats"]["nodes"] >= 3
        assert 0.0 <= body["stats"]["density"] <= 1.0
        assert body["stats"]["communities"] == len(body["communities"])

    async def test_communities_are_listed_from_the_largest(
        self, client: AsyncClient, rum_id: str
    ) -> None:
        body = (await client.get(f"{API}/match/graph")).json()
        sizes = [group["size"] for group in body["communities"]]

        assert sizes == sorted(sizes, reverse=True)
        assert all(group["size"] == len(group["ingredients"]) for group in body["communities"])
