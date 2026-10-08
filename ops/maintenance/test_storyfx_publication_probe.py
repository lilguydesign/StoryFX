"""Synthetic outcome checks; no phone, server connection or notification."""
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from storyfx_publication_probe import collect, evaluate, read_state


def evidence(**totals):
    return {'read_only': True, 'start_unix': 100, 'end_unix': 10000, 'complete': False,
            'observations': [{'read_only': True, 'real_send_triggered_by_observer': False,
                              'observed_unix': 1000, 'scheduler_enabled': True,
                              'whatsapp_scope_violation': False, 'totals': totals}]}


class PublicationProbe(unittest.TestCase):
    def test_fresh_failures_are_incidents_even_with_confirmations(self):
        result = evaluate(evidence(confirmed_agent=3, failed_before_send=8), 1001)
        self.assertEqual(result['status'], 'incident')
        self.assertEqual(result['reason_code'], 'STORYFX_PUBLICATION_FAILED_BEFORE_SEND')

    def test_uncertain_has_priority_and_never_dispatches(self):
        result = evaluate(evidence(confirmed_agent=3, failed_before_send=8, uncertain=1,
                                   adapter_not_validated=46), 1001)
        self.assertEqual(result['reason_code'], 'STORYFX_PUBLICATION_UNCERTAIN')
        self.assertFalse(result['real_send_triggered'])
        self.assertFalse(result['notifications_sent'])
        self.assertEqual(result['metrics']['totals']['failed_before_send'], 8)

    def test_late_supported_occurrence_is_incident(self):
        self.assertEqual(evaluate(evidence(late=1), 1000)['reason_code'], 'STORYFX_PUBLICATION_LATE')

    def test_unsupported_is_excluded_not_claimed_healthy(self):
        result = evaluate(evidence(adapter_not_validated=44), 1000)
        self.assertEqual(result['status'], 'waiting')
        self.assertFalse(result['metrics']['publication_verified'])

    def test_no_activity_and_waiting_are_normal(self):
        self.assertEqual(evaluate(evidence(), 1000)['status'], 'waiting')
        self.assertEqual(evaluate(evidence(waiting=2), 1000)['status'], 'waiting')

    def test_only_confirmations_never_establish_delivery_or_autonomy(self):
        result = evaluate(evidence(confirmed_agent=1, confirmed_legacy_unverified_count=1), 1000)
        self.assertEqual(result['status'], 'ok')
        self.assertFalse(result['metrics']['publication_verified'])
        self.assertFalse(result['metrics']['total_autonomy_verified'])

    def test_freshness_boundary(self):
        self.assertEqual(evaluate(evidence(), 3400)['status'], 'waiting')
        self.assertEqual(evaluate(evidence(), 3401)['reason_code'], 'STORYFX_PUBLICATION_PROOF_STALE')

    def test_scope_violation_has_priority(self):
        value = evidence(uncertain=1)
        value['observations'][-1]['whatsapp_scope_violation'] = True
        self.assertEqual(evaluate(value, 1000)['reason_code'], 'STORYFX_SCOPE_CHANGED')

    def test_unsafe_observer_is_incident(self):
        value = evidence()
        value['observations'][-1]['real_send_triggered_by_observer'] = True
        self.assertEqual(evaluate(value, 1000)['reason_code'], 'STORYFX_OBSERVER_BOUNDARY_INVALID')

    def test_disabled_scheduler_alone_is_not_an_incident(self):
        value = evidence(outside_active_scheduler=2)
        value['observations'][-1]['scheduler_enabled'] = False
        self.assertEqual(evaluate(value, 1000)['status'], 'waiting')

    def test_manual_recipe_hold_is_normal_but_does_not_hide_other_incidents(self):
        self.assertEqual(evaluate(evidence(manual_recipe_hold=5), 1000)['status'], 'waiting')
        for counts, reason in (({'late': 1}, 'STORYFX_PUBLICATION_LATE'),
                               ({'uncertain': 1}, 'STORYFX_PUBLICATION_UNCERTAIN'),
                               ({'failed_before_send': 1}, 'STORYFX_PUBLICATION_FAILED_BEFORE_SEND')):
            with self.subTest(counts=counts):
                self.assertEqual(evaluate(evidence(manual_recipe_hold=5, **counts), 1000)['reason_code'], reason)

    def test_completed_observation_retains_unresolved_incidents(self):
        value = evidence(uncertain=1)
        value['complete'] = True
        value['observations'][-1]['observed_unix'] = 10900
        self.assertEqual(evaluate(value, 99999)['reason_code'], 'STORYFX_PUBLICATION_UNCERTAIN')
        value['observations'][-1]['totals'] = {}
        self.assertEqual(evaluate(value, 99999)['status'], 'waiting')

    def test_completion_cannot_hide_a_stale_unfinished_window(self):
        value = evidence()
        value['complete'] = True
        self.assertEqual(evaluate(value, 99999)['reason_code'], 'STORYFX_PUBLICATION_WINDOW_INVALID')

    def test_invalid_shape_and_unknown_verdict_are_not_success(self):
        for value in (None, {}, {'read_only': True, 'observations': [None]},
                      evidence(uncertain=-1), evidence(uncertain=True), evidence(new_verdict=1)):
            with self.subTest(value=value):
                self.assertEqual(evaluate(value, 1000)['status'], 'unknown')

    def test_private_input_is_never_echoed(self):
        value = evidence(uncertain=1)
        value['observations'][-1].update(profile='PRIVATE_PROFILE', token='PRIVATE_TOKEN',
                                         rows=[{'album': 'PRIVATE_ALBUM'}])
        original = copy.deepcopy(value)
        output = json.dumps(evaluate(value, 1000))
        self.assertNotIn('PRIVATE_', output)
        self.assertEqual(value, original)

    def test_read_only_file_and_missing_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'observation.json'
            path.write_text(json.dumps(evidence(failed_before_send=1)), encoding='utf-8')
            before = path.read_bytes()
            result = collect(datetime.fromtimestamp(1000, timezone.utc), path=path)
            self.assertEqual(result['status'], 'incident')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(read_state(path)['observations'][0]['totals'], {'failed_before_send': 1})
            self.assertEqual(collect(1000, path=path.with_name('missing'))['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
