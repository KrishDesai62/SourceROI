"""Independent reconciliation of instrumented C++ events and Python raw artifacts.

No matching-count shortcut: bind each reservation, wire body, task, terminal HTTP
response and native token counters. Failures/unknowns never become zero usage.
"""
import json
from pathlib import Path


def inspect_native(root,manifest,reservations,responses,errors):
    root=Path(root);fail=[]
    try:records=[json.loads(line) for line in (root/'native-events.jsonl').read_text().splitlines()]
    except (OSError,ValueError):return {'failures':['native_audit_missing_or_invalid'],'confirmed_completions':None}
    wanted={r['request_id']:r for r in reservations}
    if len(wanted)!=len(reservations):fail.append('duplicate_reservation')
    if any(r.get('event') in ('denied','untracked_task','untracked_finish') for r in records):fail.append('native_untracked_or_denied_traffic')
    ids={r.get('request_id') for r in records if r.get('event') in ('admitted','bound','dispatched','completed','failed','cancelled','http_response')}
    if ids!=set(wanted):fail.append('native_request_identity_set_mismatch')
    completed=0;tasks=[]
    for rid,reservation in wanted.items():
        rs=[r for r in records if r.get('request_id')==rid]
        def only(name):
            hits=[r for r in rs if r.get('event')==name]
            if len(hits)!=1:fail.append('native_'+name+'_cardinality:'+rid);return None
            return hits[0]
        admitted,bound,dispatch,finish,http=[only(k) for k in ('admitted','bound','dispatched','completed','http_response')]
        if any(r.get('event') in ('failed','cancelled') for r in rs):fail.append('native_failed_or_cancelled_usage_incomplete:'+rid)
        try:
            body=json.loads((root/reservation['artifact']).read_text())
            if admitted and json.loads(admitted['body'])!=body:fail.append('native_request_body_mismatch:'+rid)
            task_ids=[r['task_id'] for r in (bound,dispatch,finish) if r]
            if len(set(task_ids))!=1:fail.append('native_task_identity_mismatch:'+rid)
            elif task_ids:tasks.append(task_ids[0])
            order=[r['event'] for r in rs]
            if order!=['admitted','bound','dispatched','completed','http_response']:fail.append('native_state_order_or_terminal_mismatch:'+rid)
            response=[r for r in responses if r['request_id']==rid]
            if len(response)!=1 or http is None or http['code']!=200:fail.append('native_terminal_response_missing:'+rid);continue
            captured=json.loads((root/response[0]['artifact']).read_text())
            if captured['status_code']!=http['code'] or captured['body']!=http['body']:fail.append('native_raw_response_mismatch:'+rid)
            data=json.loads(http['body']);usage=data.get('usage')
            if not isinstance(usage,dict) or not finish:fail.append('native_usage_unknown:'+rid);continue
            if any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens')) or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']:fail.append('native_usage_invalid:'+rid)
            if usage.get('prompt_tokens')!=finish['input_tokens'] or usage.get('completion_tokens')!=finish['output_tokens']:fail.append('native_token_counter_mismatch:'+rid)
            if usage!=response[0].get('usage'):fail.append('captured_usage_mismatch:'+rid)
            completed+=1
        except (KeyError,ValueError,OSError,TypeError):fail.append('native_artifact_or_protocol_invalid:'+rid)
    if len(set(tasks))!=len(tasks):fail.append('native_task_reused')
    if len(reservations)>manifest['max_calls']:fail.append('native_call_cap_exceeded')
    return {'failures':sorted(set(fail)),'confirmed_completions':completed,'server_records':len(records)}
