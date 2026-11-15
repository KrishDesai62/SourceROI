"""Compile the same native admission/task ledger used by the instrumented build.

These are deterministic protocol checks, not model efficacy or independent review.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from sourceroi.live.native_accounting import inspect_native
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def probe(tmp_path_factory):
    root=tmp_path_factory.mktemp('native-probe');binary=root/'probe'
    compiler=shutil.which('clang++') or shutil.which('g++')
    if not compiler:pytest.skip('Native C++ compiler unavailable')
    subprocess.run([compiler,'-std=c++17','-pthread','-I',str(ROOT/'sourceroi/live/native'),str(ROOT/'tests/fixtures/native_accounting_probe.cpp'),'-o',str(binary)],check=True,capture_output=True)
    return binary


def run_probe(probe,root,mode='normal',permit=True,limit='1',seconds='10'):
    permits=root/'permits';permits.mkdir()
    if permit:(permits/'abc-1').write_text('{}')
    env={**os.environ,'SOURCEROI_NATIVE_AUDIT':str(root/'native-events.jsonl'),'SOURCEROI_NATIVE_PERMITS':str(permits),
         'SOURCEROI_NATIVE_MAX_CALLS':limit,'SOURCEROI_NATIVE_MAX_SECONDS':seconds}
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    result=subprocess.run([str(probe),mode],env=env,capture_output=True,preexec_fn=limits)
    rows=[json.loads(l) for l in (root/'native-events.jsonl').read_text().splitlines()]
    return result,rows


def test_native_normal_protocol_independently_reconciles(probe,tmp_path):
    result,records=run_probe(probe,tmp_path)
    assert result.returncode==0
    assert [r['event'] for r in records]==['admitted','bound','dispatched','completed','http_response']
    (tmp_path/'request.json').write_text('{}')
    body=records[-1]['body'];(tmp_path/'response.json').write_text(json.dumps({'status_code':200,'body':body}))
    reservation=[{'request_id':'abc-1','artifact':'request.json'}]
    response=[{'request_id':'abc-1','artifact':'response.json','usage':json.loads(body)['usage']}]
    audit=inspect_native(tmp_path,{'max_calls':1},reservation,response,[])
    assert audit['failures']==[] and audit['confirmed_completions']==1
    records[3]['input_tokens']=999
    (tmp_path/'native-events.jsonl').write_text('\n'.join(json.dumps(r) for r in records))
    assert 'native_token_counter_mismatch:abc-1' in inspect_native(tmp_path,{'max_calls':1},reservation,response,[])['failures']


@pytest.mark.parametrize('mode',['untracked','child','double_finish'])
def test_native_aborts_untracked_child_and_duplicate_generation(probe,tmp_path,mode):
    result,records=run_probe(probe,tmp_path,mode)
    assert result.returncode!=0
    assert any(r['event'] in ('untracked_task','untracked_finish') for r in records)


@pytest.mark.parametrize('mode',['duplicate','cancel','failed'])
def test_native_replays_failures_and_cancellations_fail_closed(probe,tmp_path,mode):
    result,records=run_probe(probe,tmp_path,mode)
    assert result.returncode==0
    assert any(r['event'] in ('denied','cancelled','failed') for r in records)
    (tmp_path/'request.json').write_text('{}')
    audit=inspect_native(tmp_path,{'max_calls':1},[{'request_id':'abc-1','artifact':'request.json'}],[],[])
    assert audit['failures']


@pytest.mark.parametrize('permit,limit,seconds',[(False,'1','10'),(True,'0','10'),(True,'1','0')])
def test_native_requires_single_use_permit_and_server_budgets(probe,tmp_path,permit,limit,seconds):
    result,records=run_probe(probe,tmp_path,permit=permit,limit=limit,seconds=seconds)
    assert result.returncode==3 and [r['event'] for r in records]==['denied']


def test_default_native_gate_stays_closed(tmp_path):
    from sourceroi.live.experiment import Experiment
    with pytest.raises(ValueError,match='Live inference disabled'):Experiment(tmp_path/'no-run')
    assert not (tmp_path/'no-run').exists()


def test_authorization_is_single_use_and_has_durable_attempt_cap(tmp_path,monkeypatch):
    from sourceroi.live import native_gate as gate
    monkeypatch.setattr(gate,'ROOT',tmp_path)
    native={'authorization':{'scope':'accounting_smoke','authorization_id':'existing-two-call-accounting-smoke','max_attempts':2,'max_seconds':30}}
    ledger=gate.begin(native,'run')
    gate.reserve(ledger,'run','r1');gate.reserve(ledger,'run','r2')
    with pytest.raises(ValueError):gate.reserve(ledger,'run','r3')
    gate.finish(ledger)
    with pytest.raises(FileExistsError):gate.begin(native,'different-run')
    assert json.loads(Path(ledger).read_text())['attempts']==['r1','r2']


def test_native_audit_missing_http_or_task_body_never_reconciles(probe,tmp_path):
    result,records=run_probe(probe,tmp_path)
    (tmp_path/'request.json').write_text('{"wrong":true}')
    (tmp_path/'response.json').write_text(json.dumps({'status_code':200,'body':records[-1]['body']}))
    requests=[{'request_id':'abc-1','artifact':'request.json'}]
    responses=[{'request_id':'abc-1','artifact':'response.json','usage':json.loads(records[-1]['body'])['usage']}]
    assert 'native_request_body_mismatch:abc-1' in inspect_native(tmp_path,{'max_calls':1},requests,responses,[])['failures']
    (tmp_path/'native-events.jsonl').write_text('\n'.join(json.dumps(r) for r in records[:-1]))
    assert inspect_native(tmp_path,{'max_calls':1},requests,responses,[])['failures']
