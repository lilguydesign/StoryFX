"""Authenticated settings and Windows bridge routes, separate from Android diagnostics."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import Field
from .control_models import Strict, Change, Removal, Launch
from .control_catalog import Catalog
from .control_broker import Broker
from .models import Empty


class PairStart(Strict):
    name: str = Field(min_length=1, max_length=80)
    proof: str = Field(pattern=r'^[A-Za-z0-9_-]{43,128}$')


class PairPoll(Strict):
    request_id: UUID
    proof: str = Field(pattern=r'^[A-Za-z0-9_-]{43,128}$')


class PairApprove(Strict):
    request_id: UUID


class Contact(Strict):
    profiles: list[str] = Field(max_length=100)


class Completion(Strict):
    state: Literal['CONFIRMED', 'NEEDS_REVIEW', 'FAILED_BEFORE_PUBLICATION']
    evidence: Literal['own_status_verified', 'provider_ui_verified', 'result_uncertain', 'preflight_refused']


def build_control_router(store, sessions, owner, credential):
    router = APIRouter(prefix='/v1/control')
    catalog = Catalog(store)
    broker = Broker(store, catalog, sessions)

    def node(token=Depends(credential)):
        return broker.authenticate(token)

    @router.get('')
    def snapshot(user=Depends(owner)):
        return broker.snapshot(user)

    @router.post('/settings/{collection}')
    def create(collection: str, body: Change, user=Depends(owner)):
        return catalog.write(user, collection, body)

    @router.put('/settings/{collection}/{item_id}')
    def update(collection: str, item_id: UUID, body: Change, user=Depends(owner)):
        return catalog.write(user, collection, body, str(item_id))

    @router.post('/settings/{collection}/{item_id}/remove')
    def remove(collection: str, item_id: UUID, body: Removal, user=Depends(owner)):
        return catalog.remove(user, collection, str(item_id), body.revision)

    @router.post('/launch')
    def launch(body: Launch, user=Depends(owner)):
        return broker.launch(user, body)

    @router.post('/windows/start')
    def start(body: PairStart):
        return broker.begin(body.name, body.proof)

    @router.post('/windows/poll')
    def poll(body: PairPoll):
        return broker.poll(str(body.request_id), body.proof)

    @router.post('/windows/approve')
    def approve(body: PairApprove, user=Depends(owner)):
        return broker.approve(user, str(body.request_id))

    @router.post('/windows/heartbeat')
    def heartbeat(body: Contact, executor=Depends(node)):
        return broker.heartbeat(executor, body.profiles)

    @router.post('/windows/claim')
    def claim(_body: Empty, executor=Depends(node)):
        return broker.claim(executor)

    @router.post('/windows/jobs/{job_id}/complete')
    def complete(job_id: UUID, body: Completion, executor=Depends(node)):
        return broker.complete(executor, str(job_id), body.state, body.evidence)

    @router.post('/windows/jobs/{job_id}/ready')
    def ready(job_id: UUID, _body: Empty, executor=Depends(node)):
        return broker.ready(executor, str(job_id))

    return router
