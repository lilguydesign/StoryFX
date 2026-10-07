"""Evaluate bounded private evidence without publishing, retrying or claiming autonomy."""
from collections import Counter
from datetime import datetime


def observe(snapshot, start, end, grace=900):
    now = snapshot['observed_unix']
    rows = []
    for value in snapshot['rows']:
        due = datetime.fromisoformat(value['due_at'].replace('Z', '+00:00')).timestamp()
        if not start <= due <= end:
            continue
        state = value['state']
        verdict = ('not_validated' if not value['supported'] else
                   'confirmed' if state == 'CONFIRMED' else
                   'needs_review' if state == 'NEEDS_REVIEW' else
                   'failed' if state == 'FAILED_BEFORE_PUBLICATION' else
                   'late' if now > due + grace else 'waiting')
        rows.append({**{k: value[k] for k in ('device', 'platform', 'system', 'count', 'due_at')},
                     'state': state, 'verdict': verdict})
    totals = dict(Counter(row['verdict'] for row in rows))
    return {'observed_unix': now, 'start_unix': start, 'end_unix': end,
            'window_elapsed': now >= end, 'rows': rows, 'totals': totals,
            'scheduler_enabled': snapshot['scheduler']['enabled'],
            'all_scheduled_rows_confirmed': bool(rows) and now >= end and
                all(row['verdict'] == 'confirmed' for row in rows),
            # USB state, natural sleep and Facebook execution require separate witnesses.
            'total_autonomy_verified': False, 'real_send_triggered_by_observer': False}
