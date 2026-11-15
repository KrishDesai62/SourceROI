from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,run_data_ci
from sourceroi.live.diagnosis import diagnose,test_source_addition as source_addition
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.ingest import load_benchmark,scan_sources
from sourceroi.live.policies import select_context
from sourceroi.live.validation import Budget
from tools.validate_study import create_project,simulated_model


def chunk(id,text,title='Report'):
    return {'id':id,'document_id':id.split('#')[0],'source_id':'a','text':text,'title':title}


def evidence_cfg(fallback=False):
    return {'sources':[{'id':'a','reliability':.8}], 'settings':{'max_chunks':3,'retrieval_policy':{'name':'evidence_aware','k':3,'fallback':fallback}}}


def test_no_answers_or_task_labels_enter_evidence_selection():
    cfg=evidence_cfg()
    chunks=[chunk('a::one#0','Acme revenue is 42.'),chunk('a::two#0','Acme cash is 7.')]
    selected,trace=select_context('Compare Acme revenue and cash.',chunks,cfg)
    assert len(selected)==2
    assert trace['requirements']['multiple_documents']
    assert 'expected' not in trace and 'answer' not in trace


def test_conflicting_quantities_are_not_deduplicated_away():
    cfg=evidence_cfg()
    chunks=[chunk('a::one#0','Acme revenue is 42.'),chunk('a::two#0','Acme revenue is 7.')]
    selected,trace=select_context('What is Acme revenue?',chunks,cfg)
    assert len(selected)==2
    assert trace['potential_conflicts']
    assert 'potential_conflict_preserved' in trace['uncertainty_signals']


def test_uncertain_evidence_falls_back_before_generation():
    cfg=evidence_cfg(True)
    chunks=[chunk('a::one#0','Acme sales 42.'),chunk('a::two#0','Unrelated information.')]
    selected,trace=select_context('Compare Acme and Missingco revenue.',chunks,cfg)
    assert trace['fallback_used']
    assert trace['fallback_extra_generation_calls']==0
    assert selected


def test_duplicate_removal_preserves_opposing_negation():
    cfg=evidence_cfg()
    a=chunk('a::one#0','Acme revenue is increasing rapidly this year.')
    b=chunk('a::two#0',a['text'])
    c=chunk('a::three#0','Acme revenue is not increasing rapidly this year.')
    selected,trace=select_context('Acme revenue increasing', [a,b,c],cfg)
    assert trace['removed_near_duplicates']
    assert any('not increasing' in r['text'] for r in selected)


def test_actual_token_budget_cap_and_unsupported_tokenizer():
    cfg=evidence_cfg();cfg['settings']['retrieval_policy']['max_context_tokens']=2
    chunks=[chunk('a::one#0','Acme revenue 42.')]
    with pytest.raises(ValueError,match='tokenizer'):
        select_context('Acme revenue',chunks,cfg)
    cfg['_context_token_counter']=lambda ctx:sum(len(c['text'].split()) for c in ctx)
    selected,trace=select_context('Acme revenue',chunks,cfg)
    assert not selected
    assert trace['measured_selection_context_tokens']<=2
    assert 'token_budget_infeasible_for_selected_evidence' in trace['uncertainty_signals']


def test_no_context_evidence_policy_does_not_query_model(tmp_path):
    create_project(tmp_path);cfg=read_config(tmp_path)
    cfg['settings']['retrieval_policy']={'name':'evidence_aware','fallback':True}
    budget=Budget({'max_model_calls_per_run':1});cfg['_experiment_budget']=budget
    task=load_benchmark(cfg)[:1]
    with patch('sourceroi.live.engine.run_chat') as model:
        result=evaluate_variant(cfg,task,[],[])
        model.assert_not_called()
    assert result['tasks'][0]['actual']=='INSUFFICIENT_EVIDENCE'
    assert result['tasks'][0]['usage_source']=='not_called_no_context'
    assert budget.calls==0


def test_duration_guard_checks_before_model_request(monkeypatch):
    guard=Budget({'max_model_calls_per_run':10,'max_run_seconds':1})
    guard.started-=2
    with pytest.raises(ValueError,match='duration'):
        guard.before()
    assert guard.calls==0


