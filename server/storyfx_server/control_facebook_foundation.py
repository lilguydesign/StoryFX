"""Canonical permissions and capability boundaries, with Facebook dispatch still closed."""
import json
from dataclasses import dataclass
from .store import DomainError
from .control_native_runtime import availability


def capability():
    # No database flag or heartbeat can fabricate the missing native UI contracts.
    return {'ready': False, 'reason': 'ADAPTER_NOT_VALIDATED', 'contract_version': 1,
            'manual_trial_ready': False, 'auto_ready': False,
            'identity_contract': None, 'media_contract': None, 'proof_contract': None}


@dataclass(frozen=True, repr=False)
class NativeTarget:
    owner_id: str
    profile_id: str
    profile: str
    device_id: str
    node_id: str


def resolve_secondary(db, owner, profile_id, expected_device=None):
    """Caller holds the same write transaction used for reservation/claim/ready."""
    if not db.in_transaction:
        raise DomainError('NATIVE_TRANSACTION_REQUIRED', 500)
    rows = list(db.execute('''SELECT p.id AS profile_id,p.json_name,p.value,a.device_id,a.node_id
      FROM control_android_profiles a
      JOIN control_items p ON p.id=a.profile_id AND p.owner_id=a.owner_id AND p.collection='profiles'
      JOIN control_android_links primary_link ON primary_link.device_id=a.device_id
        AND primary_link.node_id=a.node_id AND primary_link.owner_id=a.owner_id
      JOIN control_items primary_profile ON primary_profile.owner_id=primary_link.owner_id
        AND primary_profile.collection='profiles' AND primary_profile.json_name=primary_link.profile
      JOIN control_nodes n ON n.id=a.node_id AND n.owner_id=a.owner_id AND n.revoked=0
      JOIN devices d ON d.id=a.device_id AND d.owner_id=a.owner_id AND d.revoked=0
      WHERE a.owner_id=? AND a.profile_id=? AND a.platform='Facebook' AND a.revoked IS NULL''',
      (owner, profile_id)))
    if len(rows) != 1:
        raise DomainError('FACEBOOK_PROFILE_NOT_ASSOCIATED', 409)
    row = rows[0]
    if not json.loads(row['value']).get('enabled', True):
        raise DomainError('PROFILE_NOT_FOUND', 422)
    if expected_device is not None and row['device_id'] != expected_device:
        raise DomainError('FACEBOOK_DEVICE_MISMATCH', 409)
    return NativeTarget(owner, row['profile_id'], row['json_name'], row['device_id'], row['node_id'])


def physical_busy(db, target, exclude_job_id=None):
    """Canonical device links exclude peers; hardware metadata only tightens exclusion."""
    if not db.in_transaction:
        raise DomainError('NATIVE_TRANSACTION_REQUIRED', 500)
    profiles = {row['json_name']: json.loads(row['value']) for row in db.execute(
        "SELECT json_name,value FROM control_items WHERE owner_id=? AND collection='profiles'", (target.owner_id,))}
    shared = {row['profile'] for row in db.execute(
        'SELECT profile FROM control_android_links WHERE owner_id=? AND device_id=?',
        (target.owner_id, target.device_id))}
    shared.update(row['json_name'] for row in db.execute('''SELECT p.json_name FROM control_android_profiles a
      JOIN control_items p ON p.id=a.profile_id AND p.owner_id=a.owner_id AND p.collection='profiles'
      WHERE a.owner_id=? AND a.device_id=? AND a.revoked IS NULL''', (target.owner_id, target.device_id)))
    hardware = {profiles[name].get('adb_serial') for name in shared if name in profiles}
    hardware.discard(''); hardware.discard(None)
    for row in db.execute('''SELECT id,node_id,payload FROM control_jobs WHERE owner_id=?
      AND completed IS NULL AND state IN ('QUEUED','CLAIMED','CANCEL_REQUESTED','NEEDS_REVIEW')''', (target.owner_id,)):
        if row['id'] == exclude_job_id:
            continue
        other = json.loads(row['payload']).get('device')
        if row['node_id'] == target.node_id or other in shared or profiles.get(other, {}).get('adb_serial') in hardware:
            return True
    return db.execute("SELECT 1 FROM jobs WHERE device_id=? AND status IN ('QUEUED','CLAIMED','STARTED','NEEDS_REVIEW') LIMIT 1",
                      (target.device_id,)).fetchone() is not None


def trial_status(db, target, now):
    runtime = availability(db, target.owner_id, target.device_id, target.node_id, now)
    return {'association_exists': True, 'physical_ready': runtime['physical_ready'],
            'physical_reason': runtime['reason'], 'physical_busy': physical_busy(db, target),
            **capability()}


def require_manual_trial(db, owner, profile_id, now, expected_device=None):
    # Resolve/check for diagnostics, but never let these prerequisites stand in for UI validation.
    target = resolve_secondary(db, owner, profile_id, expected_device)
    trial_status(db, target, now)
    raise DomainError('ADAPTER_NOT_VALIDATED', 409)
