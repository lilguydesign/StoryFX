"""Closed synthetic evidence; no owner credentials, SSH or notifications."""
from storyfx_scheduler_recovery_probe import evaluate


def test_no_evidence_is_unknown():
    assert evaluate(None)['status'] == 'unknown'


def test_owner_stop_is_disabled_and_error_pause_is_incident():
    assert evaluate({'enabled': False, 'wait_reason': '', 'read_only': True})['status'] == 'disabled'
    assert evaluate({'enabled': False, 'wait_reason': 'CONTROL_UNAVAILABLE', 'read_only': True})['status'] == 'incident'


def test_bounded_wait_is_not_publication_success():
    result = evaluate({'enabled': True, 'wait_reason': 'AUTH_UNAVAILABLE',
                       'next_check_in_seconds': 30, 'read_only': True})
    assert result['status'] == 'waiting'
    assert result['real_send_triggered'] is False and result['total_autonomy_verified'] is False
    assert not result['notifications_sent']


def test_stale_wait_is_an_incident():
    for remaining in (None, -61, 301):
        assert evaluate({'enabled': True, 'wait_reason': 'RATE_LIMITED',
                         'next_check_in_seconds': remaining, 'read_only': True})['status'] == 'incident'


def test_active_scheduler_does_not_prove_autonomy():
    result = evaluate({'enabled': True, 'wait_reason': '', 'read_only': True})
    assert result['status'] == 'ok' and not result['total_autonomy_verified']
