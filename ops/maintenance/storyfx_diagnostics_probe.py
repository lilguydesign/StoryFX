"""Offline StoryFX prototype checks. No HTTP, notification, phone or database writes."""

from datetime import datetime, timezone

IDENTITY = "storyfx_local_diagnostics"
MAX_AGE_SECONDS = 120
LEASE_TIMEOUT_SECONDS = 120
STATUSES = {"QUEUED", "CLAIMED", "STARTED", "NEEDS_REVIEW", "EXPIRED", "CANCELLED",
            "DIAGNOSTIC_CONFIRMED"}


def _time(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _check(identity, status, reason, **metrics):
    return {"id": identity, "status": status, "reason_code": reason, "metrics": metrics}


def _queue_check(dashboard, now):
    if not isinstance(dashboard, dict) or dashboard.get("mode") != "diagnostic_only":
        return _check("storyfx_diagnostic_queue", "unknown", "QUEUE_PROOF_MISSING")
    jobs, metrics = dashboard.get("jobs"), dashboard.get("metrics", {})
    if not isinstance(jobs, list) or len(jobs) > 1000 or not isinstance(metrics, dict):
        return _check("storyfx_diagnostic_queue", "unknown", "QUEUE_PROOF_INVALID")
    reviewed, expired_active, active_unknown = 0, 0, 0
    for job in jobs:
        if (not isinstance(job, dict) or not isinstance(job.get("status"), str)
                or job["status"] not in STATUSES):
            return _check("storyfx_diagnostic_queue", "unknown", "QUEUE_STATUS_UNVERIFIED")
        status = job["status"]
        if status == "NEEDS_REVIEW":
            reviewed += 1
        elif status in {"CLAIMED", "STARTED"}:
            expiry = _time(job.get("lease_expires_at"))
            if expiry is None or now is None:
                active_unknown += 1
            elif expiry <= now:
                expired_active += 1
    total = metrics.get("total_jobs", len(jobs))
    review_total = metrics.get("needs_review", reviewed)
    if (type(total) is not int or type(review_total) is not int or total < len(jobs)
            or review_total < reviewed or review_total < 0 or review_total > total):
        return _check("storyfx_diagnostic_queue", "unknown", "QUEUE_COUNTS_UNVERIFIED")
    if expired_active:
        return _check("storyfx_diagnostic_queue", "incident", "STALE_LEASE_NOT_REVIEWED",
                      expired_active=expired_active, expected_status="NEEDS_REVIEW",
                      lease_timeout_seconds=LEASE_TIMEOUT_SECONDS)
    if review_total:
        return _check("storyfx_diagnostic_queue", "waiting", "DIAGNOSTIC_NEEDS_REVIEW",
                      needs_review=review_total, replay_allowed=False)
    if active_unknown or total > len(jobs):
        return _check("storyfx_diagnostic_queue", "unknown", "LEASE_COVERAGE_UNVERIFIED",
                      active_without_lease_proof=active_unknown, partial_queue=total > len(jobs))
    return _check("storyfx_diagnostic_queue", "ok", "QUEUE_EMPTY_NORMAL" if not jobs else "QUEUE_READY",
                  observed_jobs=len(jobs), publication_verified=False)


def evaluate(health_json, dashboard_json=None, *, observed_at=None, now=None):
    """Evaluate supplied evidence without accepting URLs or reflecting payload text.

    ``observed_at`` is the trusted time of collection, not a timestamp supplied
    by the health payload. Optional ``now`` supports deterministic fixture tests.
    This probe is not connected to the deployed maintenance collector.
    """
    current = _time(now) if now is not None else datetime.now(timezone.utc)
    observed = _time(observed_at)
    checks = []
    if current is None or observed is None:
        checks.append(_check("storyfx_observation", "unknown", "OBSERVATION_TIME_MISSING"))
    else:
        age = (current - observed).total_seconds()
        if age < -30 or age > MAX_AGE_SECONDS:
            checks.append(_check("storyfx_observation", "unknown", "OBSERVATION_STALE_OR_FUTURE"))
        else:
            checks.append(_check("storyfx_observation", "ok", "OBSERVATION_FRESH"))
    if not isinstance(health_json, dict):
        checks.append(_check("storyfx_local_health", "unknown", "HEALTH_PROOF_MISSING"))
    else:
        mode, publishing = health_json.get("mode"), health_json.get("publishing_enabled")
        if mode is None or type(publishing) is not bool:
            checks.append(_check("storyfx_diagnostic_boundary", "unknown", "MODE_PROOF_MISSING"))
        elif mode != "diagnostic_only" or publishing:
            checks.append(_check("storyfx_diagnostic_boundary", "incident", "DIAGNOSTIC_BOUNDARY_INVALID"))
        else:
            checks.append(_check("storyfx_diagnostic_boundary", "ok", "DIAGNOSTIC_ONLY"))
        for field, identity in (("database_ok", "storyfx_database"),
                                ("recovery_worker_ok", "storyfx_recovery_worker")):
            value = health_json.get(field)
            status = "unknown" if type(value) is not bool else "ok" if value else "incident"
            reason = "PROOF_MISSING" if status == "unknown" else "HEALTHY" if value else "UNHEALTHY"
            checks.append(_check(identity, status, reason))
        status = health_json.get("status")
        health_status = "ok" if status == "ok" else "incident" if status == "degraded" else "unknown"
        checks.append(_check("storyfx_local_health", health_status,
                             "HEALTH_OK" if health_status == "ok" else "HEALTH_NOT_PROVEN"))
    checks.append(_queue_check(dashboard_json, current))
    priority = {"ok": 0, "waiting": 1, "unknown": 2, "incident": 3}
    overall = max((check["status"] for check in checks), key=priority.get)
    return {"id": IDENTITY, "label": "StoryFX — diagnostic local", "status": overall,
            "checks": checks, "metrics": {"maturity": "local_diagnostic_prototype",
                "deployed": False, "collector_connected": False, "permanent_timer_verified": False,
                "publication_verified": False, "android_agent_verified": False,
                "notifications_sent": False, "business_mutations": False}}
