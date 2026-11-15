"""Owned local experiment boundary, not a general agent orchestration service.

Private authenticated UNIX socket, exclusive runtime/test lease, fsynced attempt
reservations and parent-death supervision. No retries or inference on recovery.
Native server logs must reconcile before a complete-accounting claim is possible.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import urlparse
import httpx

DEFAULT_LEASE=Path(__file__).resolve().parents[2]/'workspace/.local-llm/experiment.lock'


def sha(data):return hashlib.sha256(data).hexdigest()


def write_once(path,data):
    raw=json.dumps(data,sort_keys=True,indent=2,allow_nan=False).encode()
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


@contextmanager
def runtime_lease(path=DEFAULT_LEASE):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Runtime/test lease occupied; stop the other experiment or regression suite') from None
        try:yield handle
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def events(root):
    path=Path(root)/'events.jsonl';previous=None;rows=[]
    if not path.exists():return rows
    for line in path.read_text().splitlines():
        row=json.loads(line);check={k:v for k,v in row.items() if k!='hash'}
        if row.get('previous_hash')!=previous or row.get('sequence')!=len(rows) or row.get('hash')!=sha(json.dumps(check,sort_keys=True).encode()):raise ValueError('Experiment event chain failed integrity check')
        rows.append(row);previous=row['hash']
    return rows


def audit_native_log(text,recorded_attempts):
    """Native slot evidence is diagnostic, never a substitute for request IDs.

    The pinned HTTP logger registration is disabled upstream. Equal slot and
    ledger counts therefore cannot certify individual requests or responses.
    Cancellation timing output must not be called a confirmed completion.
    """
    messages=[]
    for line in text.splitlines():
        try:
            record=json.loads(line)
            messages.append(record.get('message',record.get('text',line)) if isinstance(record,dict) else line)
        except ValueError:messages.append(line)
    joined='\n'.join(str(m) for m in messages)
    prefix=r'(?m)^(?:(?:\d+\.)+\d+\s+[A-Z]\s+)?slot\s+[A-Za-z_]+:\s*id\s+\d+\s*\|\s*'
    tasks=re.findall(prefix+r'task\s+(\d+)\s*\|\s*processing task, is_child\s*=\s*(\d+)\s*$',joined)
    failures=['native_request_id_reconciliation_unverified']
    if len(tasks)>recorded_attempts:failures.append('untracked_native_generation')
    if any(child!='0' for _,child in tasks):failures.append('native_child_generations_present')
    return {'status':'PENDING','failures':failures,'generation_task_count':len(tasks),'task_ids':[int(t) for t,_ in tasks],
            'timing_records':len(re.findall(r'prompt eval time',joined)),
            'cancelled_task_ids':[int(t) for t in re.findall(r'cancel task, id_task\s*=\s*(\d+)',joined)],
            'confirmed_completions':None,'complete_usage':None,
            'source':'https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/server-http.cpp#L245',
            'gate':'No native launch until actual server request/response IDs can be independently matched; counts alone are insufficient.'}


def reconcile(root):
    """Read-only audit: incomplete/unknown data never becomes complete by restart."""
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text());rows=events(root);failures=[]
    reservations=[r for r in rows if r['event']=='reserved'];responses=[r for r in rows if r['event']=='response'];errors=[r for r in rows if r['event']=='request_failed']
    for r in rows:
        if r.get('artifact'):
            path=root/r['artifact']
            if not path.is_file() or sha(path.read_bytes())!=r['artifact_sha256']:failures.append('artifact_mismatch:'+r['artifact'])
    # Logs become immutable after supervisor exit and are included in the seal.
    worker=json.loads((root/'worker-exit.json').read_text()) if (root/'worker-exit.json').exists() else None
    if worker is None:failures.append('runtime_exit_not_observed')
    elif worker['reason']!='owner_shutdown':failures.append('abnormal_shutdown:'+worker['reason'])
    text=(root/'server.log').read_text(errors='replace') if (root/'server.log').exists() else ''
    if manifest['runtime_kind']=='fixture':
        records=[]
        for line in text.splitlines():
            try:records.append(json.loads(line))
            except ValueError:failures.append('unparseable_fixture_server_log')
        dispatch=[r for r in records if r.get('event')=='accepted_chat'];finished=[r for r in records if r.get('event')=='response']
        unauthorized=[r for r in records if r.get('event')=='unauthorized']
        wanted=[r['request_id'] for r in reservations]
        if sorted(r['request_id'] for r in dispatch)!=sorted(wanted):failures.append('server_dispatch_mismatch')
        captured=responses+[r for r in errors if r.get('artifact')]
        if sorted(r['request_id'] for r in finished)!=sorted(r['request_id'] for r in captured):failures.append('server_response_mismatch')
        if unauthorized:failures.append('untracked_unauthorized_request_attempt')
        completed_generations=len(finished)
    elif manifest['runtime_kind']=='native_instrumented':
        from .native_accounting import inspect_native
        audited=inspect_native(root,manifest,reservations,responses,errors)
        completed_generations=audited['confirmed_completions'];failures.extend(audited['failures'])
    else:
        # Native logs do not currently bind server task IDs to client request IDs.
        # Count evidence is retained, but never call it complete reconciliation.
        native=audit_native_log(text,len(reservations))
        completed_generations=native['confirmed_completions']
        failures.extend(native['failures'])
    if len(reservations)>manifest['max_calls']:failures.append('call_budget_exceeded')
    terminal={r['request_id'] for r in responses+errors}
    if terminal!={r['request_id'] for r in reservations}:failures.append('unresolved_request_reservation')
    if errors:failures.append('failed_request_usage_unknown')
    tokens=[]
    for r in responses:
        usage=r.get('usage') or {}
        if any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens')) or usage.get('total_tokens')!=usage.get('prompt_tokens',0)+usage.get('completion_tokens',0):
            failures.append('missing_or_inconsistent_provider_usage')
        else:tokens.append(usage['total_tokens'])
    seal=root/'seal.json'
    if seal.exists():
        for path,value in json.loads(seal.read_text()).items():
            if not (root/path).is_file() or sha((root/path).read_bytes())!=value:failures.append('sealed_artifact_mismatch:'+path)
    return {'run_id':manifest['run_id'],'runtime_kind':manifest['runtime_kind'],'status':'INCONCLUSIVE' if failures else 'RECONCILED',
        'failures':sorted(set(failures)),'submitted_attempts':sum(r['event'] in ('reserved','denied') for r in rows),
        'dispatched_attempts':len(reservations),'response_count':len(responses),'failed_requests':len(errors),
        'confirmed_server_completions':completed_generations,'provider_reported_tokens_for_captured_successes':sum(tokens),
        'complete_total_tokens':sum(tokens) if not failures else None,'actual_live_inference':manifest['runtime_kind'] in ('native','native_instrumented'),
        'note':'Instrumented native accounting reconciles exact task/response identities; fixture results are not Qwen validation. Legacy native mode remains gated.'}


class Experiment:
    def __init__(self,output,*,max_calls=8,max_seconds=90,lease_path=DEFAULT_LEASE,fixture_command=None,native_certificate=None,authorization=None):
        self.native=None
        if native_certificate is not None:
            from .native_gate import validate
            self.native=validate(native_certificate,authorization,max_calls,max_seconds)
        cap=64 if self.native else 8
        if type(max_calls) is not int or not 1<=max_calls<=cap or type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0<max_seconds<=90:raise ValueError('Experiment cap is 1..8 calls and at most 90 seconds')
        if fixture_command is None and not self.native:
            raise ValueError('Live inference disabled: native request/response reconciliation is not yet verified; use offline replay')
        fixture=Path(__file__).resolve().parents[2]/'tests/fixtures/experiment_runtime.py'
        if not self.native and (len(fixture_command)!=2 or Path(fixture_command[0]).resolve()!=Path(sys.executable).resolve() or Path(fixture_command[1]).resolve()!=fixture.resolve()):
            raise ValueError('Only the bundled explicit fake runtime may use fixture mode')
        self.output=Path(output);self.limit=max_calls;self.max_seconds=max_seconds;self.lease_path=lease_path
        self.command=fixture_command;self.run_id=uuid.uuid4().hex;self.owner_pid=os.getpid();self.lock=threading.RLock();self.calls=0;self.closed=False;self.cancelled=False

    def _event(self,event,**fields):
        rows=events(self.output);record={'sequence':len(rows),'previous_hash':rows[-1]['hash'] if rows else None,'run_id':self.run_id,
            'event':event,'elapsed_seconds':time.monotonic()-self.started,**fields}
        record['hash']=sha(json.dumps(record,sort_keys=True).encode())
        with (self.output/'events.jsonl').open('a') as f:f.write(json.dumps(record,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())

    def __enter__(self):
        if self.output.exists():raise ValueError('Experiment destination exists; restart is audit-only')
        self.lease=runtime_lease(self.lease_path);self.lease_handle=self.lease.__enter__()
        try:
            self.output.mkdir(parents=True);(self.output/'requests').mkdir();self.started=time.monotonic()
            if self.native:
                from .native_gate import begin
                self.authorization_ledger=begin(self.native,self.run_id)
            self.private=Path(tempfile.mkdtemp(prefix='sr-',dir='/tmp'));os.chmod(self.private,0o700)
            self.key=secrets.token_urlsafe(32);keyfile=self.private/'key';keyfile.write_text(self.key+'\n');os.chmod(keyfile,0o600)
            self.socket=self.private/'model.sock'
            fixture_copy=self.private/'fixture.py'
            native_env={}
            if self.native:
                command=[self.native['binary'],'-m',self.native['model'],'--host',str(self.socket),'--api-key-file',str(keyfile),'-c','4096','-np','1','--no-warmup','--no-webui','--no-context-shift','--no-slots']
                self.permits=self.private/'permits';self.permits.mkdir(mode=0o700)
                native_env={'SOURCEROI_NATIVE_AUDIT':str(self.output.resolve()/'native-events.jsonl'),
                    'SOURCEROI_NATIVE_PERMITS':str(self.permits),'SOURCEROI_NATIVE_MAX_CALLS':str(self.limit),'SOURCEROI_NATIVE_MAX_SECONDS':str(self.max_seconds)}
            else:
                fixture_copy.write_bytes(Path(self.command[1]).read_bytes())
                command=[sys.executable,str(fixture_copy),'--socket',str(self.socket),'--key-file',str(keyfile)]
            write_once(self.output/'manifest.json',{'version':1,'run_id':self.run_id,'max_calls':self.limit,'max_seconds':self.max_seconds,
                'runtime_kind':'native_instrumented' if self.native else 'fixture','owner_pid':self.owner_pid,'command_hash':sha(json.dumps(command if self.native else self.command).encode()),'runtime_command':command if self.native else None,'transport':'private_authenticated_UNIX_socket',
                'fixture_source_sha256':None if self.native else sha(fixture_copy.read_bytes()),'native_certificate':self.native,
                'scope':'Authorized instrumented native runtime' if self.native else 'Explicit fake runtime protocol only; no model weights or real inference'})
            spec=self.private/'worker.json';write_once(spec,{'output':str(self.output.resolve()),'private_dir':str(self.private),'run_id':self.run_id,'command':command,'max_seconds':self.max_seconds,'environment':native_env})
            read_fd,self.control=os.pipe()
            try:
                self.worker=subprocess.Popen([sys.executable,str(Path(__file__).with_name('experiment_worker.py')),'--spec',str(spec),'--parent-fd',str(read_fd)],
                    pass_fds=(read_fd,self.lease_handle.fileno()),close_fds=True,start_new_session=True)
            finally:os.close(read_fd)
            def retire_orphan_group():
                self.worker.wait()
                try:os.killpg(self.worker.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            self.watchdog=threading.Thread(target=retire_orphan_group,daemon=True);self.watchdog.start()
            self.client=httpx.Client(transport=httpx.HTTPTransport(uds=str(self.socket)),base_url='http://localhost',trust_env=False)
            while True:
                if self.worker.poll() is not None or time.monotonic()-self.started>=min(20 if self.native else 8,self.max_seconds):raise RuntimeError('Fixture runtime failed startup')
                try:
                    response=self.client.get('/health',headers={'Authorization':'Bearer '+self.key},timeout=.2)
                    if response.status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.02)
            self._event('runtime_ready');return self
        except BaseException:
            self.close();raise

    def post(self,url,body,timeout=30,*_args,**_kwargs):
        # Check before touching a lock potentially inherited held across fork.
        if os.getpid()!=self.owner_pid:raise RuntimeError('Experiment handles cannot be used from another process')
        with self.lock:
            if self.closed:raise RuntimeError('Experiment is closed')
            path=urlparse(url).path
            if path not in ('/v1/chat/completions','/tokenize'):raise ValueError('Uncontrolled runtime route refused')
            if self.native and path=='/tokenize':raise ValueError('Native experiment disables auxiliary routes; no hidden tokenizer traffic')
            if path=='/tokenize':
                self._event('tokenizer_request')
                return self.client.post(path,json=body,headers={'Authorization':'Bearer '+self.key},timeout=min(timeout,self.remaining())).json()
            request_id=self.run_id+'-'+str(self.calls+1)
            if self.calls>=self.limit or self.cancelled or self.remaining()<=0 or body.get('stream') or body.get('n',1)!=1 or body.get('best_of',1)!=1:
                name=f'requests/denied-{len(events(self.output)):03d}.json';write_once(self.output/name,body)
                self._event('denied',reason='budget_cancel_or_streaming',request_id=request_id,artifact=name,artifact_sha256=sha((self.output/name).read_bytes()))
                raise ValueError('Generation denied before dispatch')
            if self.native:
                from .native_gate import reserve
                reserve(self.authorization_ledger,self.run_id,request_id)
            self.calls+=1
            name=f'requests/{self.calls:03d}-request.json';write_once(self.output/name,body)
            self._event('reserved',request_id=request_id,artifact=name,artifact_sha256=sha((self.output/name).read_bytes()))
            wire=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            if self.native:
                with (self.permits/request_id).open('xb') as permit:permit.write(wire);permit.flush();os.fsync(permit.fileno())
            captured_response=None
            try:
                response=self.client.post(path,content=wire,headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key,'X-SourceROI-Request':request_id},timeout=min(timeout,self.remaining()))
                response_name=f'requests/{self.calls:03d}-response.json'
                # Preserve body/status even on HTTP failure; never retry implicitly.
                write_once(self.output/response_name,{'status_code':response.status_code,'body':response.text})
                captured_response=response_name
                response.raise_for_status();data=response.json()
                self._event('response',request_id=request_id,usage=data.get('usage'),artifact=response_name,artifact_sha256=sha((self.output/response_name).read_bytes()))
                return data
            except BaseException as exc:
                evidence={'artifact':captured_response,'artifact_sha256':sha((self.output/captured_response).read_bytes())} if captured_response else {}
                self._event('request_failed',request_id=request_id,error_type=type(exc).__name__,**evidence)
                raise

    def remaining(self):return max(0,self.max_seconds-(time.monotonic()-self.started))

    def configure(self,cfg):
        local=deepcopy(cfg);local['_experiment_transport']=self.post
        local['model']={**local['model'],'local_only':True,'base_url':'http://127.0.0.1:1/v1'}
        return local

    def cancel(self):
        self.cancelled=True
        if getattr(self,'control',None) is not None:
            try:os.write(self.control,b'cancel')
            except OSError:pass
            os.close(self.control);self.control=None

    def close(self):
        if self.closed:return
        if getattr(self,'control',None) is not None:
            try:os.write(self.control,b'stop')
            except OSError:pass
            os.close(self.control);self.control=None
        worker=getattr(self,'worker',None)
        if worker is not None:
            try:worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.terminate();worker.wait(timeout=5)
            if getattr(self,'watchdog',None):self.watchdog.join(timeout=2)
        try:
            with self.lock:
                self.closed=True
                if getattr(self,'client',None):self.client.close()
                if (self.output/'manifest.json').exists():
                    if self.native and getattr(self,'authorization_ledger',None):
                        from .native_gate import finish
                        write_once(self.output/'authorization-ledger.json',finish(self.authorization_ledger))
                    try:audit=reconcile(self.output)
                    except (ValueError,KeyError):audit={'status':'INCONCLUSIVE','run_id':self.run_id,'failures':['integrity_error_during_close'],'complete_total_tokens':None}
                    write_once(self.output/'reconciliation.json',audit)
                    write_once(self.output/'seal.json',{str(p.relative_to(self.output)):sha(p.read_bytes()) for p in self.output.rglob('*') if p.is_file()})
        finally:
            if getattr(self,'private',None):shutil.rmtree(self.private,ignore_errors=True)
            if getattr(self,'lease_handle',None) is not None:self.lease.__exit__(None,None,None);self.lease_handle=None

    def __exit__(self,*_):self.close()
