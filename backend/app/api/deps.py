"""Composition root: qui si decide quale implementazione soddisfa quale porta.

È l'unico punto del progetto in cui i tre layer si toccano. Le annotazioni
di ritorno dichiarano le **porte di dominio** (`IngredientRepository`,
`UnitOfWork`), non le classi concrete: è così che MyPy verifica
staticamente che gli adapter SQLAlchemy rispettino i Protocol, senza che
questi ultimi debbano essere ereditati. Se un metodo cambia firma da una
parte e non dall'altra, il type check fallisce qui.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.solver.balancing_solver import BalancingSolver
from app.application.use_cases.balancing import (
    CalculateBalanceUseCase,
    CalculateStoredRecipeBalanceUseCase,
    OptimizeRecipeUseCase,
    OptimizeStoredRecipeUseCase,
)
from app.application.use_cases.glassware import ListGlasswareUseCase
from app.application.use_cases.ingredients import (
    CreateIngredientUseCase,
    DeleteIngredientUseCase,
    GetIngredientUseCase,
    ListIngredientsUseCase,
)
from app.application.use_cases.matching import (
    DescribeFlavorGraphUseCase,
    FindFlavorBridgeUseCase,
    FindSubstitutesUseCase,
    FlavorGraphProvider,
    SuggestPairingsUseCase,
)
from app.application.use_cases.recipes import (
    CreateRecipeUseCase,
    DeleteRecipeUseCase,
    GetRecipeUseCase,
    ListRecipesUseCase,
    UpdateRecipeUseCase,
)
from app.core.config import get_settings
from app.domain.matching import FlavorSearchRepository, GraphSnapshotCache
from app.domain.repositories import IngredientRepository, RecipeRepository, UnitOfWork
from app.infrastructure.cache import NullGraphSnapshotCache, RedisGraphSnapshotCache
from app.infrastructure.db.repositories import (
    SqlAlchemyFlavorSearchRepository,
    SqlAlchemyIngredientRepository,
    SqlAlchemyRecipeRepository,
    SqlAlchemyUnitOfWork,
)
from app.infrastructure.db.session import session_scope
from app.infrastructure.redis_client import redis_scope

# --- Risorse di infrastruttura ------------------------------------------


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in session_scope():
        yield session


async def get_redis() -> AsyncGenerator[Redis | None, None]:
    """Il client Redis, oppure `None` se Redis non è configurato.

    Il controllo sta qui e non in `redis_scope`: decidere se una risorsa
    esiste è compito del composition root, e così il pool non viene mai
    costruito su un URL assente.
    """
    if get_settings().redis_url is None:
        yield None
        return
    async for client in redis_scope():
        yield client


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis | None, Depends(get_redis)]


# --- Porte ---------------------------------------------------------------


def get_ingredient_repository(session: SessionDep) -> IngredientRepository:
    return SqlAlchemyIngredientRepository(session)


def get_recipe_repository(session: SessionDep) -> RecipeRepository:
    return SqlAlchemyRecipeRepository(session)


def get_unit_of_work(session: SessionDep) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_flavor_search_repository(session: SessionDep) -> FlavorSearchRepository:
    return SqlAlchemyFlavorSearchRepository(session)


def get_graph_cache(redis: RedisDep) -> GraphSnapshotCache:
    if redis is None:
        return NullGraphSnapshotCache()
    return RedisGraphSnapshotCache(redis)


IngredientRepoDep = Annotated[IngredientRepository, Depends(get_ingredient_repository)]
RecipeRepoDep = Annotated[RecipeRepository, Depends(get_recipe_repository)]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
FlavorSearchDep = Annotated[FlavorSearchRepository, Depends(get_flavor_search_repository)]
GraphCacheDep = Annotated[GraphSnapshotCache, Depends(get_graph_cache)]


# --- Servizi applicativi --------------------------------------------------


@lru_cache(maxsize=1)
def get_solver() -> BalancingSolver:
    """Il solver è stateless: una sola istanza serve tutto il processo."""
    return BalancingSolver()


SolverDep = Annotated[BalancingSolver, Depends(get_solver)]


# --- Casi d'uso -----------------------------------------------------------


def get_create_ingredient_use_case(
    ingredients: IngredientRepoDep, uow: UnitOfWorkDep
) -> CreateIngredientUseCase:
    return CreateIngredientUseCase(ingredients, uow)


def get_get_ingredient_use_case(ingredients: IngredientRepoDep) -> GetIngredientUseCase:
    return GetIngredientUseCase(ingredients)


def get_list_ingredients_use_case(ingredients: IngredientRepoDep) -> ListIngredientsUseCase:
    return ListIngredientsUseCase(ingredients)


def get_delete_ingredient_use_case(
    ingredients: IngredientRepoDep, uow: UnitOfWorkDep
) -> DeleteIngredientUseCase:
    return DeleteIngredientUseCase(ingredients, uow)


def get_create_recipe_use_case(
    recipes: RecipeRepoDep, ingredients: IngredientRepoDep, uow: UnitOfWorkDep
) -> CreateRecipeUseCase:
    return CreateRecipeUseCase(recipes, ingredients, uow)


def get_get_recipe_use_case(recipes: RecipeRepoDep) -> GetRecipeUseCase:
    return GetRecipeUseCase(recipes)


def get_list_recipes_use_case(recipes: RecipeRepoDep) -> ListRecipesUseCase:
    return ListRecipesUseCase(recipes)


def get_update_recipe_use_case(
    recipes: RecipeRepoDep, ingredients: IngredientRepoDep, uow: UnitOfWorkDep
) -> UpdateRecipeUseCase:
    return UpdateRecipeUseCase(recipes, ingredients, uow)


def get_delete_recipe_use_case(recipes: RecipeRepoDep, uow: UnitOfWorkDep) -> DeleteRecipeUseCase:
    return DeleteRecipeUseCase(recipes, uow)


def get_calculate_balance_use_case(ingredients: IngredientRepoDep) -> CalculateBalanceUseCase:
    return CalculateBalanceUseCase(ingredients)


def get_calculate_stored_balance_use_case(
    recipes: RecipeRepoDep,
) -> CalculateStoredRecipeBalanceUseCase:
    return CalculateStoredRecipeBalanceUseCase(recipes)


def get_optimize_recipe_use_case(
    ingredients: IngredientRepoDep, solver: SolverDep
) -> OptimizeRecipeUseCase:
    return OptimizeRecipeUseCase(ingredients, solver)


def get_optimize_stored_recipe_use_case(
    recipes: RecipeRepoDep, solver: SolverDep
) -> OptimizeStoredRecipeUseCase:
    return OptimizeStoredRecipeUseCase(recipes, solver)


# --- Matcher organolettico -------------------------------------------------


def get_flavor_graph_provider(
    flavor_search: FlavorSearchDep, recipes: RecipeRepoDep, cache: GraphCacheDep
) -> FlavorGraphProvider:
    return FlavorGraphProvider(flavor_search, recipes, cache)


GraphProviderDep = Annotated[FlavorGraphProvider, Depends(get_flavor_graph_provider)]


def get_find_substitutes_use_case(
    ingredients: IngredientRepoDep, flavor_search: FlavorSearchDep
) -> FindSubstitutesUseCase:
    return FindSubstitutesUseCase(ingredients, flavor_search)


def get_suggest_pairings_use_case(provider: GraphProviderDep) -> SuggestPairingsUseCase:
    return SuggestPairingsUseCase(provider)


def get_find_bridge_use_case(
    ingredients: IngredientRepoDep, provider: GraphProviderDep
) -> FindFlavorBridgeUseCase:
    return FindFlavorBridgeUseCase(ingredients, provider)


def get_describe_graph_use_case(provider: GraphProviderDep) -> DescribeFlavorGraphUseCase:
    return DescribeFlavorGraphUseCase(provider)


def get_list_glassware_use_case() -> ListGlasswareUseCase:
    return ListGlasswareUseCase()
