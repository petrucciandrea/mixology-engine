"""Repository su PostgreSQL reale: mapping, vincoli, aggregate."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Recipe, RecipeIngredient
from app.domain.enums import (
    DilutionMethod,
    GlassType,
    IngredientCategory,
    RecipeFamily,
    ServingIce,
)
from app.domain.flavor import FlavorProfile
from app.domain.repositories import IngredientRepository, RecipeRepository, UnitOfWork

from .conftest import make_ingredient

pytestmark = pytest.mark.integration


class TestIngredientRepository:
    async def test_round_trip_preserves_every_field(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        original = make_ingredient(
            "Rum Agricole",
            IngredientCategory.SPIRIT,
            abv=0.50,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.93,
            flavor=FlavorProfile.from_descriptors(alcohol_heat=0.75, herbaceous=0.8, funky=0.6),
        )
        await ingredient_repository.add(original)
        await unit_of_work.commit()

        loaded = await ingredient_repository.get(original.id)

        assert loaded == original, "il mapping deve essere una biiezione"

    async def test_flavor_vector_survives_the_pgvector_column(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        """Il vettore va e torna da una colonna `vector(32)` senza perdite.

        È il test che dimostra che l'estensione è attiva e che la
        dimensione dichiarata nel dominio coincide con quella dello schema.
        """
        flavor = FlavorProfile.from_descriptors(sour=0.95, citrus=0.9, herbaceous=0.2)
        ingredient = make_ingredient("Lime", IngredientCategory.JUICE, flavor=flavor)
        await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        loaded = await ingredient_repository.get(ingredient.id)

        assert loaded is not None
        assert loaded.flavor_profile is not None
        assert loaded.flavor_profile.as_dict()["citrus"] == pytest.approx(0.9)
        assert loaded.flavor_profile.cosine_similarity(flavor) == pytest.approx(1.0, abs=1e-6)

    async def test_an_ingredient_without_a_profile_is_still_valid(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        """Si può inserire un ingrediente prima di averlo profilato.

        Resta usabile dal solver, che guarda solo le grandezze fisiche; è
        invisibile al matcher, non al bar.
        """
        ingredient = make_ingredient("Distillato Anonimo", flavor=None)
        await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        loaded = await ingredient_repository.get(ingredient.id)
        assert loaded is not None
        assert loaded.flavor_profile is None

    async def test_get_returns_none_for_an_unknown_id(
        self, ingredient_repository: IngredientRepository
    ) -> None:
        assert await ingredient_repository.get(str(uuid.uuid4())) is None

    async def test_get_many_loads_everything_in_one_pass(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        created = [make_ingredient(f"Ingrediente {index}") for index in range(3)]
        for ingredient in created:
            await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        loaded = await ingredient_repository.get_many([item.id for item in created])

        assert {item.id for item in loaded} == {item.id for item in created}

    async def test_get_many_is_empty_for_an_empty_request(
        self, ingredient_repository: IngredientRepository
    ) -> None:
        """Nessun id significa nessuna query, non una query senza filtri."""
        assert await ingredient_repository.get_many([]) == []

    async def test_the_unique_name_constraint_is_enforced_by_the_database(
        self, ingredient_repository: IngredientRepository, db_session: AsyncSession
    ) -> None:
        """L'ultima linea di difesa contro due richieste concorrenti.

        Il caso d'uso controlla prima di scrivere, ma fra il controllo e la
        scrittura può inserirsi un'altra transazione: solo il vincolo sul
        database chiude davvero la finestra.
        """
        first = make_ingredient("Gin Duplicato")
        await ingredient_repository.add(first)

        clash = make_ingredient("altro")
        clash = type(clash)(  # stesso nome, id diverso
            id=str(uuid.uuid4()),
            name=first.name,
            category=clash.category,
            physical_profile=clash.physical_profile,
        )
        with pytest.raises(IntegrityError):
            await ingredient_repository.add(clash)
        await db_session.rollback()

    async def test_listing_filters_by_category_and_activity(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        spirit = make_ingredient("Vodka", IngredientCategory.SPIRIT)
        syrup = make_ingredient("Sciroppo", IngredientCategory.SYRUP, abv=0.0, brix=50.0)
        await ingredient_repository.add(spirit)
        await ingredient_repository.add(syrup)
        await unit_of_work.commit()

        spirits = await ingredient_repository.list(category=IngredientCategory.SPIRIT, limit=200)
        spirit_ids = {item.id for item in spirits}

        assert spirit.id in spirit_ids
        assert syrup.id not in spirit_ids

    async def test_deactivated_ingredients_disappear_from_the_default_listing(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        from dataclasses import replace

        ingredient = make_ingredient("Amaro Fuori Listino", IngredientCategory.AMARO)
        await ingredient_repository.add(ingredient)
        await ingredient_repository.save(replace(ingredient, is_active=False))
        await unit_of_work.commit()

        active = await ingredient_repository.list(limit=200)
        everything = await ingredient_repository.list(active_only=False, limit=200)

        assert ingredient.id not in {item.id for item in active}
        assert ingredient.id in {item.id for item in everything}

    async def test_count_agrees_with_the_listing(
        self, ingredient_repository: IngredientRepository, unit_of_work: UnitOfWork
    ) -> None:
        before = await ingredient_repository.count(category=IngredientCategory.BITTER)
        await ingredient_repository.add(make_ingredient("Bitter", IngredientCategory.BITTER))
        await unit_of_work.commit()

        assert await ingredient_repository.count(category=IngredientCategory.BITTER) == before + 1


class TestRecipeRepository:
    async def _stock_daiquiri(
        self,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> Recipe:
        rum = make_ingredient("Rum", IngredientCategory.SPIRIT, abv=0.40, density_g_ml=0.95)
        lime = make_ingredient(
            "Lime", IngredientCategory.JUICE, abv=0.0, brix=7.5, acidity=6.0, density_g_ml=1.03
        )
        syrup = make_ingredient(
            "Sciroppo", IngredientCategory.SYRUP, abv=0.0, brix=50.0, density_g_ml=1.23
        )
        for ingredient in (rum, lime, syrup):
            await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        return Recipe(
            id=str(uuid.uuid4()),
            name="Daiquiri",
            dilution_method=DilutionMethod.SHAKEN,
            serving_ice=ServingIce.NONE,
            instructions="Shake con ghiaccio, doppio filtro, coppetta ghiacciata.",
            ingredients=(
                RecipeIngredient(ingredient=rum, volume_ml=60.0),
                RecipeIngredient(ingredient=lime, volume_ml=30.0),
                RecipeIngredient(ingredient=syrup, volume_ml=20.0),
            ),
        )

    async def test_an_aggregate_comes_back_whole(
        self,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        recipe = await self._stock_daiquiri(ingredient_repository, unit_of_work)
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded == recipe, "ricetta, dosaggi e ingredienti tornano identici"

    @pytest.mark.parametrize("serving_ice", list(ServingIce))
    async def test_serving_ice_survives_the_round_trip(
        self,
        serving_ice: ServingIce,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        recipe = replace(
            await self._stock_daiquiri(ingredient_repository, unit_of_work),
            serving_ice=serving_ice,
        )
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded is not None
        assert loaded.serving_ice is serving_ice

    @pytest.mark.parametrize("glass", [None, *GlassType])
    async def test_glass_survives_the_round_trip(
        self,
        glass: GlassType | None,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        recipe = replace(
            await self._stock_daiquiri(ingredient_repository, unit_of_work), glass=glass
        )
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded is not None
        assert loaded.glass is glass

    @pytest.mark.parametrize("family", [None, *RecipeFamily])
    async def test_family_survives_the_round_trip(
        self,
        family: RecipeFamily | None,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        recipe = replace(
            await self._stock_daiquiri(ingredient_repository, unit_of_work), family=family
        )
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded is not None
        assert loaded.family is family

    async def test_the_pouring_order_is_preserved(
        self,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """L'ordine non è cosmetico: il solver assegna i volumi per posizione."""
        recipe = await self._stock_daiquiri(ingredient_repository, unit_of_work)
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded is not None
        assert [item.ingredient.id for item in loaded.ingredients] == [
            item.ingredient.id for item in recipe.ingredients
        ]

    async def test_saving_replaces_the_dosage(
        self,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        recipe = await self._stock_daiquiri(ingredient_repository, unit_of_work)
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        rebalanced = recipe.with_volumes((55.0, 27.5, 15.0))
        await recipe_repository.save(rebalanced)
        await unit_of_work.commit()

        loaded = await recipe_repository.get(recipe.id)

        assert loaded is not None
        assert loaded.volumes_ml == (55.0, 27.5, 15.0)
        assert len(loaded.ingredients) == 3, "nessuna riga orfana lasciata indietro"

    async def test_deleting_a_recipe_removes_its_doses(
        self,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
        db_session: AsyncSession,
    ) -> None:
        recipe = await self._stock_daiquiri(ingredient_repository, unit_of_work)
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        assert await recipe_repository.delete(recipe.id) is True
        await unit_of_work.commit()

        assert await recipe_repository.get(recipe.id) is None

    async def test_deleting_an_unknown_recipe_reports_false(
        self, recipe_repository: RecipeRepository
    ) -> None:
        assert await recipe_repository.delete(str(uuid.uuid4())) is False

    async def test_an_ingredient_used_by_a_recipe_cannot_be_deleted(
        self,
        recipe_repository: RecipeRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
        db_session: AsyncSession,
    ) -> None:
        """La foreign key è RESTRICT, non CASCADE.

        Cancellare un ingrediente non deve svuotare in silenzio le ricette
        che lo usano: per toglierlo dal listino esiste la disattivazione.
        """
        recipe = await self._stock_daiquiri(ingredient_repository, unit_of_work)
        await recipe_repository.add(recipe)
        await unit_of_work.commit()

        used_ingredient_id = recipe.ingredients[0].ingredient.id
        with pytest.raises(IntegrityError):
            await ingredient_repository.delete(used_ingredient_id)
        await db_session.rollback()
