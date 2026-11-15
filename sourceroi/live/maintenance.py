"""Workflow counters and opt-in study events. Automation never counts as human time."""
from datetime import datetime,timezone
import json
from pathlib import Path
from .data_ci import digest


def counters(spec,approval=None):
    approval=approval or {};changes=approval.get('expected_changes',{});protected=set(approval.get('protected_tasks',[]))
    proposals=[p for p in spec['evaluation_proposals'] if p.get('classification')=='PROPOSED_CHANGE']
    accepted=[p['task_id'] for p in proposals if changes.get(p['task_id'])==p['suggested_expected']]
    corrected=[p['task_id'] for p in proposals if p['task_id'] in changes and changes[p['task_id']]!=p['suggested_expected']]
    rejected=[p['task_id'] for p in proposals if p['task_id'] in approval.get('rejected_tasks',[]) or p['task_id'] in protected]
    affected={r['task_id'] for r in spec['impact'] if r['potentially_affected']}
    return {'proposed_changes':len(proposals),'accepted_suggestions':len(accepted),'rejected_suggestions':len(rejected),
        'manual_correction_fields':len(corrected),'manual_answer_entry_fields':len(set(changes)-set(accepted)-set(corrected)),
        'ambiguous_items':sum(p.get('classification')=='AMBIGUOUS_REVIEW' for p in spec['evaluation_proposals']),
        'new_tests_proposed':len(spec['candidate_tests']),'protected_expectations_preserved':len(protected-set(changes)),
        'review_complete':bool(approval) and affected<=set(changes)|protected,
        'actual_human_edits':None,'review_elapsed_seconds':None,
        'measurement_basis':'Field/decision counters only, not observed human interactions or human effort savings'}


def events(path):
    path=Path(path);rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    previous=None
    for i,row in enumerate(rows):
        if row.get('sequence')!=i or row.get('previous_hash')!=previous or row.get('hash')!=digest({k:v for k,v in row.items() if k!='hash'}):raise ValueError('Study event chain failed integrity check')
        previous=row['hash']
    return rows


def _record(path,*,protocol_id,session_id,participant_id,origin,workflow,change_id,event,edit_count=0):
    if origin not in ('human','automation') or workflow not in ('maintained_full_suite','maintained_with_diff','sourceroi') or event not in ('start','review','edit','complete'):raise ValueError('Invalid study event')
    if any(not isinstance(v,str) or not v.strip() for v in (protocol_id,session_id,participant_id,change_id)) or type(edit_count) is not int or edit_count<0:raise ValueError('Invalid study identity/edit count')
    rows=events(path);session=[r for r in rows if r['session_id']==session_id]
    if event=='start' and session or event!='start' and (not session or session[-1]['event']=='complete'):raise ValueError('Invalid study event order')
    if session and any(session[0][k]!=v for k,v in {'protocol_id':protocol_id,'participant_id':participant_id,'origin':origin,'workflow':workflow,'change_id':change_id}.items()):raise ValueError('Study session identity changed')
    row={'sequence':len(rows),'previous_hash':rows[-1]['hash'] if rows else None,'timestamp':datetime.now(timezone.utc).isoformat(),
        'protocol_id':protocol_id,'session_id':session_id,'participant_id':participant_id,'origin':origin,'workflow':workflow,
        'change_id':change_id,'event':event,'edit_count':edit_count}
    row['hash']=digest(row);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:f.write(json.dumps(row)+'\n')
    return row


def summarize(path):
    rows=events(path);sessions={}
    for row in rows:sessions.setdefault(row['session_id'],[]).append(row)
    complete=[]
    for ident,rs in sessions.items():
        if rs[0]['origin']!='human' or rs[-1]['event']!='complete':continue
        complete.append({'session_id':ident,'workflow':rs[0]['workflow'],'change_id':rs[0]['change_id'],
            'elapsed_seconds':(datetime.fromisoformat(rs[-1]['timestamp'])-datetime.fromisoformat(rs[0]['timestamp'])).total_seconds(),
            'edit_count':sum(r['edit_count'] for r in rs), 'identity_status':'participant-declared; operator must validate study/identity/activity'})
    return {'completed_declared_human_sessions':complete,'excluded_automated_sessions':sum(rs[0]['origin']=='automation' for rs in sessions.values()),
        'time_savings':None,'study_status':'pending external validated study' if not complete else 'raw participant-declared timing; no causal labor-savings estimate'}


def record(path,**event):
    # Local study logger is serialised across CLI processes on macOS/Linux.
    import fcntl
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix(path.suffix+'.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try:return _record(path,**event)
        finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
