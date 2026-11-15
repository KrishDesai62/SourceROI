from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from examples.knowledge_change.demo import workspace,external_agent
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze

@pytest.fixture
def setup(tmp_path):
    src=workspace(tmp_path/'src');freeze(src,tmp_path/'frozen')
    before=read_config(tmp_path/'frozen');after=workspace(tmp_path/'candidate',days=14)
    return before,after,a.propose(before,after)

def approved(spec):
    return a.review(spec,reviewer='test policy owner',rationale='Test fixture explicit intent',expected_changes={'returns':'14'},
        protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})

def run(setup,**kw):
    before,after,spec=setup
    return a.execute(before,after,spec,callback=external_agent,**kw)

def test_changed_fact_proposal_never_changes_benchmark(setup):
    before,after,spec=setup
    assert spec['changes'][0]['facts']
    assert all(p['status']=='pending' for p in spec['evaluation_proposals'])
    assert '"expected": "30"' in (Path(after['_root'])/'benchmark.jsonl').read_text()
    assert spec['intent']['status']=='unknown'

def test_approved_change_preserves_unrelated_expectation(setup):
    result=run(setup,approval=approved(setup[2]))
    assert result['verdict']=='ACCEPT'
    assert all(r['candidate_correct'] for r in result['tasks'])
    assert result['execution']['calls']==4
    assert len(a.timeline(setup[1]))==1

def test_unapproved_changed_answer_is_not_auto_ground_truth(setup):
    assert run(setup)['verdict']=='REVIEW' # Unknown business intent is not a confirmed regression

def test_bad_protected_behavior_blocks(setup):
    before,after,spec=setup
    path=Path(after['_root'])/'sources/policy/warranty.json';path.write_text('{"warranty_days": 1}')
    spec=a.propose(before,after)
    result=run((before,after,spec),approval=approved(spec))
    assert result['verdict']=='BLOCK' and 'warranty' in result['blocking_tasks']

def test_review_is_hash_bound_and_tamper_rejected(setup):
    spec=setup[2];approval=approved(spec);approval['expected_changes']['returns']='999'
    with pytest.raises(ValueError,match='bound'):run(setup,approval=approval)
    spec['changes'].clear()
    with pytest.raises(ValueError,match='hash'):run(setup)

def test_stale_sources_rejected(setup):
    (Path(setup[1]['_root'])/'sources/policy/returns.json').write_text('{}')
    with pytest.raises(ValueError,match='Stale'):run(setup)

def test_missing_models_fail_closed(setup,monkeypatch):
    from sourceroi.live.provider import ProviderError
    def unavailable(*args,**kwargs):raise ProviderError('Explicitly unavailable test provider')
    monkeypatch.setattr('sourceroi.live.provider._post',unavailable)
    before,after,spec=setup
    result=a.execute(before,after,spec,approval=approved(spec),max_calls=4)
    assert result['verdict']=='INCONCLUSIVE'

def test_budget_incomplete_and_callback_labels_hidden(setup):
    assert run(setup,max_calls=3)['verdict']=='INCONCLUSIVE'
    def incomplete(cfg,tasks):
        assert all(set(t)=={'id','question'} for t in tasks)
        return {'tasks':[]}
    assert a.execute(*setup[:2],setup[2],callback=incomplete)['verdict']=='INCONCLUSIVE'

def test_no_review_no_changes_requires_review(tmp_path):
    src=workspace(tmp_path/'src');freeze(src,tmp_path/'frozen');before=read_config(tmp_path/'frozen')
    spec=a.propose(before,src)
    assert a.execute(before,src,spec,callback=external_agent)['verdict']=='REVIEW'

def test_replacement_evidence_is_required(setup):
    spec=setup[2];approval=a.review(spec,reviewer='Owner',rationale='Explicit decision',expected_changes={'returns':'14'},protected_tasks=['warranty'])
    assert run(setup,approval=approval)['verdict']=='REVIEW'

def test_unknown_review_task_and_conflicting_decisions(setup):
    with pytest.raises(ValueError):a.review(setup[2],reviewer='Owner',rationale='Decision',protected_tasks=['fake'])
    with pytest.raises(ValueError):a.review(setup[2],reviewer='Owner',rationale='Decision',protected_tasks=['returns'],expected_changes={'returns':'14'})

