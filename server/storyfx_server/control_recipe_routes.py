"""Owner/session/origin protected manual-validation endpoints."""
from typing import Literal
from uuid import UUID
from fastapi import Depends
from pydantic import Field, field_validator
from .control_models import Strict
from .models import Empty


class RecipeDraft(Strict):
    client_key: UUID
    revision: int = Field(ge=0)
    row_ids: list[UUID] = Field(min_length=1, max_length=30)
    executor: Literal['android']

    @field_validator('row_ids')
    @classmethod
    def unique(cls, values):
        if len(values) != len(set(values)):
            raise ValueError('RECIPE_DUPLICATE_ROW')
        return values


class RecipeStep(Strict):
    client_key: UUID


def mount_recipes(router, broker, owner):
    recipes = broker.recipes

    @router.get('/recipes')
    def listing(user=Depends(owner)):
        return recipes.list(user)

    @router.post('/recipes')
    def create(body: RecipeDraft, user=Depends(owner)):
        return recipes.create(user, body)

    @router.get('/recipes/{recipe_id}')
    def read(recipe_id: UUID, user=Depends(owner)):
        return recipes.read(user, str(recipe_id))

    @router.post('/recipes/{recipe_id}/start')
    def start(recipe_id: UUID, _body: Empty, user=Depends(owner)):
        return recipes.start(user, str(recipe_id))

    @router.post('/recipes/{recipe_id}/steps/{step_id}/launch')
    def launch(recipe_id: UUID, step_id: UUID, body: RecipeStep, user=Depends(owner)):
        return recipes.launch(user, str(recipe_id), str(step_id), body.client_key)

    @router.post('/recipes/{recipe_id}/cancel')
    def cancel(recipe_id: UUID, _body: Empty, user=Depends(owner)):
        return recipes.cancel(user, str(recipe_id))

    @router.post('/recipes/{recipe_id}/release')
    def release(recipe_id: UUID, _body: Empty, user=Depends(owner)):
        return recipes.release(user, str(recipe_id))
