"""Transient outages defer dispatch; authorization/configuration stops remain final."""
import pytest
from test_private_auth import private
from test_control_scheduler import setup
from storyfx_server.control_scheduler_waits import SchedulerWaits
from storyfx_server.store import DomainError


def row(app):
    with app.state.store.transaction() as db:
        return dict(db.execute('SELECT * FROM control_schedulers').fetchone())


def jobs(app):
    with app.state.store.transaction() as db:
        return [dict(r) for r in db.execute('SELECT id,state FROM control_jobs ORDER BY id')]


def start(private):
    app, browser, provider, now, _, body = setup(private)
    from test_control_center import HEADERS
    result = browser.post('/v1/control/scheduler/start', headers=HEADERS,
                          json={**body, 'mode': 'auto'})
    assert result.status_code == 200
    return app, browser, provider, now


@pytest.mark.parametrize('code,status', [('AUTH_UNAVAILABLE', 503), ('RATE_LIMITED', 429)])
def test_outage_backoff_is_durable_and_no_dispatch_before_live_revalidation(private, code, status):
    app, _, provider, now = start(private)
    scheduler = app.state.control_scheduler
    original = provider.owner
    calls = []

    def unavailable(_access):
        calls.append(1)
        raise DomainError(code, status)

    provider.owner = unavailable
    before = jobs(app)
    now[0] += 60
    scheduler.tick()
    assert row(app)['enabled'] and row(app)['wait_reason'] == code
    assert jobs(app) == before
    wait = SchedulerWaits(scheduler.broker)  # Recreated worker retains its deadline.
    assert not wait.due(row(app))
    scheduler.tick()
    assert len(calls) == 1 and jobs(app) == before
    now[0] += 30
    scheduler.tick()
    assert len(calls) == 2
    provider.owner = original
    now[0] += 59
    scheduler.tick()
    assert row(app)['wait_reason'] == code
    now[0] += 1
    scheduler.tick()
    assert row(app)['enabled'] and not row(app)['wait_reason']
    assert jobs(app) == before  # No historical catch-up or failed/uncertain replay.
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_scheduler_waits').fetchone()[0] == 0
        kinds = [r[0] for r in db.execute('SELECT kind FROM control_events')]
    assert kinds.count('SCHEDULER_CONTROL_WAITING') == 1
    assert kinds.count('SCHEDULER_CONTROL_RESUMED') == 1


@pytest.mark.parametrize('code,status,reason', [
    ('OWNER_ACCESS_REQUIRED', 403, 'OWNER_ACCESS_REQUIRED'),
    ('UNAUTHORIZED', 401, 'OWNER_ACCESS_REQUIRED'),
    ('PRIVATE_RECEIPT_INVALID', 503, 'CONTROL_UNAVAILABLE'),
])
def test_security_and_unclassified_failures_still_pause(private, code, status, reason):
    app, _, provider, _ = start(private)

    def denied(_access):
        raise DomainError(code, status)

    provider.owner = denied
    app.state.control_scheduler.tick()
    assert not row(app)['enabled'] and row(app)['wait_reason'] == reason


def test_owner_stop_during_outage_is_never_reactivated(private):
    app, _, _, now = start(private)
    scheduler = app.state.control_scheduler
    before = row(app)
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_schedulers SET enabled=0')
    assert scheduler.waits.defer(before, DomainError('AUTH_UNAVAILABLE', 503))
    now[0] += 3600
    scheduler.tick()
    assert not row(app)['enabled']
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_scheduler_waits').fetchone()[0] == 0


def test_wait_preserves_queued_jobs_and_bounds_retry_interval(private):
    from test_control_center import HEADERS
    app, browser, _, now, _, body = setup(private)
    result = browser.post('/v1/control/scheduler/start', headers=HEADERS,
                          json={**body, 'mode': 'manual'})
    assert result.status_code == 200
    scheduler = app.state.control_scheduler
    before = jobs(app)
    assert len(before) == 2 and all(j['state'] == 'QUEUED' for j in before)
    for expected in (30, 60, 120, 240, 300, 300):
        assert scheduler.waits.defer(row(app), DomainError('AUTH_UNAVAILABLE', 503))
        with app.state.store.transaction() as db:
            next_check = db.execute('SELECT next_check FROM control_scheduler_waits').fetchone()[0]
        assert next_check - now[0] == expected
        assert jobs(app) == before
        now[0] = next_check
