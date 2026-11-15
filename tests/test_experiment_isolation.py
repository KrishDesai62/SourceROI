"""Failure injection against an explicit fixture runtime, never local Qwen."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import httpx
import pytest
from sourceroi.live.experiment import Experiment,reconcile,events,runtime_lease
COMMAND=[sys.executable,str(Path(__file__).parent/'fixtures/experiment_runtime.py')]
URL='http://127.0.0.1:1/v1/chat/completions'
def runtime(tmp_path,**kwargs):return Experiment(tmp_path/'run',lease_path=tmp_path/'lease',fixture_command=COMMAND,**kwargs)

def test_serialized_concurrent_attempts_enforce_budget_and_reconcile(tmp_path):
    with runtime(tmp_path,max_calls=3) as runner:
        def request(_):
            try:return runner.post(URL,{'messages':[]})
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(request,range(8)))
        assert sum(x is not None for x in results)==3
    report=reconcile(tmp_path/'run')
    assert report['status']=='RECONCILED' and report['dispatched_attempts']==3
    assert report['submitted_attempts']==8 and report['complete_total_tokens']==21
    assert report['actual_live_inference'] is False and not runner.private.exists()

def test_failed_retry_attempts_are_counted_usage_unknown(tmp_path):
    with runtime(tmp_path,max_calls=2) as runner:
        for _ in range(2):
            with pytest.raises(httpx.HTTPStatusError):runner.post(URL,{'mode':'fail'})
        with pytest.raises(ValueError):runner.post(URL,{})
    report=reconcile(tmp_path/'run')
    assert report['dispatched_attempts']==2 and report['failed_requests']==2
    assert report['complete_total_tokens'] is None and report['status']=='INCONCLUSIVE'
    assert 'server_response_mismatch' not in report['failures']
    assert len(list((tmp_path/'run/requests').glob('*-response.json')))==2

def test_untracked_unauthorized_request_never_generates_and_invalidates_audit(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        with httpx.Client(transport=httpx.HTTPTransport(uds=str(runner.socket)),base_url='http://localhost') as client:
            assert client.post('/v1/chat/completions',json={}).status_code==401
        runner.post(URL,{})
    report=reconcile(tmp_path/'run')
    assert report['confirmed_server_completions']==1
    assert 'untracked_unauthorized_request_attempt' in report['failures']

def test_untracked_authorized_traffic_is_detected_not_called_complete(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        with httpx.Client(transport=httpx.HTTPTransport(uds=str(runner.socket)),base_url='http://localhost') as client:
            client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+runner.key},json={})
    assert 'server_dispatch_mismatch' in reconcile(tmp_path/'run')['failures']

def test_missing_usage_never_becomes_zero_cost_proof(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:runner.post(URL,{'mode':'no_usage'})
    assert reconcile(tmp_path/'run')['complete_total_tokens'] is None

def test_cancel_interrupts_generation_and_records_uncertainty(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        errors=[]
        def request():
            try:runner.post(URL,{'mode':'delay'})
            except Exception as exc:errors.append(type(exc).__name__)
        thread=threading.Thread(target=request);thread.start();deadline=time.monotonic()+3
        while 'accepted_chat' not in (tmp_path/'run/server.log').read_text() and time.monotonic()<deadline:time.sleep(.01)
        runner.cancel();thread.join(timeout=4);assert not thread.is_alive() and errors
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'
    assert json.loads((tmp_path/'run/worker-exit.json').read_text())['reason']=='cancelled'

def test_runtime_crash_and_restart_are_audit_only(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        with pytest.raises(httpx.HTTPError):runner.post(URL,{'mode':'crash'})
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'
    with pytest.raises(ValueError,match='destination exists'):
        with runtime(tmp_path):pass
    assert len([e for e in events(tmp_path/'run') if e['event']=='reserved'])==1

def test_budget_deadline_prevents_new_requests(tmp_path):
    with runtime(tmp_path,max_calls=1,max_seconds=.8) as runner:
        time.sleep(.9)
        with pytest.raises(ValueError):runner.post(URL,{})
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'
    assert not [e for e in events(tmp_path/'run') if e['event']=='reserved']

def test_artifact_and_event_integrity_tampering_detected(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:runner.post(URL,{})
    (tmp_path/'run/requests/001-request.json').write_text('{"changed":true}')
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'
    with (tmp_path/'run/events.jsonl').open('a') as f:f.write('{broken\n')
    with pytest.raises(ValueError):reconcile(tmp_path/'run')

def test_runtime_test_lease_is_exclusive_and_live_is_disabled(tmp_path):
    with runtime_lease(tmp_path/'lease'):
        with pytest.raises(RuntimeError,match='lease occupied'):
            with runtime_lease(tmp_path/'lease'):pass
    with pytest.raises(ValueError,match='Live inference disabled'):Experiment(tmp_path/'real')

def test_unexpected_owner_death_retires_child_runtime(tmp_path):
    script="""
