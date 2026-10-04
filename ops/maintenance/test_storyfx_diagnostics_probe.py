"""Synthetic health/queue fixtures; no network, private data, timer or notification."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

import storyfx_diagnostics_probe as probe

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def health():
    return {"status": "ok", "mode": "diagnostic_only", "publishing_enabled": False,
            "database_ok": True, "recovery_worker_ok": True}


def dashboard(jobs=None):
    items = jobs or []
    return {"mode": "diagnostic_only", "jobs": items, "metrics": {
        "total_jobs": len(items), "needs_review": sum(row["status"] == "NEEDS_REVIEW" for row in items)}}


class StoryfxDiagnosticsProbeTests(unittest.TestCase):
    def evaluate(self, current=None, queue=None, observed=NOW):
        return probe.evaluate(health() if current is None else current,
                              dashboard() if queue is None else queue, observed_at=observed, now=NOW)

    def reasons(self, result):
        return {row["reason_code"] for row in result["checks"]}

    def test_fresh_empty_queue_is_normal_but_not_publication_or_timer_proof(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "ok")
        self.assertIn("QUEUE_EMPTY_NORMAL", self.reasons(result))
        for field in ("publication_verified", "permanent_timer_verified", "collector_connected",
                      "android_agent_verified", "notifications_sent", "business_mutations", "deployed"):
            self.assertFalse(result["metrics"][field])

    def test_wrong_mode_or_publishing_flag_is_an_incident(self):
        for value in ({**health(), "mode": "publication"}, {**health(), "publishing_enabled": True}):
            with self.subTest(value=value):
                result = self.evaluate(value)
                self.assertEqual(result["status"], "incident")
                self.assertIn("DIAGNOSTIC_BOUNDARY_INVALID", self.reasons(result))

    def test_missing_non_boolean_health_evidence_is_unknown(self):
        for field in ("publishing_enabled", "database_ok", "recovery_worker_ok"):
            for value in (None, "true", 1):
                result = self.evaluate({**health(), field: value})
                self.assertEqual(result["status"], "unknown")
        self.assertEqual(probe.evaluate(None, observed_at=NOW, now=NOW)["status"], "unknown")

    def test_database_and_recovery_worker_failures_are_independent_incidents(self):
        for field in ("database_ok", "recovery_worker_ok"):
            result = self.evaluate({**health(), field: False})
            self.assertEqual(result["status"], "incident")
            self.assertIn("UNHEALTHY", self.reasons(result))

    def test_missing_stale_future_and_naive_observation_are_unknown(self):
        for stamp in (None, NOW - timedelta(seconds=121), NOW + timedelta(seconds=31), "2026-10-04T12:00:00"):
            self.assertEqual(self.evaluate(observed=stamp)["status"], "unknown")
        self.assertEqual(self.evaluate(observed=NOW - timedelta(seconds=120))["status"], "ok")

    def test_expired_claim_requires_review_without_replaying(self):
        expiry = (NOW - timedelta(seconds=1)).isoformat()
        result = self.evaluate(queue=dashboard([{"status": "CLAIMED", "lease_expires_at": expiry}]))
        self.assertEqual(result["status"], "incident")
        self.assertIn("STALE_LEASE_NOT_REVIEWED", self.reasons(result))
        check = result["checks"][-1]
        self.assertEqual(check["metrics"]["expected_status"], "NEEDS_REVIEW")
        self.assertEqual(check["metrics"]["lease_timeout_seconds"], 120)
        reviewed = self.evaluate(queue=dashboard([{"status": "NEEDS_REVIEW"}]))
        self.assertEqual(reviewed["status"], "waiting")
        self.assertFalse(reviewed["checks"][-1]["metrics"]["replay_allowed"])

    def test_unexpired_active_lease_is_healthy_missing_lease_is_unknown(self):
        job = {"status": "STARTED", "lease_expires_at": (NOW + timedelta(seconds=1)).isoformat()}
        self.assertEqual(self.evaluate(queue=dashboard([job]))["status"], "ok")
        self.assertEqual(self.evaluate(queue=dashboard([{"status": "STARTED"}]))["status"], "unknown")

    def test_partial_or_invalid_queue_never_claims_exhaustive_lease_health(self):
        partial = dashboard()
        partial["metrics"]["total_jobs"] = 201
        self.assertEqual(self.evaluate(queue=partial)["status"], "unknown")
        for queue in ({}, {"mode": "publication"}, dashboard([{"status": "SUCCESS"}]),
                      {"mode": "diagnostic_only", "jobs": [{"status": []}]}):
            self.assertEqual(self.evaluate(queue=queue)["status"], "unknown")

    def test_transport_confirmation_does_not_confirm_story_publication(self):
        result = self.evaluate(queue=dashboard([{"status": "DIAGNOSTIC_CONFIRMED"}]))
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["metrics"]["publication_verified"])

    def test_payload_urls_private_text_and_unknown_fields_are_not_reflected(self):
        value = {**health(), "url": "https://private.invalid/token", "secret": "PRIVATE_VALUE"}
        queue = dashboard([{"status": "QUEUED", "private_name": "PRIVATE_NAME"}])
        output = json.dumps(self.evaluate(value, queue))
        for private in ("private.invalid", "PRIVATE_VALUE", "PRIVATE_NAME"):
            self.assertNotIn(private, output)

    def test_catalog_records_local_non_deployed_non_illustrated_scope(self):
        value = json.loads(Path(probe.__file__).with_name("storyfx_diagnostics_catalog.json").read_text())
        self.assertEqual(value["maturity"], "local_diagnostic_prototype")
        self.assertEqual(value["local_endpoint"], "http://127.0.0.1:18743/health")
        self.assertIsNone(value["public_endpoint"])
        self.assertIsNone(value["illustration"])
        self.assertFalse(value["deployed"])
        self.assertFalse(value["collector_connected"])


if __name__ == "__main__":
    unittest.main()
