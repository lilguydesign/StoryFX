"""Closed, owner-scoped attempt evidence; no screen text, media or device identities."""
import json
from typing import Literal
from pydantic import Field, StrictBool
from .control_models import Strict
from .control_media_modes import media_count
from .store import DomainError


class AttemptDiagnostics(Strict):
    stage: Literal['preflight', 'album_media_unavailable', 'provider_not_ready',
                   'updates_navigation_failed', 'own_status_unavailable',
                   'share_selection_refused', 'contacts_preview_refused',
                   'own_status_verification', 'complete']
    app_version: str = Field(pattern=r'^\d+\.\d+\.\d+$', max_length=32)
    expected_count: int = Field(strict=True, ge=1, le=30)
    selected_count: int | None = Field(default=None, strict=True, ge=0, le=30)
    verified_count: int | None = Field(default=None, strict=True, ge=0, le=30)
    elapsed_ms: int = Field(strict=True, ge=0, le=900000)
    service_ready: StrictBool
    network: Literal['unknown', 'offline', 'wifi', 'cellular', 'other'] = 'unknown'
    provider_package: Literal['whatsapp_business', 'unknown'] = 'unknown'
    account_verified: StrictBool = False
    verification_method: Literal['none', 'recent_rows', 'recent_visible'] = 'none'
    navigation_state: Literal['unknown', 'provider_pending', 'updates_home',
                              'own_list', 'updates_tab', 'conversation'] = 'unknown'
    own_label_count: int = Field(default=0, strict=True, ge=0, le=2500)


def quantified_batch(value, expected):
    return bool(value and value.get('expected_count') == expected
                and value.get('selected_count') == expected
                and value.get('verified_count') == expected
                and value.get('provider_package') == 'whatsapp_business'
                and value.get('verification_method') in {'recent_rows', 'recent_visible'})


class AttemptEvidence:
    def __init__(self, store):
        self.store = store
        with store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS control_attempt_diagnostics (
              job_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, recorded REAL NOT NULL,
              value TEXT NOT NULL)''')

    def save(self, db, row, state, evidence, diagnostics):
        if diagnostics is None:
            return
        value = diagnostics.model_dump()
        payload = json.loads(row['payload'])
        if (value['expected_count'] != media_count(payload)
                or state == 'CONFIRMED' and not quantified_batch(value, media_count(payload))):
            raise DomainError('PUBLICATION_DIAGNOSTICS_INVALID', 422)
        prior = db.execute('SELECT value FROM control_attempt_diagnostics WHERE job_id=? AND owner_id=?',
                           (row['id'], row['owner_id'])).fetchone()
        if prior:
            if json.loads(prior['value']) != value or row['state'] != state or row['evidence'] != evidence:
                raise DomainError('PUBLICATION_RESULT_ALREADY_RECORDED', 409)
            return
        # Old final reports must not acquire later observations disguised as failure evidence.
        if row['completed'] is not None:
            raise DomainError('PUBLICATION_RESULT_ALREADY_RECORDED', 409)
        db.execute('INSERT INTO control_attempt_diagnostics VALUES (?,?,?,?)',
                   (row['id'], row['owner_id'], self.store.clock(), json.dumps(value)))

    def attach(self, db, reports, owner):
        values = {row['job_id']: json.loads(row['value']) for row in db.execute(
            'SELECT job_id,value FROM control_attempt_diagnostics WHERE owner_id=?', (owner,))}
        for report in reports:
            payload = report['publication']
            diagnostics = values.get(report['id'])
            expected = media_count(payload)
            report.update(diagnostics=diagnostics, scheduled_at=payload['due_at'],
                          timezone='Africa/Douala', expected_media_count=expected,
                          batch_count_verified=report['state'] == 'CONFIRMED' and
                          quantified_batch(diagnostics, expected),
                          account_verified=bool(diagnostics and diagnostics.get('account_verified')),
                          attempt_id=report['id'], parent_attempt_id=payload.get('retry_parent'),
                          page_reference=payload.get('page') or None)


def schedule_status(value, snapshot):
    """An unsupported occurrence stays visible without making a reservation."""
    from .control_executor_status import executor_wait_reason
    reason = executor_wait_reason(snapshot, value)
    availability = ('ALREADY_REQUESTED' if value['state'] != 'PLANNED' else
                    'NOT_SUPPORTED' if reason == 'ADAPTER_NOT_VALIDATED' else
                    'READY' if reason == 'READY' else 'WAITING_EXECUTOR')
    return {'availability': availability, 'wait_reason': reason}
