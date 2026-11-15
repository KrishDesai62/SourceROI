from copy import deepcopy
import json
from pathlib import Path
import pytest
from examples.knowledge_change.demo import workspace,external_agent
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.ingest import scan_sources
from sourceroi.live.release_policy import inspect

@pytest.fixture
def setup(tmp_path):
    original=workspace(tmp_path/'source');freeze(original,tmp_path/'accepted');before=read_config(tmp_path/'accepted')
    after=workspace(tmp_path/'candidate',days=14)
    intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'authored fixture owner','rationale':'Returns changes; warranty must stay correct'}
    spec=a.propose(before,after,intent=intent)
    approval=a.review(spec,reviewer='test owner',rationale='Known fixture change',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    return before,after,spec,approval


def callback(cfg,tasks):
    result=external_agent(cfg,tasks);manifest={d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}
    for r in result['tasks']:r.update(citations=r['retrieved_chunk_ids'],knowledge_manifest=manifest,knowledge_version=digest(manifest),json_format_valid=True)
    return result


def run(setup,**kwargs):
    before,after,spec,approval=setup
    return a.execute(before,after,spec,approval=approval,callback=kwargs.pop('callback',callback),policy='strict_grounded',**kwargs)


def reviews_for(report):
    from sourceroi.live.reliability_review import packet
    reviews={}
    for row in report['tasks']:
        sample=row['grounding_checks']['sample'];review=packet(sample)
        review.update(status='complete',reviewer='unit-test-expert',independent_of_generator=True,
            semantic_correctness=True,citation_correctness=True,scope_appropriate=True,uses_outdated_fact=False,
            claims=[{'start':0,'end':len(sample['answer']),'verdict':'supported','evidence':[{'id':sample['citations'][0],'quote':sample['context'][0]['text']}]}])
        reviews[review['sample_key']]=review
    return reviews


def test_exact_pass_does_not_imply_grounding_accept(setup):
    report=run(setup)
    assert report['verdict']=='REVIEW' and report['check_statuses']['exact_answer']=='PASS'
    assert report['check_statuses']['citation_integrity']=='PASS'
    assert 'semantic_review' in report['missing_checks']
    assert all(row['grounding_checks']['review']['semantic_correctness'] is None for row in report['tasks'])


def test_strict_accept_requires_bound_explicit_review(setup):
    pending=run(setup);reviewed=run(setup,semantic_reviews=reviews_for(pending),reviewers=['unit-test-expert'])
    assert reviewed['verdict']=='ACCEPT'
    assert not reviewed['missing_checks']


def test_missing_citations_and_fabricated_ids_block(setup):
    def missing(cfg,tasks):
        result=callback(cfg,tasks)
        for r in result['tasks']:r['citations']=[]
        return result
    report=run(setup,callback=missing)
    assert report['verdict']=='BLOCK' and 'citation_integrity' in report['blocking_reasons']
    def fabricated(cfg,tasks):
        result=callback(cfg,tasks);result['tasks'][0]['citations']=['not-in-retrieval#0'];return result
    assert run(setup,callback=fabricated)['verdict']=='BLOCK'


def test_legacy_policy_remains_explicitly_scoped(setup):
    before,after,spec,approval=setup
    report=a.execute(before,after,spec,approval=approval,callback=external_agent)
    assert report['verdict']=='ACCEPT' and report['release_policy']['name']=='legacy_exact'
    assert report['check_statuses']['semantic_review']=='REVIEW'
    assert 'not independent grounding proof' in report['approval_scope']


def test_missing_version_proof_is_inconclusive(setup):
    def unknown(cfg,tasks):
        result=callback(cfg,tasks)
        for r in result['tasks']:r.pop('knowledge_manifest')
        return result
    assert run(setup,callback=unknown)['verdict']=='INCONCLUSIVE'


def test_matching_number_wrong_evidence_is_deterministic_failure(setup):
    _,cfg,_,_=setup
    (Path(cfg['_root'])/'sources/policy/warranty.json').write_text('{"warranty_days":14}')
    chunks=scan_sources(cfg)[1]
    task={'id':'returns','question':'Return period?','expected':'14','evidence':[{'document_id':'policy::returns.json','quote':'14'}]}
    cid=next(c['id'] for c in chunks if c['document_id']=='policy::warranty.json')
    row={'answer':'14','citations':[cid],'retrieved_chunk_ids':[cid]}
    result=inspect(task,row,chunks,cfg,'test',builtin=True)
    assert result['citation_status']=='BLOCK' and result['cited_reference_coverage']==0
    assert result['semantic_status']=='REVIEW'


@pytest.mark.parametrize('metadata',[{'jurisdiction':'EU','effective_from':'2020-01-01'},{'jurisdiction':'US','effective_to':'2020-01-01'},{'jurisdiction':'US','effective_from':'2030-01-01'}])
def test_scope_date_mismatch_blocks_with_correct_answer(setup,metadata):
    _,cfg,_,_=setup;cfg=deepcopy(cfg);cfg['sources'][0].update(metadata)
    chunks=scan_sources(cfg)[1];cid=next(c['id'] for c in chunks if c['document_id']=='policy::returns.json')
    task={'id':'returns','question':'Returns?','expected':'14','scope':{'jurisdiction':'US','as_of':'2026-11-13'},'evidence':[{'document_id':'policy::returns.json','quote':'14'}]}
    result=inspect(task,{'answer':'14','citations':[cid],'retrieved_chunk_ids':[cid]},chunks,cfg,'test',builtin=True)
    assert result['scope_status']=='BLOCK'


def test_protected_warranty_is_not_proposed_as_truth(setup):
    before,after,_,_=setup
    (Path(after['_root'])/'sources/policy/warranty.json').write_text('{"warranty_days":1}')
    intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'fixture owner','rationale':'Returns only'}
    spec=a.propose(before,after,intent=intent)
    row=next(p for p in spec['evaluation_proposals'] if p['task_id']=='warranty')
    assert row['classification']=='PROTECTED_UNCHANGED' and row['suggested_expected'] is None
    with pytest.raises(ValueError,match='protected'):a.review(spec,reviewer='Owner',rationale='Invalid attempt',expected_changes={'warranty':'1'})


