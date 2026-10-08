"""Owner-only permission changes; neither pairing nor publication is implicit."""
from typing import Literal
from uuid import UUID
from fastapi import Depends
from pydantic import Field
from .control_models import Strict, Removal


class ProfileAssociation(Strict):
    client_key: UUID
    device_id: UUID
    profile_id: UUID
    revision: int = Field(ge=0)
    platform: Literal['Facebook']


def mount_profile_bindings(router, broker, owner):
    bindings = broker.android.profile_bindings

    @router.get('/android/profile-bindings')
    def listing(user=Depends(owner)):
        return bindings.listing(user)

    @router.post('/android/profile-bindings')
    def associate(body: ProfileAssociation, user=Depends(owner)):
        return bindings.add(user, body)

    @router.post('/android/profile-bindings/{binding_id}/remove')
    def remove(binding_id: UUID, body: Removal, user=Depends(owner)):
        return bindings.remove(user, str(binding_id), body.revision)
