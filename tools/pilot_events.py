"""Opt-in local onboarding events. Operator declarations are not verified humans."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path

EVENTS={'setup_started','setup_completed','integration_error','adapter_edit','active_time','release_result','report_feedback','participation'}
FIELDS={'event','origin','session_id','operator','details','active_seconds','adapter_edits','report_usefulness','source_owner_participated','reviewer_participated','release_verdict'}


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def read(path):
    path=Path(path)
    if not path.exists():return []
    if path.stat().st_size>2*1024*1024:raise ValueError('Event log exceeds 2 MiB; archive it before starting a new session')
    rows=[];previous=None
    for line in path.read_text().splitlines():
        row=json.loads(line)
        if row.get('sequence')!=len(rows) or row.get('previous_hash')!=previous or digest({k:v for k,v in row.items() if k!='hash'})!=row.get('hash'):raise ValueError('Event log integrity mismatch')
        rows.append(row);previous=row['hash']
    return rows


def record(path,event):
    if not isinstance(event,dict) or set(event)-FIELDS:raise ValueError('Unknown event fields')
    if event.get('event') not in EVENTS or event.get('origin') not in ('automation','operator'):raise ValueError('Choose a documented event and origin')
    if not isinstance(event.get('session_id'),str) or not event['session_id'].strip():raise ValueError('session_id required')
    if event['origin']=='operator' and (not isinstance(event.get('operator'),str) or not event['operator'].strip()):raise ValueError('Operator event requires the actual operator declaration')
    for key in ('details','operator','report_usefulness','session_id'):
        if event.get(key) is not None and (not isinstance(event[key],str) or len(event[key])>4000):raise ValueError('Invalid bounded text field: '+key)
    seconds=event.get('active_seconds')
    if seconds is not None and (type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<=seconds<=86400):raise ValueError('Active seconds must be explicitly observed, finite and within one day')
    if event.get('adapter_edits') is not None and (type(event['adapter_edits']) is not int or not 0<=event['adapter_edits']<=100000):raise ValueError('Invalid adapter edit count')
    for key in ('source_owner_participated','reviewer_participated'):
        if event.get(key) is not None and type(event[key]) is not bool:raise ValueError('Participation must be an explicit boolean or null')
    if event.get('release_verdict') not in (None,'ACCEPT','BLOCK','REVIEW','INCONCLUSIVE'):raise ValueError('Invalid recorded release verdict')
    if event['origin']=='automation' and any(event.get(k) is not None for k in ('active_seconds','report_usefulness','source_owner_participated','reviewer_participated','operator')):raise ValueError('Automation cannot supply human time, feedback or participation')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix(path.suffix+'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=read(path);session=[r for r in rows if r['session_id']==event['session_id']]
        if event['event']=='setup_started' and session or event['event']!='setup_started' and not session:raise ValueError('Record setup_started once before other session events')
        if session and any(session[0].get(k)!=event.get(k) for k in ('origin','operator')):raise ValueError('Session identity changed')
        row={**event,'timestamp':datetime.now(timezone.utc).isoformat(),'sequence':len(rows),'previous_hash':rows[-1]['hash'] if rows else None}
        row['hash']=digest(row)
        with path.open('a') as stream:stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())
        path.chmod(0o600)
    return row


def summarize(path):
    rows=read(path);declared=[r['active_seconds'] for r in rows if r['origin']=='operator' and r.get('active_seconds') is not None]
    return {'status':'VERIFIED_EVENT_LOG_INTEGRITY','events':len(rows),'operator_declared_active_seconds':sum(declared) if declared else None,
        'actual_independently_verified_human_time':None,'operator_feedback':[r for r in rows if r['origin']=='operator' and r.get('report_usefulness') is not None],
        'customer_adoption':'PENDING','identity':'Self-declared; not authenticated','automatic_time_inference':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['record','summarize']);p.add_argument('--log',type=Path,required=True);p.add_argument('--input',type=Path)
    a=p.parse_args()
    try:
        if a.action=='record' and (not a.input or a.input.stat().st_size>16000):raise ValueError('Provide --input JSON event of at most 16000 bytes')
        print(json.dumps(record(a.log,json.loads(a.input.read_text())) if a.action=='record' else summarize(a.log),indent=2))
    except (ValueError,OSError,TypeError) as exc:p.exit(2,'Pilot event failed: '+str(exc)+'\n')