from sourceroi.live.experiment import Experiment
import os,sys
runner=Experiment(sys.argv[1],lease_path=sys.argv[2],fixture_command=[sys.executable,sys.argv[3]])
runner.__enter__()
os._exit(9)
"""
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path/'run'),str(tmp_path/'lease'),COMMAND[1]],timeout=8)
    assert result.returncode==9
    deadline=time.monotonic()+5
    while not (tmp_path/'run/worker-exit.json').exists() and time.monotonic()<deadline:time.sleep(.02)
    assert json.loads((tmp_path/'run/worker-exit.json').read_text())['reason']=='owner_disappeared'
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'
    # The exit record precedes final private-directory cleanup and process exit.
    # The lease must remain held until that cleanup actually finishes.
    deadline=time.monotonic()+3
    while True:
        try:
            with runtime_lease(tmp_path/'lease'):break
        except RuntimeError:
            if time.monotonic()>=deadline:pytest.fail('Supervisor did not release the retired runtime lease')
            time.sleep(.02)


def test_provider_uses_owned_transport_without_open_model_port(tmp_path):
    from sourceroi.live.provider import run_chat
    with runtime(tmp_path,max_calls=1) as runner:
        cfg=runner.configure({'model':{'name':'fixture','max_output_tokens':20},'sources':[]})
        result=run_chat('Explicit fixture request, not factual validation',[],cfg)
        assert result['answer']=='fixture' and result['input_tokens']==5
    assert reconcile(tmp_path/'run')['status']=='RECONCILED'


def test_pytest_session_holds_production_runtime_lease():
    with pytest.raises(RuntimeError,match='lease occupied'):
        with runtime_lease():pass


def test_real_or_arbitrary_program_cannot_be_mislabeled_as_fixture(tmp_path):
    with pytest.raises(ValueError,match='bundled explicit fake'):
        Experiment(tmp_path/'wrong',fixture_command=[sys.executable,'arbitrary_native_wrapper.py'])


def test_configuring_local_model_does_not_expand_existing_budget(tmp_path,monkeypatch):
    from tools import local_llm
    model=tmp_path/'model';model.mkdir();project=tmp_path/'project';project.mkdir()
    (model/'manifest.json').write_text(json.dumps({'model_file':'fixture-not-loaded'}))
    (project/'project.json').write_text(json.dumps({'settings':{'max_model_calls_per_run':3}}))
    monkeypatch.setattr(local_llm,'checksum',lambda _:local_llm.MODEL['sha256'])
    assert local_llm.configure(project,model)['settings']['max_model_calls_per_run']==3


def test_supervisor_death_cannot_leave_runtime_serving(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        errors=[]
        def request():
            try:runner.post(URL,{'mode':'delay'})
            except Exception as exc:errors.append(type(exc).__name__)
        thread=threading.Thread(target=request);thread.start();deadline=time.monotonic()+3
        while 'accepted_chat' not in (tmp_path/'run/server.log').read_text() and time.monotonic()<deadline:time.sleep(.01)
        runner.worker.kill();thread.join(timeout=3)
        assert not thread.is_alive() and errors
    assert reconcile(tmp_path/'run')['status']=='INCONCLUSIVE'


def test_multiple_completion_or_stream_requests_are_not_dispatched(tmp_path):
    with runtime(tmp_path,max_calls=1) as runner:
        for body in ({'n':2},{'best_of':2},{'stream':True}):
            with pytest.raises(ValueError):runner.post(URL,body)
    report=reconcile(tmp_path/'run')
    assert report['submitted_attempts']==3 and report['dispatched_attempts']==0


def test_inherited_handle_rejected_before_any_inherited_lock(tmp_path,monkeypatch):
    import sourceroi.live.experiment as module
    with runtime(tmp_path,max_calls=1) as runner:
        original=runner.lock
        class ForbiddenLock:
            def __enter__(self):pytest.fail('Forked handle must not touch an inherited lock')
            def __exit__(self,*_):pass
        runner.lock=ForbiddenLock()
        try:
            with monkeypatch.context() as patch:
                patch.setattr(module.os,'getpid',lambda:runner.owner_pid+1)
                with pytest.raises(RuntimeError,match='another process'):runner.post(URL,{})
        finally:runner.lock=original
