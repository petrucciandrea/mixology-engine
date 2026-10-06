"""Test HTTP end-to-end: routing, DTO, errori, catena completa.

Coprono il percorso felice e — soprattutto — i casi di errore, che sono
quelli in cui un'API si rivela ben fatta o no.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from .conftest import API, create_ingredient, daiquiri_payload

pytestmark = pytest.mark.api


class TestServiceEndpoints:
    async def test_root_announces_the_service(self, client: AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "mixology-engine"

    async def test_health_reports_every_dependency(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        body = response.json()

        assert response.status_code == 200
        assert body == {"status": "ok", "database": "connected", "redis": "connected"}

    async def test_health_without_redis_is_not_degraded(
        self, client_without_redis: AsyncClient
    ) -> None:
        """Redis serve solo alla cache del grafo: se non è configurato il
        servizio è completo, solo senza un'ottimizzazione. Un 503 qui
        farebbe ritirare l'istanza all'orchestratore senza motivo."""
        response = await client_without_redis.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected", "redis": "disabled"}

    async def test_openapi_schema_is_served(self, client: AsyncClient) -> None:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert f"{API}/balance" in response.json()["paths"]


class TestIngredientsApi:
    async def test_flavor_vocabulary_is_discoverable(self, client: AsyncClient) -> None:
        """Il client non deve conoscere i 32 descrittori a memoria."""
        response = await client.get(f"{API}/ingredients/flavor-descriptors")
        body = response.json()

        assert response.status_code == 200
        assert body["dimension"] == 32
        assert len(body["descriptors"]) == 32
        assert set(body["families"]) == {"basic_taste", "tactile", "aroma"}

    async def test_creating_and_reading_back_an_ingredient(self, client: AsyncClient) -> None:
        ingredient_id = await create_ingredient(
            client,
            name="Mezcal",
            category="SPIRIT",
            abv=0.45,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.94,
            flavor={"smoke": 0.9, "earthy": 0.6, "alcohol_heat": 0.7},
        )

        response = await client.get(f"{API}/ingredients/{ingredient_id}")
        body = response.json()

        assert response.status_code == 200
        assert body["category"] == "SPIRIT"
        assert body["physical_profile"]["abv"] == 0.45
        assert body["dominant_flavors"][0] == "smoke"
        assert body["is_active"] is True

    async def test_unknown_ingredient_is_a_404_with_a_typed_error(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(f"{API}/ingredients/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["error"]["type"] == "EntityNotFoundError"

    async def test_duplicate_name_is_a_409(self, client: AsyncClient) -> None:
        payload = {
            "name": f"Gin Unico {uuid.uuid4().hex[:8]}",
            "category": "SPIRIT",
            "physical_profile": {
                "density_g_ml": 0.94,
                "brix": 0.0,
                "acidity": 0.0,
                "abv": 0.43,
            },
        }
        assert (await client.post(f"{API}/ingredients", json=payload)).status_code == 201

        clash = await client.post(f"{API}/ingredients", json=payload)

        assert clash.status_code == 409
        assert clash.json()["error"]["type"] == "DuplicateEntityError"

    async def test_an_unknown_flavor_descriptor_is_rejected(self, client: AsyncClient) -> None:
        """Un refuso nel vocabolario non deve passare in silenzio."""
        response = await client.post(
            f"{API}/ingredients",
            json={
                "name": f"Refuso {uuid.uuid4().hex[:8]}",
                "category": "SPIRIT",
                "physical_profile": {
                    "density_g_ml": 0.94,
                    "brix": 0.0,
                    "acidity": 0.0,
                    "abv": 0.43,
                },
                "flavor_profile": {"citrusy": 0.9},
            },
        )

        assert response.status_code == 422
        assert response.json()["error"]["type"] == "InvalidFlavorProfileError"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("abv", 40.0), ("brix", 120.0), ("acidity", 50.0), ("density_g_ml", 5.0)],
    )
    async def test_physically_impossible_values_are_rejected(
        self, client: AsyncClient, field: str, value: float
    ) -> None:
        """`abv: 40` invece di `0.40` è l'errore più probabile su questa API."""
        profile = {"density_g_ml": 0.94, "brix": 0.0, "acidity": 0.0, "abv": 0.43}
        profile[field] = value

        response = await client.post(
            f"{API}/ingredients",
            json={
                "name": f"Impossibile {uuid.uuid4().hex[:8]}",
                "category": "SPIRIT",
                "physical_profile": profile,
            },
        )

        assert response.status_code == 422

    async def test_deactivating_removes_it_from_the_default_listing(
        self, client: AsyncClient, rum_id: str
    ) -> None:
        deactivated = await client.delete(f"{API}/ingredients/{rum_id}")
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        listing = await client.get(f"{API}/ingredients", params={"limit": 200})
        assert rum_id not in {item["id"] for item in listing.json()["items"]}

        with_inactive = await client.get(
            f"{API}/ingredients", params={"limit": 200, "include_inactive": True}
        )
        assert rum_id in {item["id"] for item in with_inactive.json()["items"]}

    async def test_listing_is_paginated(self, client: AsyncClient, rum_id: str) -> None:
        response = await client.get(f"{API}/ingredients", params={"limit": 1, "offset": 0})
        body = response.json()

        assert len(body["items"]) <= 1
        assert body["limit"] == 1
        assert body["total"] >= 1


