"""Durable fail-closed waits for temporary identity-service failures only."""


class SchedulerWaits:
    transient = frozenset({('AUTH_UNAVAILABLE', 503), ('RATE_LIMITED', 429)})

    def __init__(self, broker):
        self.broker, self.store = broker, broker.store
        with self.store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS control_scheduler_waits (
              owner_id TEXT PRIMARY KEY, generation TEXT NOT NULL,
              failures INTEGER NOT NULL, next_check REAL NOT NULL,
              reason TEXT NOT NULL, status INTEGER NOT NULL)''')

    def due(self, row):
        with self.store.transaction() as db:
            wait = db.execute('SELECT next_check FROM control_scheduler_waits '
                              'WHERE owner_id=? AND generation=?',
                              (row['owner_id'], row['generation'])).fetchone()
        return not wait or self.store.clock() >= wait['next_check']

    def defer(self, row, error):
        if (error.code, error.status) not in self.transient:
            return False
        with self.store.transaction() as db:
            changed = db.execute('UPDATE control_schedulers SET wait_reason=? '
                                 'WHERE owner_id=? AND generation=? AND enabled=1',
                                 (error.code, row['owner_id'], row['generation'])).rowcount
            if not changed:
                return True  # A concurrent owner stop must never be reversed.
            previous = db.execute('SELECT failures FROM control_scheduler_waits '
                                  'WHERE owner_id=? AND generation=?',
                                  (row['owner_id'], row['generation'])).fetchone()
            failures = previous['failures'] + 1 if previous else 1
            delay = min(30 * 2 ** min(failures - 1, 4), 300)
            db.execute('INSERT INTO control_scheduler_waits VALUES (?,?,?,?,?,?) '
                       'ON CONFLICT(owner_id) DO UPDATE SET generation=excluded.generation,'
                       'failures=excluded.failures,next_check=excluded.next_check,'
                       'reason=excluded.reason,status=excluded.status',
                       (row['owner_id'], row['generation'], failures,
                        self.store.clock() + delay, error.code, error.status))
            if not previous:
                self.broker.terminal.emit(db, row['owner_id'], 'SCHEDULER_CONTROL_WAITING')
        return True

    def clear(self, row):
        with self.store.transaction() as db:
            removed = db.execute('DELETE FROM control_scheduler_waits '
                                 'WHERE owner_id=? AND generation=?',
                                 (row['owner_id'], row['generation'])).rowcount
            if removed:
                self.broker.terminal.emit(db, row['owner_id'], 'SCHEDULER_CONTROL_RESUMED')
