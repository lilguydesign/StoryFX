"""Native command access uses the existing installation credential and owner gate."""
from uuid import UUID
from fastapi import Depends
from pydantic import Field, StrictBool
from .control_models import Strict
from .models import Empty
from .store import DomainError


class Binding(Strict):
    profile: str = Field(min_length=1, max_length=100)
    enabled: StrictBool


class NativeContact(Strict):
    service_ready: StrictBool
    media_ready: StrictBool
    screen_locked: StrictBool
    app_version: str = Field(pattern=r'^\d+\.\d+\.\d+$', max_length=32)
    battery_percent: int | None = Field(default=None, ge=0, le=100)


def mount_android(router, broker, agent, completion):
    native = broker.android

    @router.post('/android/settings')
    def settings(_body: Empty, identity=Depends(agent)):
        return native.settings(identity)

    @router.post('/android/bind')
    def bind(body: Binding, identity=Depends(agent)):
        return native.bind(identity, body)

    @router.post('/android/heartbeat')
    def heartbeat(body: NativeContact, identity=Depends(agent)):
        return native.heartbeat(identity, body)

    @router.post('/android/claim')
    def claim(_body: Empty, identity=Depends(agent)):
        return broker.claim(native.node(identity))

    @router.post('/android/jobs/{job_id}/ready')
    def ready(job_id: UUID, _body: Empty, identity=Depends(agent)):
        return broker.ready(native.node(identity), str(job_id))

    @router.post('/android/jobs/{job_id}/complete')
    def complete(job_id: UUID, body: completion, identity=Depends(agent)):
        proofs = {'CONFIRMED': 'own_status_verified', 'NEEDS_REVIEW': 'result_uncertain',
                  'FAILED_BEFORE_PUBLICATION': 'preflight_refused'}
        if proofs.get(body.state) != body.evidence:
            raise DomainError('ANDROID_RESULT_INVALID', 422)
        return broker.complete(native.node(identity, require_ready=False), str(job_id), body.state, body.evidence)
