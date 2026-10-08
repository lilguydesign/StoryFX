"""Synthetic recipe monitoring; no server, phone or publication is contacted."""
import copy
from datetime import datetime, timezone
import json
import unittest
from storyfx_manual_recipe_probe import collect, evaluate


def evidence(phase='ready', **updates):
    started = phase not in {'none', 'draft'}
    value = {'contract_version': 1, 'state': phase, 'started': started,
             'lock_held': started and phase != 'released', 'pending_attempts': 0,
             'external_pending': 0, 'total_steps': 0 if phase == 'none' else 2,
             'verified_steps': 0, 'failed_steps': 0, 'uncertain_steps': 0,
             'incomplete_proof_steps': 0, 'interval_violation_steps': 0,
             'next_allowed_at': None, 'automation_ready': False,
             'resume_not_before': None, 'scheduler_enabled': True}
    value.update(updates)
    return {'read_only': True, 'complete': False, 'observations': [
        {'observed_unix': 1000, 'read_only': True, 'scheduler_enabled': True,
         'real_send_triggered_by_observer': False, 'manual_validation': value}]}


class ManualRecipeProbe(unittest.TestCase):
    def test_fresh_explicit_none_is_normal_not_missing_coverage(self):
        result = evaluate(evidence('none'), 1000)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['reason_code'], 'STORYFX_RECIPE_NOT_CONFIGURED')

    def test_missing_schema_or_read_is_unknown(self):
        value = evidence()
        del value['observations'][0]['manual_validation']
        self.assertEqual(evaluate(value, 1000)['status'], 'unknown')
        self.assertEqual(collect(1000, read=lambda _path: None)['status'], 'unknown')
        def denied(_path):
            raise OSError('PRIVATE_ERROR_VALUE')
        result = collect(1000, read=denied)
        self.assertEqual(result['status'], 'unknown')
        self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_inert_draft_and_manual_waiting_have_no_overdue_incident(self):
        for phase in ('draft', 'ready', 'cooldown', 'draining', 'in_progress', 'cancelled', 'released'):
            with self.subTest(phase=phase):
                value = evidence(phase, next_allowed_at='1970-01-01T00:05:00Z')
                value['observations'][0]['observed_unix'] = 900000
                self.assertEqual(evaluate(value, 900000)['status'], 'waiting')

    def test_draining_external_work_is_normal_without_invented_deadline(self):
        result = evaluate(evidence('draining', pending_attempts=5, external_pending=5), 1000)
        self.assertEqual(result['reason_code'], 'STORYFX_RECIPE_DRAINING')
        self.assertEqual(result['status'], 'waiting')

    def test_failed_uncertain_incomplete_or_interval_are_incidents(self):
        expected = {'failed_steps': 'STORYFX_RECIPE_FAILED', 'uncertain_steps': 'STORYFX_RECIPE_UNCERTAIN',
                    'incomplete_proof_steps': 'STORYFX_RECIPE_PROOF_INCOMPLETE',
                    'interval_violation_steps': 'STORYFX_RECIPE_INTERVAL_VIOLATION'}
        for field, reason in expected.items():
            with self.subTest(field=field):
                result = evaluate(evidence('blocked', **{field: 1}), 1000)
                self.assertEqual(result['status'], 'incident')
                self.assertEqual(result['reason_code'], reason)

    def test_blocked_without_counter_is_still_visible(self):
        self.assertEqual(evaluate(evidence('blocked'), 1000)['reason_code'], 'STORYFX_RECIPE_BLOCKED')

    def test_lock_invariants_reject_missing_active_and_spurious_draft_locks(self):
        for value in (evidence('ready', lock_held=False), evidence('draft', lock_held=True),
                      evidence('released', lock_held=True), evidence('ready', automation_ready=True),
                      evidence('cancelled', lock_held=False)):
            with self.subTest(value=value):
                self.assertEqual(evaluate(value, 1000)['reason_code'], 'STORYFX_RECIPE_LOCK_INCONSISTENT')

    def test_cancelled_draft_does_not_require_lock(self):
        self.assertEqual(evaluate(evidence('cancelled', started=False, lock_held=False), 1000)['status'], 'waiting')

    def test_scheduler_enabled_under_lock_or_after_explicit_restart_is_not_failure(self):
        for phase in ('ready', 'released'):
            with self.subTest(phase=phase):
                self.assertEqual(evaluate(evidence(phase), 1000)['status'], 'waiting')

    def test_passed_requires_complete_count_and_no_pending_attempt(self):
        result = evaluate(evidence('passed', verified_steps=2), 1000)
        self.assertEqual(result['status'], 'ok')
        self.assertFalse(result['metrics']['total_autonomy_verified'])
        self.assertFalse(result['metrics']['account_identity_verified'])
        for updates in ({'verified_steps': 1}, {'verified_steps': 2, 'pending_attempts': 1},
                        {'total_steps': 0, 'verified_steps': 0}):
            self.assertEqual(evaluate(evidence('passed', **updates), 1000)['reason_code'],
                             'STORYFX_RECIPE_PASS_INCONSISTENT')

    def test_stale_completed_window_is_not_current_recipe_evidence(self):
        value = evidence('none')
        value['complete'] = True
        self.assertEqual(evaluate(value, 3400)['status'], 'ok')
        self.assertEqual(evaluate(value, 3401)['reason_code'], 'STORYFX_RECIPE_PROOF_STALE')
        self.assertEqual(evaluate(value, 999)['reason_code'], 'STORYFX_RECIPE_CLOCK_INVALID')

    def test_shape_flags_counters_and_dates_are_strict(self):
        for updates in ({'contract_version': True}, {'contract_version': 2}, {'state': 'PRIVATE_UNKNOWN'},
                        {'lock_held': 1}, {'uncertain_steps': True}, {'failed_steps': -1},
                        {'verified_steps': 3}, {'external_pending': 1},
                        {'next_allowed_at': 'PRIVATE_DATE'}, {'next_allowed_at': '1970-01-01T00:00:00'},
                        {'resume_not_before': False}, {'scheduler_enabled': False}):
            with self.subTest(updates=updates):
                result = evaluate(evidence(**updates), 1000)
                self.assertEqual(result['status'], 'unknown')
                self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_boundary_flags_cannot_be_hidden(self):
        value = evidence()
        value['observations'][0]['real_send_triggered_by_observer'] = True
        self.assertEqual(evaluate(value, 1000)['status'], 'incident')

    def test_only_closed_fields_leave_probe_and_input_is_unchanged(self):
        value = evidence('passed', verified_steps=2)
        value['observations'][0]['manual_validation'].update(album='PRIVATE_ALBUM', token='PRIVATE_TOKEN')
        value['observations'][0]['rows'] = [{'profile': 'PRIVATE_PROFILE'}]
        before = copy.deepcopy(value)
        result = collect(datetime.fromtimestamp(1000, timezone.utc), read=lambda _path: value)
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertEqual(before, value)
        for field in ('notifications_sent', 'business_mutations', 'real_send_triggered'):
            self.assertIs(result[field], False)


if __name__ == '__main__':
    unittest.main()