def test_unknown_intent_remains_ambiguous(setup):
    before,after,_,_=setup;spec=a.propose(before,after)
    assert spec['evaluation_proposals'][0]['classification']=='AMBIGUOUS_REVIEW'
    assert spec['evaluation_proposals'][0]['suggested_expected'] is None


def test_numeric_partial_digits_do_not_break_legitimate_proposals(tmp_path):
    src=workspace(tmp_path/'src',days=21)
    p=Path(src['_root'])/'benchmark.jsonl';p.write_text(p.read_text().replace('"expected": "30"','"expected": "21"').replace('"quote": "30"','"quote": "21"'))
    freeze(src,tmp_path/'accepted');before=read_config(tmp_path/'accepted');after=workspace(tmp_path/'after',days=25)
    (Path(after['_root'])/'benchmark.jsonl').write_text(p.read_text())
    spec=a.propose(before,after,intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'Owner','rationale':'21 becomes 25'})
    proposal=next(p for p in spec['evaluation_proposals'] if p['task_id']=='returns')
    assert proposal['classification']=='PROPOSED_CHANGE' and proposal['suggested_expected']=='25'


def test_automated_events_never_count_as_human_effort(tmp_path):
    from sourceroi.live.maintenance import record,summarize,events
    path=tmp_path/'events.jsonl';common=dict(protocol_id='test',session_id='test',participant_id='automation',origin='automation',workflow='sourceroi',change_id='test')
    record(path,**common,event='start');record(path,**common,event='edit',edit_count=3);record(path,**common,event='complete')
    result=summarize(path);assert result['completed_declared_human_sessions']==[] and result['time_savings'] is None
    rows=events(path);rows[0]['edit_count']=99;path.write_text('\n'.join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError,match='integrity'):events(path)


def test_schema_constraint_uses_only_retrieved_ids(setup,monkeypatch):
    from sourceroi.live.provider import run_chat
    cfg=deepcopy(setup[1]);cfg['model'].update(runtime='llama_cpp',compact_source_ids=True)
    def post(url,body,*args):
        schema=body['response_format']['json_schema']['schema']['oneOf'][0]
        assert body['response_format']['json_schema']['schema']['oneOf'][1]['properties']['citations']['maxItems']==0
        assert schema['properties']['citations']['items']['enum']==['1']
        assert schema['properties']['citations']['minItems']==1
        return {'choices':[{'message':{'content':'{"answer":14,"citations":["1"]}'},'finish_reason':'stop'}]}
    monkeypatch.setattr('sourceroi.live.provider._post',post)
    context=scan_sources(cfg)[1][:1]
    result=run_chat('Returns?',context,{**cfg,'_require_citations':True})
    assert result['citations']==[context[0]['id']]
    assert len(result['prompt_sha256'])==64 and len(result['response_schema_sha256'])==64

def test_model_identity_mismatch_rejected_by_adapter(setup,monkeypatch):
    from sourceroi.live.provider import run_external,ProviderError
    cfg=deepcopy(setup[1]);cfg['agent']={'url':'http://127.0.0.1:1/evaluate','api_key_env':'','protocol_version':2,'capabilities':[],
        'execution_identity':{'model':'m','prompt':'p','retrieval':'r'}}
    def post(url,payload,*args):
        return {'answer':'14','filter_applied':True,'request_id':payload['request_id'],'execution_identity':{'model':'wrong','prompt':'p','retrieval':'r'},
            'enforced_restrictions':{k:payload[k] for k in ('allowed_source_ids','excluded_source_ids','excluded_document_ids')},'retrieval_controls_applied':{}}
    monkeypatch.setattr('sourceroi.live.provider._post',post)
    with pytest.raises(ProviderError,match='identity changed'):run_external('q',['policy'],[],[],cfg,'t')


