"""Integration tests run against a real local HTTP server. No paid API/key needed."""
import json
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sourceroi.live.api import create_app
from sourceroi.live.config import read_config
from sourceroi.live.engine import run, compare_runs, preflight, optimize_configurations
from sourceroi.live import db
from sourceroi.live.grade import grade, wilson_interval
from sourceroi.live.ingest import make_chunks, scan_sources
from sourceroi.live.provider import ProviderError, run_external
from sourceroi.live.cli import make_workspace


class FakeModel(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, *_):
        pass
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        incoming = json.loads(self.rfile.read(length))
        FakeModel.requests.append(incoming)
        if self.path.endswith('/chat/completions'):
            evidence = incoming['messages'][1]['content']
            # Fake only for testing the integration; not real model answers.
            question=evidence.rsplit('QUESTION:',1)[-1].lower()
            if 'Revenue: 42' in evidence and 'revenue' in question:
                answer = '42'
            elif 'Cash balance: 7' in evidence and 'cash balance' in question:
                answer = '7'
            else:
                answer = 'INSUFFICIENT_EVIDENCE'
            body = {'choices':[{'message':{'content':json.dumps({'answer':answer,'citations':[]})}}],
                    'usage':{'prompt_tokens':100,'completion_tokens':20}}
        elif self.path.endswith('/agent'):
            if incoming.get('allowed_source_ids'):
                answer = '42'
            else:
                answer = 'INSUFFICIENT_EVIDENCE'
            body = {'answer':answer,'citations':[],'filter_applied':True,
                    'usage':{'prompt_tokens':9,'completion_tokens':3,'model_cost_usd':0.002,'data_cost_usd':0.005}}
        elif self.path.endswith('/bad-agent'):
            body = {'answer':'42','filter_applied':False}
        else:
            self.send_error(404); return
        encoded=json.dumps(body).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(encoded))); self.end_headers();self.wfile.write(encoded)


@pytest.fixture(scope='module')
def mock_model():
    server = ThreadingHTTPServer(('127.0.0.1',0),FakeModel)
    worker = threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    yield f'http://127.0.0.1:{server.server_port}/v1'
    server.shutdown();server.server_close()


@pytest.fixture
def workspace(tmp_path,mock_model):
    root=tmp_path/'ws'
    (root/'sources'/'filings').mkdir(parents=True)
    (root/'sources'/'financial').mkdir(parents=True)
    (root/'sources'/'filings'/'alpha.md').write_text('# Alpha Report\nCompany: Alpha\nRevenue: 42\n')
    (root/'sources'/'financial'/'cash.md').write_text('# Alpha Cash\nCompany: Alpha\nCash balance: 7\n')
    benchmark=[{'id':'R1','question':'What is Alpha revenue?','expected':'42','scoring':'exact'},
               {'id':'C1','question':'What is Alpha cash balance?','expected':'7','scoring':'exact'}]
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in benchmark)+'\n')
    cfg={'id':'real-test','name':'Alpha Test','runner':'rag_chat','benchmark':'benchmark.jsonl',
         'model':{'name':'fake-llm','base_url':mock_model,'api_key_env':'TEST_UNUSED_KEY',
                  'input_price_per_million_usd':2.0,'output_price_per_million_usd':4.0,
                  'temperature':0,'max_output_tokens':100},
         'settings':{'max_chunks':2,'chunk_chars':350,'overlap_chars':10,
                     'max_tasks_per_run':10,'max_documents_per_study':8,'max_model_calls_per_run':30},
         'sources':[{'id':'filings','name':'Filings','path':'sources/filings'},
                    {'id':'financial','name':'Financial','path':'sources/financial'}]}
    (root/'project.json').write_text(json.dumps(cfg))
    return root


def test_real_provider_tokens_and_cost(workspace):
    FakeModel.requests.clear()
    cfg=read_config(workspace)
    report=run(cfg)
    m=report['variants'][0]['metrics']
    assert m['task_count']==2 and m['passed']==2
    assert m['provider_reported_prompt_tokens']==200
    assert m['provider_reported_completion_tokens']==40
    assert m['total_cost_usd']==pytest.approx(.00056)
    assert m['mean_latency_ms']>=m['mean_retrieval_ms']
    assert all(t['end_to_end_latency_ms']>0 for t in report['variants'][0]['tasks'])
    assert report['document_count']==2
    for request in FakeModel.requests:
        prompt=request['messages'][1]['content']
        assert '"expected"' not in prompt
    assert m['accuracy_ci95'][0]<m['accuracy_ci95'][1]