@pytest.fixture
def ci_pair(tmp_path,monkeypatch):
    root=tmp_path/'candidate';create_project(root);cfg=read_config(root)
    cfg['model']['local_only']=True
    (root/'project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}))
    cfg=read_config(root)
    frozen=tmp_path/'frozen';freeze(cfg,frozen)
    monkeypatch.setattr('sourceroi.live.engine.run_chat',simulated_model)
    return read_config(frozen),cfg


def test_data_ci_localizes_removed_reference_and_tests_repair(ci_pair):
    a,b=ci_pair
    (Path(b['_root'])/'sources/reports/Aster.txt').unlink()
    task=next(t for t in load_benchmark(b) if t['id']=='Aster-lookup')
    report=run_data_ci(a,b,task_ids=[task['id']],max_tasks=1,repair=True,ablate=True)
    assert report['verdict']=='blocked'
    assert report['comparison']['lost_tasks']==[task['id']]
    assert any('Aster.txt' in x for x in report['task_changes'][0]['plausibly_related_documents'])
    assert report['repairs'][0]['tasks']['metrics']['passed']==1
    assert report['automatically_applied'] is False
    assert not (Path(b['_root'])/'sources/reports/Aster.txt').exists()


def test_no_change_data_ci_reports_no_detected_regression(ci_pair):
    a,b=ci_pair
    report=run_data_ci(a,b,max_tasks=2)
    assert report['verdict']=='no_detected_regression'
    assert not report['changed_documents'] and not report['removed_documents']


def test_data_ci_refuses_changed_benchmark_and_snapshot_tampering(ci_pair):
    a,b=ci_pair
    path=Path(a['_root'])/'sources/reports/Aster.txt';path.write_text('changed')
    with pytest.raises(ValueError,match='immutable'):
        run_data_ci(a,b,max_tasks=1)


def test_data_ci_refuses_retrieval_config_change(ci_pair):
    a,b=ci_pair;b['settings']['max_chunks']=1
    with pytest.raises(ValueError,match='settings differ'):
        run_data_ci(a,b)


def test_missing_information_diagnoses_distinct_paths():
    task={'id':'q','question':'Acme revenue','evidence':[{'document_id':'a::one','quote':'Revenue 42'}]}
    corpus=[chunk('a::one#0','Acme Revenue 42')]
    absent=diagnose(task,{'retrieved_chunk_ids':[]},[])
    filtered=diagnose(task,{'retrieved_chunk_ids':[]},corpus)
    ignored=diagnose(task,{'retrieved_chunk_ids':['a::one#0']},corpus)
    assert absent['classification']=='reference_evidence_absent'
    assert filtered['classification']=='retrieved_then_filtered'
    assert ignored['classification']=='generation_or_scoring_failure'
    assert ignored['certainty']=='diagnostic_hypothesis'


def test_candidate_source_addition_is_measured_not_purchase_advice(tmp_path,monkeypatch):
    create_project(tmp_path);cfg=read_config(tmp_path)
    monkeypatch.setattr('sourceroi.live.engine.run_chat',simulated_model)
    tasks=[t for t in load_benchmark(cfg) if t['id']=='Aster-lookup']
    report=source_addition(cfg,tasks,scan_sources(cfg)[1],['reports'],'reports',Budget({'max_model_calls_per_run':2}))
    assert report['comparison']['gained_tasks']==['Aster-lookup']
    assert report['automatically_purchased'] is False


def test_freeze_refuses_overwrite(ci_pair):
    a,b=ci_pair
    with pytest.raises(ValueError,match='immutable'):
        freeze(b,a['_root'])


def test_data_ci_api_requires_ack_and_validates_snapshot(ci_pair):
    from sourceroi.live.api import create_app
    a,b=ci_pair;client=TestClient(create_app(b['_root']))
    snapshot=client.post('/api/v2/data-ci/freeze')
    assert snapshot.status_code==200
    sid=snapshot.json()['snapshot_id']
    assert client.post('/api/v2/data-ci',json={'snapshot_id':sid}).status_code==400
    result=client.post('/api/v2/data-ci',json={'snapshot_id':sid,'acknowledge_model_calls':True,'max_tasks':1})
    assert result.status_code==200
    assert result.json()['report']['verdict']=='no_detected_regression'
    assert client.post('/api/v2/data-ci',json={'snapshot_id':'../bad'}).status_code==422


def test_snapshot_cannot_pollute_registered_live_source(ci_pair):
    a,b=ci_pair
    with pytest.raises(ValueError,match='inside a registered source'):
        freeze(b,Path(b['_root'])/'sources/reports/snapshot')


def test_updated_document_and_source_metadata_versions_are_detected(ci_pair):
    a,b=ci_pair
    (Path(b['_root'])/'sources/reports/Aster.txt').write_text('Aster revenue: 999.')
    b['sources'][0]['reliability']=.2
    report=run_data_ci(a,b,max_tasks=1,task_ids=['Aster-lookup'])
    assert report['changed_documents']
    assert report['source_metadata_changed']
    assert report['verdict']=='blocked'


def test_critical_task_failure_escalates_severity(tmp_path,monkeypatch):
    root=tmp_path/'critical';create_project(root)
    tasks=[json.loads(x) for x in (root/'benchmark.jsonl').read_text().splitlines()]
    tasks[0]['critical']=True
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks))
    cfg=read_config(root);cfg['model']['local_only']=True
    (root/'project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}))
    cfg=read_config(root);frozen=tmp_path/'frozen';freeze(cfg,frozen)
    (root/'sources/reports/Aster.txt').unlink()
    monkeypatch.setattr('sourceroi.live.engine.run_chat',simulated_model)
    report=run_data_ci(read_config(frozen),cfg,max_tasks=1,task_ids=['Aster-lookup'])
    assert report['severity']=='critical'


def test_data_ci_cli_exports_report_and_returns_blocking_exit(ci_pair,tmp_path,capsys):
    from sourceroi.live.cli import main
    a,b=ci_pair
    (Path(b['_root'])/'sources/reports/Aster.txt').unlink()
    output=tmp_path/'report.json'
    code=main(['--project',b['_root'],'data-ci','--baseline',a['_root'],'--max-tasks','1','--output',str(output),'--allow-model-calls'])
    assert code==3
    assert json.loads(output.read_text())['verdict']=='blocked'


def test_fresh_split_audit_contains_no_detected_overlap():
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'docs/artifacts/reliability-split-audit.json').read_text())
    assert report['tasks']==24
    assert report['shared_document_ids_across_splits']==[]
    assert report['prior_exposed_title_overlap']==[]
    assert report['fivegram_near_duplicates']==[]
    assert report['test_cases_changed'] is False