class TestBalanceApi:
    async def test_calculating_a_draft_recipe_persists_nothing(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        """L'editor calcola a ogni movimento di slider: non può salvare ogni volta."""
        before = (await client.get(f"{API}/recipes")).json()["total"]

        response = await client.post(
            f"{API}/balance", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
        )
        body = response.json()

        assert response.status_code == 200
        assert body["profile"]["total_volume_ml"] == pytest.approx(110.0)
        assert body["profile"]["abv_post"] < body["profile"]["abv_pre"]
        assert body["recipe"]["id"].startswith("draft:")
        assert (await client.get(f"{API}/recipes")).json()["total"] == before

    async def test_the_computed_profile_matches_the_hand_calculation(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.post(
            f"{API}/balance", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
        )
        profile = response.json()["profile"]

        assert profile["pure_alcohol_ml"] == pytest.approx(24.0)
        assert profile["total_mass_g"] == pytest.approx(112.5)
        # 12.8253 g di zuccheri / 1.8 g di acidi
        assert profile["sugar_acid_ratio"] == pytest.approx(12.8253 / 1.8, abs=1e-3)
        # Acidità p/v: 1.8 g su 110 ml prima dell'acqua di fusione.
        assert profile["acidity_pre"] == pytest.approx(1.8 / 110.0 * 100, abs=1e-6)

    async def test_sour_balance_is_null_without_a_family(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        """Gli stessi numeri di un sour, ma senza famiglia: nessun giudizio."""
        response = await client.post(
            f"{API}/balance", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
        )

        assert response.json()["profile"]["sour_balance"] is None

    @pytest.mark.parametrize(
        ("volumes", "expected"),
        [((60, 30, 20), "BALANCED"), ((50, 15, 35), "TOO_SWEET"), ((60, 45, 5), "TOO_TART")],
    )
    async def test_a_sour_gets_a_verdict_on_its_sugar_acid_ratio(
        self,
        client: AsyncClient,
        rum_id: str,
        lime_id: str,
        syrup_id: str,
        volumes: tuple[float, float, float],
        expected: str,
    ) -> None:
        payload = {**daiquiri_payload(rum_id, lime_id, syrup_id, volumes), "family": "SOUR"}

        response = await client.post(f"{API}/balance", json=payload)

        assert response.json()["profile"]["sour_balance"] == expected

    async def test_balance_includes_the_serving_profile_only_with_ice(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        without_ice = await client.post(f"{API}/balance", json=payload)
        assert without_ice.json()["serving_profile"] is None

        on_ice = await client.post(
            f"{API}/balance",
            params={"consumption_minutes": 5},
            json={**payload, "serving_ice": "CUBES"},
        )
        serving = on_ice.json()["serving_profile"]
        assert serving["consumption_minutes"] == 5
        assert serving["melt_water_ml"] > 0
        assert serving["abv"] < on_ice.json()["profile"]["abv_post"]
        assert serving["temperature_c"] > serving["initial_temperature_c"]
        assert 0 < serving["remaining_ice_g"] < serving["ice_mass_g"]

    async def test_balance_on_ice_carries_the_serving_curve(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        without_ice = await client.post(f"{API}/balance", json=payload)
        assert without_ice.json()["serving_curve"] is None

        response = await client.post(f"{API}/balance", json={**payload, "serving_ice": "CUBES"})
        on_ice = response.json()
        curve = on_ice["serving_curve"]
        # Mezz'ora al minuto, dal drink appena servito.
        assert [point["consumption_minutes"] for point in curve] == list(range(31))
        assert curve[0]["melt_water_ml"] == 0
        assert curve[0]["abv"] == pytest.approx(on_ice["profile"]["abv_post"])
        # Il campione a 10 minuti è il profilo di servizio di default.
        assert curve[10] == on_ice["serving_profile"]

    async def test_implausible_consumption_time_is_a_422(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.post(
            f"{API}/balance",
            params={"consumption_minutes": 600},
            json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20)),
        )
        assert response.status_code == 422

    async def test_referencing_a_missing_ingredient_is_a_404(
        self, client: AsyncClient, rum_id: str
    ) -> None:
        response = await client.post(
            f"{API}/balance",
            json={
                "name": "Fantasma",
                "dilution_method": "SHAKEN",
                "serving_ice": "NONE",
                "ingredients": [
                    {"ingredient_id": rum_id, "volume_ml": 60},
                    {"ingredient_id": str(uuid.uuid4()), "volume_ml": 30},
                ],
            },
        )

        assert response.status_code == 404
        assert response.json()["error"]["type"] == "EntityNotFoundError"

    async def test_an_empty_recipe_is_rejected_by_the_schema(self, client: AsyncClient) -> None:
        response = await client.post(
            f"{API}/balance",
            json={
                "name": "Vuota",
                "dilution_method": "SHAKEN",
                "serving_ice": "NONE",
                "ingredients": [],
            },
        )
        assert response.status_code == 422

    async def test_unknown_fields_are_refused(self, client: AsyncClient, rum_id: str) -> None:
        """`extra="forbid"` intercetta i refusi nei nomi dei campi.

        Senza, un client che scrive `dilutionMethod` riceverebbe un 200 e un
        risultato calcolato con il metodo sbagliato.
        """
        response = await client.post(
            f"{API}/balance",
            json={
                "name": "Refuso",
                "dilution_method": "SHAKEN",
                "serving_ice": "NONE",
                "ingredients": [{"ingredient_id": rum_id, "volume_ml": 60}],
                "dilutionMethod": "STIRRED",
            },
        )
        assert response.status_code == 422


class TestOptimizeApi:
    async def test_optimizing_reaches_the_targets_and_reports_convergence(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.post(
            f"{API}/optimize",
            json={
                "recipe": daiquiri_payload(rum_id, lime_id, syrup_id, (50, 15, 35)),
                # Target compatibili fra loro: i valori di un Daiquiri 60/25/20.
                "target": {"abv": 0.15, "brix": 8.0, "acidity": 0.95},
            },
        )
        body = response.json()

        assert response.status_code == 200
        assert body["status"] == "CONVERGED"
        assert body["max_relative_error"] < 0.10
        assert body["iterations"] > 0
        assert len(body["residuals"]) == 3

    async def test_the_returned_profile_belongs_to_the_returned_recipe(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        """Ciò che l'API dichiara deve essere ciò che si ottiene versando."""
        optimized = (
            await client.post(
                f"{API}/optimize",
                json={
                    "recipe": daiquiri_payload(rum_id, lime_id, syrup_id, (50, 15, 35)),
                    "target": {"abv": 0.16, "brix": 10.0},
                },
            )
        ).json()

        recomputed = await client.post(
            f"{API}/balance",
            json={
                "name": optimized["recipe"]["name"],
                "dilution_method": optimized["recipe"]["dilution_method"],
                "serving_ice": optimized["recipe"]["serving_ice"],
                "ingredients": [
                    {
                        "ingredient_id": item["ingredient"]["id"],
                        "volume_ml": item["volume_ml"],
                    }
                    for item in optimized["recipe"]["ingredients"]
                ],
            },
        )

        assert recomputed.json()["profile"]["abv_post"] == pytest.approx(
            optimized["profile"]["abv_post"]
        )

    async def test_per_ingredient_bounds_are_honoured(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.post(
            f"{API}/optimize",
            json={
                "recipe": daiquiri_payload(rum_id, lime_id, syrup_id, (50, 15, 35)),
                "target": {"abv": 0.14, "brix": 9.0},
                "settings": {"bounds_by_ingredient": {rum_id: {"min_ml": 50.0, "max_ml": 55.0}}},
            },
        )
        body = response.json()

        rum_volume = next(
            item["volume_ml"]
            for item in body["recipe"]["ingredients"]
            if item["ingredient"]["id"] == rum_id
        )
        assert 50.0 <= rum_volume <= 55.0

    async def test_an_empty_target_is_rejected(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        response = await client.post(
            f"{API}/optimize",
            json={
                "recipe": daiquiri_payload(rum_id, lime_id, syrup_id, (50, 15, 35)),
                "target": {},
            },
        )
        assert response.status_code == 422


class TestRecipesApi:
    async def test_full_lifecycle(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        created = await client.post(
            f"{API}/recipes",
            json={
                **daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20)),
                "instructions": "Shake, doppio filtro, coppetta ghiacciata.",
            },
        )
        assert created.status_code == 201
        recipe_id = created.json()["id"]
        assert created.json()["instructions"].startswith("Shake")

        fetched = await client.get(f"{API}/recipes/{recipe_id}")
        assert fetched.status_code == 200
        assert [item["volume_ml"] for item in fetched.json()["ingredients"]] == [60, 30, 20]

        updated = await client.put(
            f"{API}/recipes/{recipe_id}",
            json=daiquiri_payload(rum_id, lime_id, syrup_id, (55, 27.5, 15)),
        )
        assert updated.status_code == 200
        assert [item["volume_ml"] for item in updated.json()["ingredients"]] == [55, 27.5, 15]

        assert (await client.delete(f"{API}/recipes/{recipe_id}")).status_code == 204
        assert (await client.get(f"{API}/recipes/{recipe_id}")).status_code == 404

    async def test_serving_ice_is_stored_and_returned(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        created = await client.post(
            f"{API}/recipes",
            json={
                **daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20)),
                "serving_ice": "CRUSHED",
            },
        )
        assert created.status_code == 201
        assert created.json()["serving_ice"] == "CRUSHED"

        fetched = await client.get(f"{API}/recipes/{created.json()['id']}")
        assert fetched.json()["serving_ice"] == "CRUSHED"

    async def test_serving_ice_is_mandatory_and_closed_vocabulary(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        """Il servizio non ha un default: ometterlo è un errore, non "senza ghiaccio"."""
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        missing = {key: value for key, value in payload.items() if key != "serving_ice"}
        assert (await client.post(f"{API}/recipes", json=missing)).status_code == 422

        unknown = {**payload, "serving_ice": "SPHERE"}
        assert (await client.post(f"{API}/recipes", json=unknown)).status_code == 422

    async def test_glass_is_optional_stored_and_returned(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        without = await client.post(f"{API}/recipes", json=payload)
        assert without.status_code == 201
        assert without.json()["glass"] is None

        created = await client.post(f"{API}/recipes", json={**payload, "glass": "COUPE"})
        assert created.status_code == 201
        assert created.json()["glass"] == "COUPE"

        fetched = await client.get(f"{API}/recipes/{created.json()['id']}")
        assert fetched.json()["glass"] == "COUPE"

    async def test_family_is_optional_stored_and_returned(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        without = await client.post(f"{API}/recipes", json=payload)
        assert without.status_code == 201
        assert without.json()["family"] is None

        created = await client.post(f"{API}/recipes", json={**payload, "family": "SOUR"})
        assert created.status_code == 201
        assert created.json()["family"] == "SOUR"

        fetched = await client.get(f"{API}/recipes/{created.json()['id']}")
        assert fetched.json()["family"] == "SOUR"

    async def test_family_is_a_closed_vocabulary(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        response = await client.post(f"{API}/recipes", json={**payload, "family": "FLIP"})

        assert response.status_code == 422

    async def test_glass_is_a_closed_vocabulary(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        response = await client.post(f"{API}/recipes", json={**payload, "glass": "BUCKET"})

        assert response.status_code == 422

    async def test_balance_reports_how_the_drink_fills_the_glass(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        assert (await client.post(f"{API}/balance", json=payload)).json()["glass_fit"] is None

        coupe = (await client.post(f"{API}/balance", json={**payload, "glass": "COUPE"})).json()
        assert coupe["glass_fit"]["capacity_ml"] == 200
        assert coupe["glass_fit"]["max_volume_ml"] == pytest.approx(180.0)
        assert coupe["glass_fit"]["ice_volume_ml"] == 0
        assert coupe["glass_fit"]["volume_ml"] == pytest.approx(coupe["profile"]["final_volume_ml"])
        assert coupe["glass_fit"]["overflows"] is False

        rocks = (
            await client.post(
                f"{API}/balance", json={**payload, "glass": "ROCKS", "serving_ice": "CUBES"}
            )
        ).json()
        # 350 × 0.9 × 0.35 = 110.25 ml di ghiaccio.
        assert rocks["glass_fit"]["ice_volume_ml"] == pytest.approx(110.25)

        shot = (await client.post(f"{API}/balance", json={**payload, "glass": "SHOT"})).json()
        assert shot["glass_fit"]["overflows"] is True
        assert shot["glass_fit"]["fill_ratio"] > 1.0

    async def test_optimize_respects_the_glass_capacity(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        payload = daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))

        response = await client.post(
            f"{API}/optimize",
            json={
                "recipe": {**payload, "glass": "COUPE"},
                "target": {"final_volume_ml": 220},
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "INFEASIBLE"
        assert response.json()["recipe"]["glass"] == "COUPE"

    async def test_balance_of_a_stored_recipe(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        recipe_id = (
            await client.post(
                f"{API}/recipes", json=daiquiri_payload(rum_id, lime_id, syrup_id, (60, 30, 20))
            )
        ).json()["id"]

        response = await client.get(f"{API}/recipes/{recipe_id}/balance")

        assert response.status_code == 200
        assert response.json()["profile"]["total_volume_ml"] == pytest.approx(110.0)

    async def test_optimizing_a_stored_recipe_does_not_overwrite_it(
        self, client: AsyncClient, rum_id: str, lime_id: str, syrup_id: str
    ) -> None:
        """Ottimizzare è una consultazione, salvare è una decisione separata."""
        recipe_id = (
            await client.post(
                f"{API}/recipes", json=daiquiri_payload(rum_id, lime_id, syrup_id, (50, 15, 35))
            )
        ).json()["id"]

        optimized = await client.post(
            f"{API}/recipes/{recipe_id}/optimize",
            json={"target": {"abv": 0.16, "brix": 10.0}},
        )
        assert optimized.status_code == 200
        assert optimized.json()["recipe"]["ingredients"][0]["volume_ml"] != 50

        unchanged = await client.get(f"{API}/recipes/{recipe_id}")
        assert [item["volume_ml"] for item in unchanged.json()["ingredients"]] == [50, 15, 35]

    async def test_deleting_an_unknown_recipe_is_a_404(self, client: AsyncClient) -> None:
        response = await client.delete(f"{API}/recipes/{uuid.uuid4()}")
        assert response.status_code == 404