def test_new_content_impacts_without_history(setup):
    before,after,_=setup
    (Path(after['_root'])/'sources/policy/new.txt').write_text('The returns_days policy question now has a revised rule.')
    spec=a.propose(before,after)
    assert any('topic_overlap' in r['reasons'] for r in spec['impact'])

def test_cli_plan_review_and_api(setup,tmp_path,capsys):
    from sourceroi.live.cli import main
    before,after,spec=setup
    output=tmp_path/'plan.json'
    assert main(['--project',after['_root'],'change-plan','--baseline',before['_root'],'--output',str(output)])==0
    assert json.loads(output.read_text())['id']==spec['id']
    from sourceroi.live.api import create_app
    client=TestClient(create_app(after['_root']))
    response=client.post('/api/v2/knowledge/review',json={'specification':spec,'decisions':{'reviewer':'Owner','rationale':'Explicit protection','protected_tasks':['warranty']}})
    assert response.status_code==200
    assert client.get('/api/v2/knowledge/timeline').status_code==200
    assert client.post('/api/v2/knowledge/release',json={'snapshot_id':'a'*32,'specification':spec}).status_code==400

def test_engine_actual_schema_and_incomplete_responses(setup):
    def engine_schema(cfg,tasks):
        r=external_agent(cfg,tasks)
        for row in r['tasks']:row['actual']=row.pop('answer')
        return r
    assert a.execute(*setup[:2],setup[2],approval=approved(setup[2]),callback=engine_schema)['verdict']=='ACCEPT'
    def truncated(cfg,tasks):
        r=external_agent(cfg,tasks);r['tasks'][0]['response_complete']=False;return r
    assert a.execute(*setup[:2],setup[2],approval=approved(setup[2]),callback=truncated)['verdict']=='INCONCLUSIVE'

def test_snapshot_benchmark_tampering_rejected(setup):
    before,after,spec=setup
    path=Path(before['_root'])/'benchmark.jsonl';path.write_text(path.read_text().replace('365','366'))
    with pytest.raises(ValueError,match='snapshot'):a.propose(before,after)

def test_proposal_correction_is_explicit_not_silent(setup):
    p=setup[2]['evaluation_proposals'][0]
    assert p['suggested_expected'] is None and p['classification']=='AMBIGUOUS_REVIEW'
    approval=approved(setup[2]);r=run(setup,approval=approval)
    assert r['evaluation_maintenance'][0]['decision']=='approved'
    assert p['status']=='pending' # immutable proposal retained

def test_repair_intervention_does_not_mutate_candidate(setup,tmp_path):
    before,after,_=setup
    path=Path(after['_root'])/'sources/policy/returns.json';path.unlink()
    spec=a.propose(before,after)
    approval=a.review(spec,reviewer='Owner',rationale='Returns must remain correct',protected_tasks=['returns','warranty'])
    repaired=workspace(tmp_path/'repair');rspec=a.propose(before,repaired)
    decision=a.review(rspec,reviewer='Owner',rationale='Restore original knowledge',protected_tasks=['returns','warranty'])
    r=a.verify_repair(before,after,spec,repaired,rspec,approval=approval,repair_approval=decision,callback=external_agent,max_calls=8)
    assert r['restored_registered_suite'] and not path.exists()
    assert r['calls']==8

def test_empty_reviews_and_duplicates_cannot_accept(setup):
    def duplicates(cfg,tasks):
        r=external_agent(cfg,tasks);r['tasks'].append(r['tasks'][0]);return r
    assert a.execute(*setup[:2],setup[2],callback=duplicates)['verdict']=='INCONCLUSIVE'
    with pytest.raises(ValueError):a.review(setup[2],reviewer=' ',rationale='Missing owner')

def test_inputs_changed_during_evaluation_fail_closed(setup):
    def mutate(cfg,tasks):
        r=external_agent(cfg,tasks)
        if cfg['_root']==setup[1]['_root']:
            (Path(cfg['_root'])/'sources/policy/warranty.json').write_text('{"warranty_days": 1}')
        return r
    r=a.execute(*setup[:2],setup[2],approval=approved(setup[2]),callback=mutate)
    assert r['verdict']=='INCONCLUSIVE'

