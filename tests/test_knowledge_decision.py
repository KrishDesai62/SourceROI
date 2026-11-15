"""Evidence-only decisions; authored fixtures are not empirical model validation."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tools.benchmark_knowledge_decision import workspace
from sourceroi.live.knowledge_decision import run,DecisionRequest,binary_metrics
from sourceroi.live import db
from sourceroi.live.api import create_app
from sourceroi.live.security import SecurityStore


@pytest.fixture
def project(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Knowledge decision must never generate')
    monkeypatch.setattr('sourceroi.live.provider._post',forbidden)
    return workspace(tmp_path/'project')


def test_redundant_protected_and_combined_interventions(project):
    old,new,request=project;report=run(old,new,request)
    by={r['id']:r for r in report['recommendations']};experiments={e['name']:e for e in report['experiments']}
    assert by['duplicate']['recommendation']=='REMOVE' and by['policy']['recommendation']=='KEEP'
    assert by['warranty']['recommendation']=='KEEP'
    assert experiments['without_duplicate']['verdict']=='REVIEW'
    assert experiments['without_policy']['verdict']=='BLOCK'
    assert experiments['without_both']['conventional']['reference_regressions']==['combined','returns','warranty']
    assert sum(len(experiments[n]['conventional']['reference_regressions']) for n in ('without_policy','without_warranty'))==4
    assert len(experiments['without_both']['conventional']['reference_regressions'])==3
    assert all(e['verdict']==e['conventional']['verdict'] for e in report['experiments'])
    assert report['conventional_comparison']['additional_verified_detection']==0
    assert report['conventional_comparison']['conventional_selected_experiment']==report['recommended_experiment']
    assert report['overhead']['generation_attempts']==0 and not report['release_authorized']
    assert all(e['prompt_tokens'] is None and e['model_cost_usd'] is None and e['answer_accuracy'] is None for e in report['experiments'])
    assert report['validation']['semantic_review']=='PENDING'
    again=run(old,new,request);assert again==report
    assert len([r for r in db.list_runs(new) if r['mode']=='knowledge_decision'])==1
    from sourceroi.live.assurance import timeline
    assert timeline(new)[0]['kind']=='knowledge_decision' and timeline(new)[0]['verdict']=='REVIEW'


def test_update_and_conflict_do_not_grant_approval(tmp_path):
    old,new,request=workspace(tmp_path/'changed',changed=True)
    request['alternatives']=[{'name':'updated','corpus':'candidate'}]
    report=run(old,new,request)
    assert next(r for r in report['recommendations'] if r['id']=='policy')['recommendation']=='UPDATE'
    updated=report['experiments'][1];assert updated['verdict']=='BLOCK'
    assert updated['conventional']['protected_reference_regressions']==['returns']
    assert not report['release_authorized']
    old,new,request=workspace(tmp_path/'conflict',conflict=True)
    report=run(old,new,request)
    assert report['specification']['potential_conflicts']
    assert next(e for e in report['experiments'] if e['name']=='updated')['conventional']['uncertain_tasks']


def test_missing_evidence_is_not_a_quality_pass(tmp_path):
    old,new,request=workspace(tmp_path/'unknown',unsupported=True)
    report=run(old,new,request)
    assert report['recommended_experiment'] is None and report['verdict']=='INCONCLUSIVE'
    assert next(r for r in report['recommendations'] if r['id']=='duplicate')['recommendation']=='REVIEW'


def test_document_passage_alternative_provenance(project):
    from sourceroi.live.ingest import scan_sources
    old,new,request=project;_,chunks=scan_sources(old)
    passage=next(c['id'] for c in chunks if c['source_id']=='duplicate')
    request['alternatives']=[{'name':'doc','corpus':'baseline','exclude_documents':['duplicate::returns-copy.txt']},
        {'name':'passage','corpus':'baseline','exclude_passages':[passage]}]
    report=run(old,new,request)
    assert {r['level'] for r in report['recommendations']}=={'source','document','passage'}
    assert next(r for r in report['recommendations'] if r['level']=='passage')['recommendation']=='REMOVE'
    for exp in report['experiments']:
        for row in exp['tasks']:
            for evidence in row['retrieved_evidence']:
                assert evidence['document_version']==report['identity']['baseline_manifest'][evidence['document_id']]


@pytest.mark.parametrize('edit',[{'alternatives':[{'name':'original'}]},{'requirements':{'min_reference_coverage':float('nan')}},{'alternatives':[{'name':'x','operation':'generate'}]},{'approve':True}])
def test_invalid_contracts_fail_closed(project,edit):
    request=deepcopy(project[2]);request.update(edit)
    with pytest.raises(ValueError):DecisionRequest.model_validate(request)


def test_unknown_ids_and_changed_labels_rejected(project):
    old,new,request=project;request['alternatives'][0]['exclude_sources']=['unknown']
    with pytest.raises(ValueError,match='Unknown'):run(old,new,request)
    request=deepcopy(project[2]);request['alternatives'][0]['exclude_sources']=[]
    p=Path(new['_root'])/'benchmark.jsonl';p.write_text(p.read_text().replace('"expected": "30"','"expected": "14"'))
    with pytest.raises(ValueError,match='identical'):run(old,new,request)


def test_authenticated_operator_only_and_no_generation(project):
    old,new,request=project;store=SecurityStore(new['_root'],initialize=True)
    for role in ('operator','viewer','reviewer'):store.add_user(role,'Development fixture password only',role)
    with TestClient(create_app(new['_root']),base_url='http://localhost') as client:
        assert client.post('/api/v2/knowledge/decisions',json=request).status_code==401
        for role,expected in [('viewer',403),('reviewer',403),('operator',200)]:
            token=store.login(role,'Development fixture password only')['token'];headers={'Authorization':'Bearer '+token}
            response=client.post('/api/v2/knowledge/decisions',json=request,headers=headers)
            assert response.status_code==expected,response.text
        report=response.json();assert report['verdict']=='REVIEW'
        assert client.get('/api/v2/runs/'+report['id'],headers=headers).json()['report']['id']==report['id']
        assert client.post('/api/v2/runs',json={'acknowledge_model_calls':True},headers=headers).status_code==403


def test_development_impact_metrics_and_undefined_cases():
    assert binary_metrics(['a','b'],['b','c'],['a','b','c'])=={'precision':.5,'recall':.5,'false_alarms':['a'],'missed':['c'],'label_status':'supplied_development_labels_not_independent'}
    assert binary_metrics([],None,[])['precision'] is None
    with pytest.raises(ValueError):binary_metrics([],['forged'],[])


def test_worker_cannot_reinsert_excluded_evidence(project,monkeypatch):
    import sourceroi.live.analysis_boundary as boundary
    original=boundary.call
    def forged(operation,**payload):
        result=original(operation,**payload)
        if operation=='knowledge_measure':
            result[1]['tasks'][0]=deepcopy(result[0]['tasks'][0])
        return result
    monkeypatch.setattr(boundary,'call',forged)
    with pytest.raises(ValueError,match='exclusions'):run(*project)


def test_context_estimates_do_not_become_actual_usage(project):
    old,new,request=project
    old['model']['input_price_per_million_usd']=2.0
    # The frozen model configuration is part of its identity: changing it must
    # fail rather than manufacturing a priced comparison against another model.
    with pytest.raises(ValueError,match='snapshot'):run(old,new,request)
    from sourceroi.live.config import read_config
    from sourceroi.live.data_ci import freeze
    root=Path(new['_root']);config=json.loads((root/'project.json').read_text());config['model']['input_price_per_million_usd']=2.0
    (root/'project.json').write_text(json.dumps(config));new=read_config(root)
    snapshot='b'*32;path=root/'.sourceroi/snapshots'/snapshot;freeze(new,path);request['snapshot_id']=snapshot
    report=run(read_config(path),new,request)
    for experiment in report['experiments']:
        assert experiment['estimated_context_input_cost_usd']==experiment['estimated_context_tokens']*2.0/1e6
        assert experiment['model_cost_usd'] is None and experiment['total_tokens'] is None


def test_pinned_version_and_scope_mismatch_are_not_supported(tmp_path):
    from sourceroi.live.knowledge_decision import measure_worker,conventional,Requirements
    from sourceroi.live import ingest
    # Call the same fixed worker entry under the worker-active flag; integration
    # tests above exercise the actual subprocess. This case isolates contracts.
    cfg={'sources':[{'id':'s','jurisdiction':'UK','effective_from':'2020-01-01'}],'settings':{'max_chunks':5}}
    chunks=[{'id':'s::x#chunk0','document_id':'s::x','source_id':'s','title':'x','text':'Rate is 12.'}]
    tasks=[{'id':'a','question':'What rate?','evidence':[{'document_id':'s::x','quote':'Rate is 12.','document_version':'older'}]},
        {'id':'b','question':'What rate?','scope':{'jurisdiction':'US'},'evidence':[{'document_id':'s::x','quote':'Rate is 12.'}]}]
    from unittest.mock import patch
    alt={'name':'original','corpus':'baseline','exclude_sources':[],'exclude_documents':[],'exclude_passages':[],'policy':None}
    with patch.object(ingest,'_WORKER_ACTIVE',True):
        rows=measure_worker({'tasks':tasks,'alternatives':[alt],'baseline':{'cfg':cfg,'chunks':chunks,'manifest':{'s::x':'current'}}})[0]['tasks']
    assert rows[0]['reference_version_mismatches']==['s::x'] and rows[0]['reference_coverage']==0
    assert not rows[1]['retrieved_chunk_ids'] and rows[1]['reference_coverage']==0
    assert conventional(rows,rows,Requirements(),set())['verdict']=='BLOCK'


def test_stale_source_during_measurement_never_persists(project,monkeypatch):
    import sourceroi.live.analysis_boundary as boundary
    original=boundary.call
    def raced(operation,**payload):
        result=original(operation,**payload)
        if operation=='knowledge_measure':(Path(project[1]['_root'])/'sources/policy/returns.txt').write_text('Returns period is 999 days.')
        return result
    monkeypatch.setattr(boundary,'call',raced)
    with pytest.raises(ValueError,match='changed during'):run(*project)
    assert not [r for r in db.list_runs(project[1]) if r['mode']=='knowledge_decision']


def test_existing_ablation_identity_and_provenance_are_retained(project):
    from sourceroi.live.ingest import scan_sources,load_benchmark
    from sourceroi.live.data_ci import digest
    old,new,request=project;tasks=load_benchmark(old);docs,_=scan_sources(old)
    base={'excluded_sources':[],'excluded_documents':[],'tasks':[{'id':t['id'],'correct':True} for t in tasks],
        'metrics':{'accuracy':1.0,'mean_latency_ms':0.0,'total_cost_usd':None}}
    removed={**deepcopy(base),'excluded_sources':['duplicate']}
    history={'mode':'ablation','manifest':{d['id']:d['fingerprint'] for d in docs},'benchmark_sha256':digest(tasks),
        'config_hash':old['_config_hash'],'measurement_kind':'synthetic_fixture','variants':[base,removed]}
    rid=db.begin(new,'ablation',[]);db.finish(new,rid,history);request['ablation_run_ids']=[rid]
    report=run(old,new,request)
    assert report['historical_ablations'][0]['measurement_kind']=='synthetic_fixture'
    assert next(r for r in report['recommendations'] if r['id']=='duplicate')['historical_ablation_observations'][0]['comparison']['delta_cost_usd'] is None
    assert report['overhead']['generation_attempts']==0 and not report['release_authorized']
    history['config_hash']='forged';other=db.begin(new,'ablation',[]);db.finish(new,other,history)
    request['ablation_run_ids']=[other]
    with pytest.raises(ValueError,match='mismatch'):run(old,new,request)
    history['config_hash']=old['_config_hash'];history['variants'][0]['metrics']['accuracy']=None
    missing=db.begin(new,'ablation',[]);db.finish(new,missing,history);request['ablation_run_ids']=[missing]
    with pytest.raises(ValueError,match='metrics'):run(old,new,request)


def test_actual_cli_dispatch_persists_offline_decision(project,tmp_path,capsys):
    from sourceroi.cli import main
    path=tmp_path/'request.json';path.write_text(json.dumps(project[2]))
    assert main(['--project',project[1]['_root'],'knowledge-decide','--request',str(path)])==0
    report=json.loads(capsys.readouterr().out)
    assert report['kind']=='knowledge_decision' and report['overhead']['generation_attempts']==0
    assert db.get(project[1],report['id'])['report']==report