def test_document_application_retrieves_historical_vs_current(tmp_path):
    from tools.validate_document_rag import make
    from examples.document_rag.server import evaluate,identity,load,digest
    from sourceroi.live.adapter import attach_contract
    root=tmp_path/'app';make(root,14);_,manifest=load(root)
    def payload(ranking):
        return attach_contract({'task_id':'t','question':'What is the return period?','allowed_source_ids':['current','archive','regional','warranty'],
            'excluded_source_ids':[],'excluded_document_ids':[],'request_filter_ack':True},
            {'protocol_version':2,'capabilities':[],'knowledge_manifest':manifest,'execution_identity':identity(ranking)},{})
    assert evaluate(payload('prefer_current'),[root],'prefer_current')['answer']=='14'
    assert evaluate(payload('prefer_archive'),[root],'prefer_archive')['answer']=='30'
    with pytest.raises(ValueError,match='Identity'):evaluate(payload('prefer_current'),[root],'prefer_archive')


def test_proposal_development_controls_are_separate_and_explicitly_authored(tmp_path,capsys):
    from tools.validate_proposals_v2 import main
    result=main(tmp_path/'proposal.json')
    assert result['summary']['development_cases']==8
    assert result['summary']['development_class_matches']==8
    assert result['summary']['development_revision_matches']==8
    assert result['summary']['protected_incorrectly_proposed']==0
    assert result['independent_labels'] is False


def test_cli_and_api_strict_policy_selection(setup,tmp_path,capsys):
    from sourceroi.live.api import create_app
    from fastapi.testclient import TestClient
    from sourceroi.live.cli import main
    before,after,spec,_=setup
    client=TestClient(create_app(after['_root']))
    response=client.post('/api/v2/knowledge/release',json={'snapshot_id':'a'*32,'specification':spec,'policy':'strict_grounded'})
    assert response.status_code==400 # Calls must still be explicitly acknowledged.
    intent=tmp_path/'intent.json';intent.write_text(json.dumps({'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'Owner','rationale':'Return change'}))
    out=tmp_path/'spec.json'
    assert main(['--project',after['_root'],'change-plan','--baseline',before['_root'],'--output',str(out),'--intent',str(intent)])==0
    assert json.loads(out.read_text())['evaluation_proposals'][0]['classification']=='PROPOSED_CHANGE'

def test_negative_semantic_review_blocks_without_rewriting_exact_label(setup):
    first=run(setup);reviews=reviews_for(first)
    next(iter(reviews.values()))['semantic_correctness']=False
    report=run(setup,semantic_reviews=reviews,reviewers=['unit-test-expert'])
    assert report['check_statuses']['exact_answer']=='PASS'
    assert report['verdict']=='BLOCK' and 'semantic_review' in report['blocking_reasons']
    assert setup[3]['expected_changes']=={'returns':'14'}


def test_passing_strict_subset_cannot_certify_remaining_tasks(tmp_path):
    original=workspace(tmp_path/'source');p=Path(original['_root'])/'benchmark.jsonl'
    tasks=[json.loads(line) for line in p.read_text().splitlines()]
    for i in range(5):tasks.append({'id':'control'+str(i),'question':'What is warranty_days?','expected':'365','evidence':[{'document_id':'policy::warranty.json','quote':'365'}]})
    p.write_text('\n'.join(json.dumps(t) for t in tasks));freeze(original,tmp_path/'accepted')
    import shutil
    shutil.copytree(tmp_path/'source',tmp_path/'candidate');before=read_config(tmp_path/'accepted');after=read_config(tmp_path/'candidate')
    (Path(after['_root'])/'sources/policy/returns.json').write_text('{"returns_days":14}')
    spec=a.propose(before,after,intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'test','rationale':'Returns only'})
    approval=a.review(spec,reviewer='test',rationale='Explicit test intent',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    setup=(before,after,spec,approval);pending=run(setup,targeted=True)
    result=run(setup,targeted=True,semantic_reviews=reviews_for(pending),reviewers=['unit-test-expert'])
    assert result['verdict']=='INCONCLUSIVE' and result['check_statuses']['execution']=='INCONCLUSIVE'
    assert result['execution']['tasks_not_executed']>0

def test_benchmark_protection_cannot_be_overridden_by_new_intent(tmp_path):
    src=workspace(tmp_path/'src');p=Path(src['_root'])/'benchmark.jsonl'
    tasks=[json.loads(line) for line in p.read_text().splitlines()];tasks[1]['behavior_constraint']='protected'
    p.write_text('\n'.join(json.dumps(t) for t in tasks));freeze(src,tmp_path/'accepted')
    import shutil
    shutil.copytree(tmp_path/'src',tmp_path/'candidate');before=read_config(tmp_path/'accepted');after=read_config(tmp_path/'candidate')
    (Path(after['_root'])/'sources/policy/warranty.json').write_text('{"warranty_days":1}')
    spec=a.propose(before,after)
    assert 'warranty' in spec['intent']['protected_tasks']
    with pytest.raises(ValueError,match='protected'):a.review(spec,reviewer='Owner',rationale='Must not override existing protection',expected_changes={'warranty':'1'})
    with pytest.raises(ValueError,match='Conflicting'):a.propose(before,after,intent={'expected_tasks':['warranty'],'declared_by':'Owner','rationale':'Cannot silently alter benchmark protection'})