def test_targeted_negative_controls_do_not_claim_full_safety(tmp_path):
    source=workspace(tmp_path/'source')
    p=Path(source['_root'])/'benchmark.jsonl'
    tasks=[json.loads(x) for x in p.read_text().splitlines()]
    for i in range(5):tasks.append({'id':f'control{i}','question':'What is warranty_days?','expected':'365','evidence':[{'document_id':'policy::warranty.json','quote':'365'}]})
    p.write_text('\n'.join(json.dumps(t) for t in tasks))
    freeze(source,tmp_path/'baseline');before=read_config(tmp_path/'baseline')
    import shutil
    shutil.copytree(tmp_path/'source',tmp_path/'candidate');after=read_config(tmp_path/'candidate')
    (tmp_path/'candidate/sources/policy/returns.json').write_text('{"returns_days":14}')
    spec=a.propose(before,after);decision=approved(spec)
    r=a.execute(before,after,spec,approval=decision,callback=external_agent,targeted=True)
    assert r['verdict']=='INCONCLUSIVE'
    assert len(r['execution']['negative_controls'])==2 and r['execution']['calls_avoided']>0

def test_unknown_or_absent_evidence_never_accepts(tmp_path):
    source=workspace(tmp_path/'src');p=Path(source['_root'])/'benchmark.jsonl'
    tasks=[json.loads(x) for x in p.read_text().splitlines()]
    for task in tasks:task['evidence']=[]
    p.write_text('\n'.join(json.dumps(t) for t in tasks));freeze(source,tmp_path/'frozen')
    before=read_config(tmp_path/'frozen');spec=a.propose(before,source)
    approval=a.review(spec,reviewer='Owner',rationale='Protect existing answers',protected_tasks=['returns','warranty'])
    assert a.execute(before,source,spec,approval=approval,callback=external_agent)['verdict']=='REVIEW'

def test_deadline_and_secret_exception_are_fail_closed(setup):
    import time
    def slow(cfg,tasks):
        time.sleep(.01);return external_agent(cfg,tasks)
    assert a.execute(*setup[:2],setup[2],callback=slow,max_seconds=.001)['verdict']=='INCONCLUSIVE'
    def secret(cfg,tasks):raise RuntimeError('secret-test-password')
    r=a.execute(*setup[:2],setup[2],callback=secret)
    assert 'secret-test-password' not in json.dumps(r)

def test_review_history_and_release_exports(setup):
    before,after,spec=setup;approval=approved(spec)
    a.save_proposal(after,spec);a.save_review(after,spec,approval)
    result=run(setup,approval=approval)
    events=a.timeline(after)
    assert {r['kind'] for r in events}=={'knowledge_change','knowledge_review','knowledge_release'}
    from sourceroi.live.api import create_app
    client=TestClient(create_app(after['_root']))
    assert client.get('/api/v2/knowledge/releases/'+result['run_id']+'/export?format=markdown').status_code==200
    assert client.get('/api/v2/knowledge/releases/'+result['run_id']+'/export?format=unsafe').status_code==400

def test_numeric_conflict_requires_review(setup):
    before,after,_=setup
    (Path(after['_root'])/'sources/policy/z_conflict.json').write_text('{\n  "returns_days": 99\n}')
    # Normal workspace JSON formatting must match the same fact shape.
    (Path(after['_root'])/'sources/policy/returns.json').write_text('{\n  "returns_days": 14\n}')
    spec=a.propose(before,after)
    assert spec['potential_conflicts']
    assert run((before,after,spec),approval=approved(spec))['verdict']=='REVIEW'

def test_forged_impact_and_diff_cannot_bypass_review(setup):
    before,after,spec=setup
    forged=deepcopy(spec)
    for row in forged['impact']:row['potentially_affected']=False
    forged['id']=a.digest({k:v for k,v in forged.items() if k!='id'})
    with pytest.raises(ValueError,match='dependencies'):a.execute(before,after,forged,callback=external_agent)
    forged=deepcopy(spec);forged['changes']=[];forged['id']=a.digest({k:v for k,v in forged.items() if k!='id'})
    with pytest.raises(ValueError,match='canonical'):a.execute(before,after,forged,callback=external_agent)

def test_malformed_review_fields_rejected(setup):
    for decisions in ({'expected_changes':['returns']},{'protected_tasks':'returns'},{'rationale':123},{'expected_evidence':[]}):
        with pytest.raises(ValueError):a.review(setup[2],**{'reviewer':'Owner','rationale':'Decision',**decisions})