def test_shared_budget_reports_study_calls_separately(tmp_path,monkeypatch):
    import shutil
    from sourceroi.live.reliability_study import run_reliability_study
    root=Path(__file__).resolve().parents[1]
    project=tmp_path/'public'
    shutil.copytree(root/'workspace/reliability-24',project,ignore=shutil.ignore_patterns('.sourceroi'))
    cfg=read_config(project)
    def model(question,context,configuration):
        return {'answer':'INSUFFICIENT_EVIDENCE','citations':[],'invalid_citations':[],
                'json_format_valid':True,'input_tokens':10,'output_tokens':2,'model_cost_usd':None,
                'data_cost_usd':0,'cost_type':'unit_test','model_latency_ms':0,'model_name':'unit-test-stub','usage_source':'unit_test'}
    monkeypatch.setattr('sourceroi.live.engine.run_chat',model)
    monkeypatch.setattr('sourceroi.live.reliability_study.count_context_tokens',lambda *args:0)
    guard=Budget({'max_model_calls_per_run':320});guard.before();guard.before()
    report=run_reliability_study(cfg,{'name':'original'},budget=guard)
    assert report['generation_calls']==guard.calls-2
    assert report['session_calls']==guard.calls
    assert report['status']=='completed'


def test_partial_ci_scope_is_explicit(ci_pair):
    a,b=ci_pair;report=run_data_ci(a,b,max_tasks=1)
    assert report['selection_mode']=='bounded_prefix_subset'
    assert report['evaluated_tasks']==1
    assert report['untested_task_count']==7
    assert report['task_coverage_fraction']==1/8


def test_present_document_evidence_is_not_misclassified_when_chunking_hides_quote(tmp_path):
    create_project(tmp_path);cfg=read_config(tmp_path)
    path=tmp_path/'sources/reports/Aster.txt';path.write_text('Acme reference that spans multiple chunks.')
    task={'id':'x','question':'Acme reference','evidence':[{'document_id':'reports::Aster.txt','quote':'reference that spans'}]}
    diagnostic=diagnose(task,{'retrieved_chunk_ids':[]},[],cfg)
    assert diagnostic['classification']=='present_not_retrieved'
    assert diagnostic['full_document_reference_hits']==1


def test_existing_model_evidence_is_protected_before_execution(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    output=tmp_path/'existing.json';output.write_text('preserve me')
    completed=subprocess.run([sys.executable,str(root/'tools/run_reliability_validation.py'),'--output',str(output),
                              '--ci-root',str(tmp_path/'unused-ci')],capture_output=True,text=True,timeout=10)
    assert completed.returncode!=0
    assert 'before any inference' in completed.stderr
    assert output.read_text()=='preserve me'
    assert not (tmp_path/'unused-ci').exists()


def test_incomplete_reliability_run_keeps_partial_evidence(tmp_path,monkeypatch):
    import shutil
    from sourceroi.live import db
    from sourceroi.live.reliability_study import run_reliability_study,export_reliability
    root=Path(__file__).resolve().parents[1];project=tmp_path/'public'
    shutil.copytree(root/'workspace/reliability-24',project,ignore=shutil.ignore_patterns('.sourceroi'))
    cfg=read_config(project);attempts=[]
    def model(question,context,configuration):
        attempts.append(1)
        if len(attempts)==2:raise RuntimeError('unit test timeout')
        return {'answer':'INSUFFICIENT_EVIDENCE','citations':[],'invalid_citations':[],'json_format_valid':True,
            'input_tokens':1,'output_tokens':1,'model_cost_usd':None,'data_cost_usd':0,'cost_type':'unit_test',
            'model_latency_ms':0,'model_name':'unit-test-stub','usage_source':'unit_test'}
    monkeypatch.setattr('sourceroi.live.engine.run_chat',model)
    with pytest.raises(RuntimeError,match='unit test timeout'):
        run_reliability_study(cfg,{'name':'original'})
    saved=db.get(cfg,db.list_runs(cfg)[0]['id'])
    assert saved['status']=='failed'
    report=saved['report'];assert report['verdict']=='inconclusive'
    assert len(report['experiments'][0]['partial_tasks'])==1
    output=tmp_path/'incomplete.json';export_reliability(report,output)
    assert output.exists() and not output.with_suffix('.md').exists()