def test_live_source_ablation_and_document_ablation(workspace):
    cfg=read_config(workspace)
    report=run(cfg,mode='ablation')
    assert report['api_calls']==6
    assert len(report['variants'])==3
    assert any(r['lost_tasks'] for r in report['impacts'])
    ids=sorted(report['manifest'])
    docs=run(cfg,mode='document_ablation',document_ids=ids)
    assert len(docs['impacts'])==2
    assert sum(len(r['lost_tasks']) for r in docs['impacts'])>=2
    assert all('excluded_documents' in r for r in docs['impacts'])


def test_optimizer_selects_lower_cost_qualifying_source_set(workspace, monkeypatch):
    cfg=read_config(workspace)
    market = workspace/'sources'/'market'
    market.mkdir(exist_ok=True)
    (market/'noise.md').write_text('# Market Outlook\nCompany: Alpha\nAlpha revenue increased materially. Alpha revenue forecast is 42 and the market expects 42 for the year.\n')
    cfg['sources'].append({'id':'market','name':'Market','path':'sources/market','per_call_price_usd':0.03})
    cfg['settings']['max_chunks'] = 5
    (workspace/'project.json').write_text(json.dumps(cfg))
    cfg = read_config(workspace)

    def fake_run_chat(question, context, cfg):
        has_revenue = any('Revenue' in chunk['text'] for chunk in context)
        has_cash = any('Cash balance' in chunk['text'] for chunk in context)
        if 'revenue' in question.lower() and has_revenue:
            answer = '42'
        elif 'cash' in question.lower() and has_cash:
            answer = '7'
        else:
            answer = 'INSUFFICIENT_EVIDENCE'
        prompt_tokens = 75 + 25 * len(context)
        completion_tokens = 10
        model_cost = round((prompt_tokens * 2.0 + completion_tokens * 4.0) / 1_000_000, 8)
        citations = [chunk['id'] for chunk in context if chunk['id'].startswith('filings::') or chunk['id'].startswith('financial::')]
        return {'answer': answer, 'citations': citations, 'invalid_citations': [],
                'json_format_valid': True, 'input_tokens': prompt_tokens,
                'output_tokens': completion_tokens, 'model_cost_usd': model_cost,
                'cost_type': 'token_priced_estimate', 'data_cost_usd': 0.0,
                'model_latency_ms': 12.0, 'model_name': 'fake-llm', 'usage_source': 'provider_reported'}

    monkeypatch.setattr('sourceroi.live.engine.run_chat', fake_run_chat)
    result = optimize_configurations(cfg, quality_floor=1.0, min_groundedness=0.75, objective='cost_per_success', max_tasks=2)
    assert result['status'] == 'ok'
    assert result['recommended']['excluded_sources'] == ['market']
    assert result['recommended']['delta_cost_usd'] is not None and result['recommended']['delta_cost_usd'] < 0
    assert result['recommended']['input_token_reduction_pct'] is not None and result['recommended']['input_token_reduction_pct'] > 0
    assert result['recommended']['accuracy'] >= 1.0


def test_detect_data_regression_and_compare_runs(workspace):
    cfg=read_config(workspace)
    before=run(cfg)
    first=db.begin(cfg,'baseline',[]);db.finish(cfg,first,before)
    original=workspace/'sources'/'filings'/'alpha.md'
    original.write_text(original.read_text().replace('Revenue: 42','Revenue: 999'))
    changed=read_config(workspace)
    after=run(changed)
    second=db.begin(changed,'baseline',[]);db.finish(changed,second,after)
    delta=compare_runs(db.get(changed,first),db.get(changed,second))
    assert 'R1' in delta['comparison']['lost_tasks']
    assert 'filings::alpha.md' in delta['changed_documents']
    assert first != second
    assert len(db.list_runs(changed))==2


