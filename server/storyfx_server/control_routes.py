"""Authenticated settings and Windows bridge routes, separate from Android diagnostics."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import Field
from .control_models import Strict, Change, Removal, Launch
from .control_catalog import Catalog
from .control_broker import Broker
from .models import Empty
from .control_scheduler import Scheduler
from .control_scheduler_models import Window, Schedule, Stop
from .control_result_proofs import Evidence
from .control_recovery import repeat, repeat_many


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
    evidence: Evidence


class Retry(Strict):
    revision: int = Field(ge=0)


class RetryBatch(Retry):
    jobs: list[UUID] = Field(min_length=1, max_length=20)


def build_control_router(store, sessions, owner, credential, agent):
    router = APIRouter(prefix='/v1/control')
    catalog = Catalog(store)
    broker = Broker(store, catalog, sessions)
    scheduler = Scheduler(broker)
    broker.scheduler = scheduler

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

    @router.post('/jobs/{job_id}/retry')
    def retry(job_id: UUID, body: Retry, user=Depends(owner)):
        return repeat(broker, user, str(job_id), body.revision)

    @router.post('/retry-batch')
    def retry_batch(body: RetryBatch, user=Depends(owner)):
        return repeat_many(broker, user, [str(value) for value in body.jobs], body.revision)

    @router.post('/catchup/preview')
    def catchup_preview(body: Window, user=Depends(owner)):
        return scheduler.preview(user,body)

    @router.post('/catchup/launch')
    def catchup_launch(body: Window, user=Depends(owner)):
        return scheduler.catchup(user,body)

    @router.post('/scheduler/start')
    def scheduler_start(body: Schedule, user=Depends(owner)):
        return scheduler.start(user,body)

    @router.post('/scheduler/stop')
    def scheduler_stop(_body: Empty, user=Depends(owner)):
        return scheduler.stop(user)

    @router.post('/stop')
    def stop(body: Stop, user=Depends(owner)):
        return scheduler.stop_jobs(user,body.stop_scheduler)

    @router.post('/terminal/clear')
    def clear_terminal(_body: Empty, user=Depends(owner)):
        return broker.terminal.clear(user)

    @router.post('/windows/settings')
    def windows_settings(_body: Empty, executor=Depends(node)):
        user = sessions.require_hash(executor['auth_session'])
        snapshot = catalog.read(user)
        return {'profiles':snapshot['collections']['profiles'],'revision':snapshot['revision']}

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

    from .control_android_routes import mount_android
    mount_android(router, broker, agent, Completion)
    return router, scheduler
