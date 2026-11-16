"""SQLite records and optimistic revisions. Source transcript remains immutable."""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from .extract import RuleError

class Store:
    def __init__(self,directory):
        Path(directory).mkdir(parents=True,exist_ok=True);self.path=Path(directory)/'minutes.sqlite3'
        with self.db() as conn:
            conn.executescript('''CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,updated REAL NOT NULL,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history(meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,revision INTEGER,data TEXT NOT NULL,PRIMARY KEY(meeting_id,revision));''')
    @contextmanager
    def db(self):
        conn=sqlite3.connect(self.path,timeout=10,isolation_level=None);conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON')
        try:yield conn
        finally:conn.close()
    @contextmanager
    def transaction(self):
        with self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:yield conn;conn.commit()
            except Exception:conn.rollback();raise
    def create(self,title,transcript,segments,items,mode):
        now=time.time();record={'id':uuid.uuid4().hex,'title':title,'transcript':transcript,'source_sha256':hashlib.sha256(transcript.encode()).hexdigest(),'segments':segments,'items':items,'mode':mode,'revision':1,'reviewed':False,'reviewed_at':None,'created_at':now,'updated_at':now}
        with self.transaction() as conn:
            conn.execute('INSERT INTO meetings VALUES(?,?,?,?)',(record['id'],1,now,json.dumps(record)))
            conn.execute('INSERT INTO history VALUES(?,?,?)',(record['id'],1,json.dumps(record)))
        return record
    def _get(self,conn,identifier):
        row=conn.execute('SELECT data FROM meetings WHERE id=?',(identifier,)).fetchone()
        if not row:raise RuleError('Meeting not found.',404)
        return json.loads(row['data'])
    def get(self,identifier):
        with self.db() as conn:return self._get(conn,identifier)
    def recent(self):
        with self.db() as conn:rows=conn.execute('SELECT data FROM meetings ORDER BY updated DESC LIMIT 30').fetchall()
        records=[json.loads(row['data']) for row in rows]
        return [{k:r[k] for k in ('id','title','revision','reviewed','updated_at')} for r in records]
    def _check(self,record,revision):
        if record['revision']!=revision:raise RuleError('This meeting changed in another tab. Reload it before saving.',409)
    def _save(self,conn,record):
        record['revision']+=1;record['updated_at']=time.time()
        conn.execute('UPDATE meetings SET revision=?,updated=?,data=? WHERE id=?',(record['revision'],record['updated_at'],json.dumps(record),record['id']))
        conn.execute('INSERT INTO history VALUES(?,?,?)',(record['id'],record['revision'],json.dumps(record)))
        return record
    def review(self,identifier,body):
        with self.transaction() as conn:
            r=self._get(conn,identifier);self._check(r,body.revision)
            by_id={i['id']:i for i in r['items']}
            if len({e.id for e in body.edits})!=len(body.edits):raise RuleError('Duplicate edited item IDs.')
            for edit in body.edits:
                if edit.id not in by_id:raise RuleError('Unknown edited item ID.')
                item=by_id[edit.id]
                if item['kind']!='action' and (edit.owner or edit.due_text):raise RuleError('Only action items may have owners and due text.')
                updates=edit.model_dump(exclude={'id'})
                updates['owner']=updates['owner'].strip() or None if updates['owner'] else None
                updates['due_text']=updates['due_text'].strip() or None if updates['due_text'] else None
                if any(item.get(k)!=v for k,v in updates.items()):item['edited']=True
                item.update(updates)
            if body.reviewed and not any(i['included'] for i in r['items']):raise RuleError('Include at least one item before marking reviewed.')
            r['reviewed']=body.reviewed;r['reviewed_at']=time.time() if body.reviewed else None
            return self._save(conn,r)
    def add(self,identifier,body):
        with self.transaction() as conn:
            r=self._get(conn,identifier);self._check(r,body.revision)
            if len(r['items'])>=100:raise RuleError('Use at most 100 items per meeting.')
            source=next((s for s in r['segments'] if s['id']==body.source_id),None)
            if not source:raise RuleError('Select an existing source segment.')
            if body.kind!='action' and (body.owner or body.due_text):raise RuleError('Only action items may have owners and due text.')
            item={'id':uuid.uuid4().hex,'kind':body.kind,'text':body.text,'source_id':body.source_id,'quote':source['text'],'owner':body.owner.strip() or None if body.owner else None,'due_text':body.due_text.strip() or None if body.due_text else None,'included':True,'edited':True,'provenance':'user-added'}
            r['items'].append(item);r['reviewed']=False;r['reviewed_at']=None
            return self._save(conn,r)
    def revisions(self,identifier):
        with self.db() as conn:
            self._get(conn,identifier)
            return [json.loads(row['data']) for row in conn.execute('SELECT data FROM history WHERE meeting_id=? ORDER BY revision',(identifier,))]
    def delete(self,identifier,revision):
        with self.transaction() as conn:
            r=self._get(conn,identifier);self._check(r,revision);conn.execute('DELETE FROM meetings WHERE id=?',(identifier,))
        return {'deleted':True}