def test_api_health_project_and_live_job(workspace):
    app=create_app(workspace)
    with TestClient(app) as client:
        assert client.get('/api/v2/health').json()['status']=='ok'
        proj=client.get('/api/v2/project').json()
        assert proj['document_count']==2 and proj['task_count']==2
        assert 'api_key' not in json.dumps(proj).lower()
        assert client.post('/api/v2/runs',json={'mode':'baseline'}).status_code==400
        call=client.post('/api/v2/runs',json={'mode':'baseline','acknowledge_model_calls':True})
        assert call.status_code==202,call.text
        rid=call.json()['id']
        for _ in range(100):
            response=client.get('/api/v2/runs/'+rid).json()
            if response['status']!='running':break
            time.sleep(.05)
        assert response['status']=='completed',response
        assert response['report']['variants'][0]['metrics']['passed']==2
        assert client.get('/').status_code==200
        assert client.get('/app.js').status_code==200
        assert client.get('/styles.css').status_code==200


def test_existing_agent_requires_ablation_filter_ack(workspace,mock_model):
    cfg=read_config(workspace)
    cfg['runner']='http_agent'
    cfg['agent']={'url':mock_model.replace('/v1','')+'/agent'}
    good=run_external('Revenue?', ['filings'], [], [], cfg, 'A')
    assert good['answer']=='42' and good['model_cost_usd']==.002
    cfg['agent']['url']=mock_model.replace('/v1','')+'/bad-agent'
    with pytest.raises(ProviderError,match='filter'):
        run_external('Revenue?', ['filings'], [], [], cfg, 'A')


def test_unpriced_costs_are_unknown(workspace):
    cpath=workspace/'project.json'
    data=json.loads(cpath.read_text())
    data['model']['input_price_per_million_usd']=None
    data['model']['output_price_per_million_usd']=None
    cpath.write_text(json.dumps(data))
    result=run(read_config(workspace))
    metrics=result['variants'][0]['metrics']
    assert metrics['total_cost_usd'] is None
    assert metrics['provider_reported_prompt_tokens']==200


def test_unknown_credential_refused(workspace):
    cfg=read_config(workspace)
    cfg['model']['base_url']='https://api.example.com/v1'
    cfg['model']['api_key_env']='THIS_ENV_IS_NOT_SET_12345'
    with pytest.raises(ProviderError,match='Missing'):
        run(cfg,max_tasks=1)


def test_benchmark_version_change_is_blocked(workspace):
    cfg=read_config(workspace)
    old=run(cfg)
    baseline=db.begin(cfg,'baseline',[]);db.finish(cfg,baseline,old)
    benchmark=workspace/'benchmark.jsonl'
    benchmark.write_text(benchmark.read_text().replace('Alpha revenue','Alpha 2025 revenue'))
    new=run(read_config(workspace))
    candidate=db.begin(cfg,'baseline',[]);db.finish(cfg,candidate,new)
    with pytest.raises(ValueError,match='Benchmark changed'):
        compare_runs(db.get(cfg,baseline),db.get(cfg,candidate))


def test_source_and_workspace_path_safety(workspace):
    cpath=workspace/'project.json'
    data=json.loads(cpath.read_text())
    data['sources'][0]['path']='../../../../etc'
    cpath.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='escapes'):
        read_config(workspace)


def test_importer_creates_real_project(tmp_path):
    docs=tmp_path/'incoming';docs.mkdir();(docs/'research').mkdir()
    (docs/'research'/'facts.csv').write_text('company,revenue\nalpha,42\n')
    (docs/'note.txt').write_text('Actual user supplied text')
    out=make_workspace(str(docs),str(tmp_path/'newproj'))
    cfg=read_config(out)
    assert len(cfg['sources'])==2
    d,chunks=scan_sources(cfg)
    assert len(d)==2
    assert any('alpha' in x['text'] for x in chunks)
    assert preflight(cfg)['task_count']==0


def test_exact_and_numeric_grade_and_wilson():
    assert grade('Sales $1,234',{'expected':'1234','scoring':'numeric'})
    assert not grade('5',{'expected':'7','scoring':'numeric','tolerance':1})
    assert grade('Growth is 14 percent',{'expected':'14 percent','scoring':'contains'})
    assert wilson_interval(0, 0) is None
    assert make_chunks('Hello world\n'*100, 260, 30)


def test_run_call_cap_rejects_expensive_study(workspace):
    cfg=read_config(workspace)
    cfg['settings']['max_model_calls_per_run']=3
    with pytest.raises(ValueError,match='cap'):
        run(cfg,mode='ablation')
