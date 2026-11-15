"""Fixed deterministic protocol fixture. Never opens a socket or loads a model."""
import json
from pathlib import Path
import time

def main():
    request=json.loads(Path('request.json').read_text());mode=request['mode']
    import os
    rid=request['attempt_id'];permit=Path('permits')/rid
    wire=permit.read_bytes();expected=json.dumps(request['body'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if wire!=expected:raise ValueError('Fixture native permit/body mismatch')
    permit.unlink()  # single-use contract; no native generation authority implied
    Path('native-request.json').write_bytes(wire)
    events=Path('native-events.jsonl')
    def event(name,**fields):
        with events.open('a') as f:f.write(json.dumps({'event':name,'request_id':rid,**fields})+'\n');f.flush();os.fsync(f.fileno())
    event('admitted',body=wire.decode());event('bound',task_id=rid);event('dispatched',task_id=rid)
    if mode=='timeout':time.sleep(5)
    if mode=='failure':raise RuntimeError('Declared fixture failure')
    result={'attempt_id':request['attempt_id'],'task_id':request['task_id'],'fixture':True,
        'child_calls':1 if mode=='child_call' else 0,'answer':request['answer'],'citations':request['citations'],
        'usage':None if mode=='missing_usage' else {'prompt_tokens':3,'completion_tokens':1}}
    usage=result['usage']
    provider={'choices':[{'message':{'content':json.dumps({'answer':request['answer'],'citations':request['citations']})},'finish_reason':'stop'}],'usage':{**usage,'total_tokens':sum(usage.values())} if usage else None}
    event('completed',task_id=rid,input_tokens=usage['prompt_tokens'] if usage else None,output_tokens=usage['completion_tokens'] if usage else None)
    captured={'status_code':200,'body':json.dumps(provider)};Path('native-response.json').write_text(json.dumps(captured))
    event('http_response',code=200,body=captured['body'])
    if mode=='child_call':event('untracked_task',task_id='unexpected-fixture-child')
    if mode=='partial':Path('response.json').write_text('{');return
    Path('response.json').write_text(json.dumps(result))
if __name__=='__main__':main()
