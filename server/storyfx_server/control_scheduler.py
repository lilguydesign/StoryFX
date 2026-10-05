"""Durable explicitly-started scheduler; never replays or invokes a phone itself."""
from datetime import datetime, timedelta
import json
from uuid import uuid4
from zoneinfo import ZoneInfo
from .control_publications import reserve, supported
from .store import DomainError, timestamp
from .control_android import executors

ZONE = ZoneInfo('Africa/Douala')


class Scheduler:
    def __init__(self, broker):
        self.broker, self.store, self.sessions = broker, broker.store, broker.sessions
        with self.store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS control_schedulers (
              owner_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, generation TEXT NOT NULL,
              auth_session TEXT NOT NULL, revision INTEGER NOT NULL, scope TEXT NOT NULL,
              from_at REAL NOT NULL, mode TEXT NOT NULL, started REAL NOT NULL,
              wait_reason TEXT NOT NULL DEFAULT '')''')

    def status(self, user):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM control_schedulers WHERE owner_id=?',(user['id'],)).fetchone()
        if not row:
            return {'enabled':False,'mode':'auto','profiles':[],'platforms':[],'wait_reason':''}
        return {'enabled':bool(row['enabled']), 'mode':row['mode'], **json.loads(row['scope']),
                'from_at':timestamp(row['from_at']),'started_at':timestamp(row['started']),
                'wait_reason':row['wait_reason']}

    def window(self, user, body):
        snapshot = self.broker.snapshot(user)
        if snapshot['revision'] != body.revision:
            raise DomainError('CONFIGURATION_CHANGED',409)
        known = {value['name'] for value in snapshot['collections']['profiles']}
        if not set(body.profiles) <= known:
            raise DomainError('PROFILE_NOT_FOUND',422)
        now = datetime.fromtimestamp(self.store.clock(),ZONE)
        day = now.replace(hour=0,minute=0,second=0,microsecond=0)
        hour,minute = map(int,body.start_time.split(':'))
        start = day + timedelta(hours=hour,minutes=minute)
        end = now
        if body.end_time:
            hour,minute = map(int,body.end_time.split(':'))
            end = min(now,day + timedelta(hours=hour,minutes=minute,seconds=59,microseconds=999999))
            if body.end_time > now.strftime('%H:%M'):
                raise DomainError('CATCHUP_FUTURE_END',422)
        if start > end:
            raise DomainError('CATCHUP_INTERVAL_INVALID',422)
        selected = [value for value in snapshot['schedule'] if value['device'] in body.profiles
                    and value['platform'] in body.platforms and start.timestamp() <=
                    datetime.fromisoformat(value['due_at'].replace('Z','+00:00')).timestamp() <= end.timestamp()]
        rows = []
        for value in selected:
            connected = len(executors(snapshot, value)) == 1
            reason = 'ALREADY_REQUESTED' if value['state'] != 'PLANNED' else 'ADAPTER_NOT_VALIDATED' if not supported(value) else 'WINDOWS_DISCONNECTED' if not connected else 'READY'
            rows.append({**value,'eligible':reason == 'READY','reason':reason})
        return snapshot, {'from_at':timestamp(start.timestamp()),'until':timestamp(end.timestamp()),
                          'timezone':'Africa/Douala','rows':rows,'eligible_count':sum(row['eligible'] for row in rows)}

    def preview(self, user, body):
        return self.window(user,body)[1]

    def catchup(self, user, body):
        snapshot, result = self.window(user,body)
        accepted = reserve(self.broker,user,snapshot,[row for row in result['rows'] if row['eligible']],strict=False)
        return {'jobs':accepted,'queued':len(accepted),'excluded':len(result['rows'])-len(accepted)}

    def start(self, user, body):
        if not self.sessions:
            raise DomainError('ACCOUNT_AUTH_REQUIRED',503)
        if body.end_time is not None:
            raise DomainError('SCHEDULER_END_NOT_SUPPORTED',422)
        window_body = body.model_copy(update={'start_time':'00:00','end_time':None}) if body.mode == 'auto' else body
        snapshot, result = self.window(user,window_body)
        start = datetime.fromisoformat(result['from_at']).timestamp() if body.mode == 'manual' else self.store.clock() // 60 * 60
        session = self.sessions.delegate(user)
        with self.store.transaction() as db:
            self.broker.catalog.revision(db,user['id'],body.revision)
            current = db.execute('SELECT enabled FROM control_schedulers WHERE owner_id=?',(user['id'],)).fetchone()
            if current and current['enabled']:
                raise DomainError('SCHEDULER_ALREADY_RUNNING',409)
            db.execute('INSERT INTO control_schedulers VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(owner_id) DO UPDATE SET '
                       'enabled=excluded.enabled,generation=excluded.generation,auth_session=excluded.auth_session,'
                       'revision=excluded.revision,scope=excluded.scope,from_at=excluded.from_at,mode=excluded.mode,started=excluded.started,wait_reason=excluded.wait_reason',
                       (user['id'],1,str(uuid4()),session,body.revision,json.dumps({'profiles':body.profiles,'platforms':body.platforms}),start,body.mode,self.store.clock(),''))
            self.broker.terminal.emit(db,user['id'],'SCHEDULER_STARTED')
        self.tick()
        return self.status(user)

    def stop(self, user):
        with self.store.transaction() as db:
            db.execute('UPDATE control_schedulers SET enabled=0 WHERE owner_id=?',(user['id'],))
            db.execute("UPDATE control_jobs SET state='CANCELLED',completed=? WHERE owner_id=? AND state='QUEUED' AND json_extract(payload,'$.scheduler_generation') IS NOT NULL",
                       (self.store.clock(),user['id']))
            self.broker.terminal.emit(db,user['id'],'SCHEDULER_STOPPED')
        return self.status(user)

    def stop_jobs(self, user, stop_scheduler):
        with self.store.transaction() as db:
            if stop_scheduler:
                db.execute('UPDATE control_schedulers SET enabled=0 WHERE owner_id=?',(user['id'],))
            queued = db.execute("UPDATE control_jobs SET state='CANCELLED',completed=? WHERE owner_id=? AND state='QUEUED'",(self.store.clock(),user['id'])).rowcount
            running = db.execute("UPDATE control_jobs SET state='CANCEL_REQUESTED' WHERE owner_id=? AND state='CLAIMED'",(user['id'],)).rowcount
            self.broker.terminal.emit(db,user['id'],'STOP_REQUESTED')
        return {'queued_cancelled':queued,'running_stop_requested':running,
                'inflight_provider_action_may_finish':bool(running),'appium_interrupted':False}

    def pause(self, row, reason):
        with self.store.transaction() as db:
            changed = db.execute('UPDATE control_schedulers SET enabled=0,wait_reason=? WHERE owner_id=? AND generation=? AND enabled=1',
                                 (reason,row['owner_id'],row['generation'])).rowcount
            if changed:
                db.execute("UPDATE control_jobs SET state='CANCELLED',completed=? WHERE owner_id=? AND state='QUEUED' AND json_extract(payload,'$.scheduler_generation')=?",
                           (self.store.clock(),row['owner_id'],row['generation']))
                self.broker.terminal.emit(db,row['owner_id'],'SCHEDULER_PAUSED')

    def tick(self):
        with self.store.transaction() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM control_schedulers WHERE enabled=1')]
        for row in rows:
            try:
                user = self.sessions.require_hash(row['auth_session'])
                if user['id'] != row['owner_id']:
                    raise DomainError('OWNER_ACCESS_REQUIRED',403)
                snapshot = self.broker.snapshot(user)
                if snapshot['revision'] != row['revision']:
                    self.pause(row,'CONFIGURATION_CHANGED'); continue
                scope = json.loads(row['scope'])
                selected = [value for value in snapshot['schedule'] if value['device'] in scope['profiles']
                            and value['platform'] in scope['platforms'] and value['due'] and value['state'] == 'PLANNED'
                            and datetime.fromisoformat(value['due_at'].replace('Z','+00:00')).timestamp() >= row['from_at']
                            and supported(value)]
                reserve(self.broker,user,snapshot,selected,strict=False,scheduler_id=row['generation'])
                waiting = any(len(executors(snapshot, value)) != 1 for value in selected)
                with self.store.transaction() as db:
                    db.execute('UPDATE control_schedulers SET mode=\'auto\',wait_reason=? WHERE owner_id=? AND generation=? AND enabled=1',
                               ('WINDOWS_DISCONNECTED' if waiting else '',user['id'],row['generation']))
            except DomainError as error:
                self.pause(row,'OWNER_ACCESS_REQUIRED' if error.status in (401,403) else 'CONTROL_UNAVAILABLE')
