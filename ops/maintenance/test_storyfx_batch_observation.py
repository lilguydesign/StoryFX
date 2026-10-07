import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('batch_observation',
    Path(__file__).with_name('storyfx_batch_observation.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def snapshot(now, rows):
    return {'observed_unix': now, 'rows': rows, 'scheduler': {'enabled': True}}


def row(**values):
    return {'device': 'Validation technique', 'platform': 'WhatsApp',
            'system': 'Validation technique', 'count': 9, 'due_at': '1970-01-01T00:01:40Z',
            'supported': True, 'state': 'PLANNED', **values}


def test_no_due_activity_is_not_success_or_failure():
    result = probe.observe(snapshot(50, []), 0, 100)
    assert result['totals'] == {} and not result['all_scheduled_rows_confirmed']
    assert not result['window_elapsed'] and not result['real_send_triggered_by_observer']


def test_uncertain_send_is_never_a_confirmed_batch():
    result = probe.observe(snapshot(1200, [row(state='NEEDS_REVIEW')]), 0, 200)
    assert result['totals'] == {'needs_review': 1} and not result['all_scheduled_rows_confirmed']


def test_unsupported_facebook_is_not_hidden_by_successful_whatsapp():
    values = [row(state='CONFIRMED'), row(platform='Facebook', supported=False)]
    result = probe.observe(snapshot(1200, values), 0, 200)
    assert result['totals'] == {'confirmed': 1, 'not_validated': 1}
    assert not result['all_scheduled_rows_confirmed'] and not result['total_autonomy_verified']


def test_late_only_after_due_plus_grace_and_excludes_other_windows():
    assert probe.observe(snapshot(999, [row()]), 0, 200)['totals'] == {'waiting': 1}
    assert probe.observe(snapshot(1001, [row()]), 0, 200)['totals'] == {'late': 1}
    assert probe.observe(snapshot(1200, [row()]), 200, 300)['rows'] == []


def test_confirmed_count_and_elapsed_window_do_not_prove_unplugged_sleep():
    result = probe.observe(snapshot(1200, [row(state='CONFIRMED', count=11)]), 0, 200)
    assert result['all_scheduled_rows_confirmed'] and result['rows'][0]['count'] == 11
    assert not result['total_autonomy_verified']
