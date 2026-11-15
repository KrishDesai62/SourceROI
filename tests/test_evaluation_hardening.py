"""Authored offline regression cases, not new real-model validation."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live import assurance as a
from sourceroi.live.evaluation_inputs import maintained_tasks,packet,assert_parity

ROUTE={'version':1,'rules':[{'contains':'CURRENT','source_ids':['current']}]}


def workspace(root,text,*,tasks=None,extras=None,settings=None):
    root.mkdir(parents=True);(root/'docs').mkdir();(root/'docs/policy.txt').write_text(text)
    tasks=tasks or [{'id':'warranty','question':'What is the warranty duration?','expected':'21','scoring':'numeric',
        'evidence':[{'document_id':'current::policy.txt','quote':'Warranty is 21 days.'}],
        'requires_grounding':True,'evidence_contract':{'version':1,'subject_aliases':[['warranty']]}}]
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
    sources=[{'id':'current','path':'docs','authority':'Authored development fixture','jurisdiction':'US','effective_from':'2025-01-01','effective_to':'2026-01-01'}]
    for sid,value in (extras or {}).items():
        (root/sid).mkdir();(root/sid/'extra.txt').write_text(value)
        sources.append({'id':sid,'path':sid,'authority':'Other authored source','jurisdiction':'US','effective_from':'2024-01-01','effective_to':'2025-01-01'})
    config={'id':'fixture','sources':sources,'model':{'name':'not-called','base_url':'http://127.0.0.1:1/v1','local_only':True},
        'settings':{'chunk_strategy':'sentences','chunk_chars':1100,'overlap_chars':100,'release_policy':'strict_grounded',**(settings or {})}}
    (root/'project.json').write_text(json.dumps(config));return read_config(root)


def pair(tmp_path,new='Warranty coverage lasts 21 days.'):
    old=workspace(tmp_path/'source','Warranty is 21 days.');freeze(old,tmp_path/'accepted')
    before=read_config(tmp_path/'accepted');after=workspace(tmp_path/'candidate',new)
    intent={'expected_tasks':[],'protected_tasks':['warranty'],'declared_by':'Authored fixture','rationale':'Preserve warranty answer; wording requires review'}
    return before,after,a.propose(before,after,intent=intent)


def test_protected_evidence_update_keeps_answer_and_requires_explicit_review(tmp_path):
    before,after,spec=pair(tmp_path)
    assert spec['evidence_proposals']
    proposal=spec['evidence_proposals'][0]
    assert proposal['semantic_equivalence']=='UNKNOWN' and proposal['frozen_expected']=='21'
    with pytest.raises(ValueError,match='explicit equivalence'):
        a.review(spec,reviewer='Fixture operator',rationale='Not independent',evidence_updates={'warranty':{'proposal_id':proposal['id'],'semantic_equivalence':None,'rationale':'Unknown'}})
    review=a.review(spec,reviewer='Fixture operator',rationale='Authored technical test, not independent human',protected_tasks=['warranty'],
        evidence_updates={'warranty':{'proposal_id':proposal['id'],'semantic_equivalence':True,'rationale':'Explicit fixture equivalence assertion only'}})
    task=maintained_tasks(load_benchmark(before),spec,review)[0]
    assert task['expected']=='21' and task['evidence'][0]['quote']=='Warranty coverage lasts 21 days.'
    assert load_benchmark(after)[0]['evidence'][0]['quote']=='Warranty is 21 days.'
    def callback(cfg,tasks):
        docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
        return {'tasks':[{'id':'warranty','answer':'21','citations':[chunks[0]['id']],'retrieved_chunk_ids':[chunks[0]['id']],
            'knowledge_manifest':manifest,'knowledge_version':digest(manifest),'response_complete':True}], 'metrics':{}}
    result=a.execute(before,after,spec,approval=review,callback=callback,max_calls=2,persist=False)
    assert result['verdict']=='REVIEW' and result['check_statuses']['semantic_review']=='REVIEW'
    assert result['check_statuses']['citation_integrity']=='PASS' and result['tasks'][0]['candidate_correct']


@pytest.mark.parametrize('new',['Warranty is 25 days.','Shipping takes 21 days.'])
def test_changed_value_or_unrelated_evidence_cannot_be_evidence_only(tmp_path,new):
    _,_,spec=pair(tmp_path,new)
    assert not spec['evidence_proposals']
    with pytest.raises(ValueError):a.review(spec,reviewer='Fixture',rationale='Invalid',evidence_updates={'warranty':{'proposal_id':'forged','semantic_equivalence':True,'rationale':'Invalid'}})


def test_qualifier_changes_cannot_be_approved_as_evidence_only(tmp_path):
    _,_,spec=pair(tmp_path,'Warranty is 21 days only if membership is active.')
    if spec['evidence_proposals']:
        p=spec['evidence_proposals'][0]
        with pytest.raises(ValueError,match='qualifications'):a.review(spec,reviewer='Fixture',rationale='Must fail',evidence_updates={'warranty':{'proposal_id':p['id'],'semantic_equivalence':True,'rationale':'Invalid shortcut'}})


def test_stale_evidence_only_approval_rejected_before_app(tmp_path):
    before,after,spec=pair(tmp_path);p=spec['evidence_proposals'][0]
    review=a.review(spec,reviewer='Fixture',rationale='Explicit fixture',evidence_updates={'warranty':{'proposal_id':p['id'],'semantic_equivalence':True,'rationale':'Fixture declaration'}})
    (Path(after['_root'])/'docs/policy.txt').write_text('Warranty is 99 days.')
    with pytest.raises(ValueError,match='Stale'):
        a.execute(before,read_config(after['_root']),spec,approval=review,callback=lambda *args:pytest.fail('No stale dispatch'),persist=False)


def test_routing_retains_active_conflicts_and_excludes_only_declared_archive(tmp_path):
    from sourceroi.live.routing import restrict
    from sourceroi.live.evidence_contract import precheck
    tasks=[{'id':'x','question':'CURRENT threshold?','expected':'12'}]
    cfg=workspace(tmp_path/'app','Threshold is 12 units.',tasks=tasks,extras={'archive':'Threshold is 10 units.'},settings={'retrieval_contract':ROUTE})
    _,chunks=scan_sources(cfg);r,trace=restrict(tasks[0]['question'],chunks,cfg)
    assert {c['source_id'] for c in r}=={'current'} and trace['matched_rule_indices']==[0]
    _,screen=precheck('threshold',r,cfg,{'version':1,'subject_aliases':[['threshold']]})
    assert not screen['potential_conflicts']
    (Path(cfg['_root'])/'docs/contradiction.txt').write_text('Threshold is 13 units.')
    _,chunks=scan_sources(cfg);r,_=restrict('CURRENT threshold?',chunks,cfg)
    _,screen=precheck('threshold',r,cfg,{'version':1,'subject_aliases':[['threshold']]})
    assert screen['abstain'] and screen['potential_conflicts']
    _,wrong=precheck('threshold',r,cfg,None,{'jurisdiction':'CA'})
    assert wrong['abstain']


@pytest.mark.parametrize('key',['source_versions','tasks','expected_answers','evidence_requirements','scope','citation_requirements','intent','approval','semantic_reviews','routing_contract'])
def test_comparator_parity_rejects_every_authority_dimension(tmp_path,key):
    before,after,spec=pair(tmp_path)
    left=packet(after,load_benchmark(before),spec=spec,approval=None);right=deepcopy(left)
    right[key]={'tampered':True}
    with pytest.raises(ValueError,match='input mismatch'):assert_parity(left,right)
    assert assert_parity(left,deepcopy(left))['status']=='VERIFIED_INPUT_PARITY'


def test_unknown_dependencies_not_dropped_without_history(tmp_path):
    tasks=[{'id':'unknown','question':'An unrelated question?','expected':'x','evidence':[]}]
    old=workspace(tmp_path/'src','An original record.',tasks=tasks);freeze(old,tmp_path/'old')
    new=workspace(tmp_path/'new','A changed record.',tasks=tasks)
    impact=a.propose(read_config(tmp_path/'old'),new)['impact'][0]
    assert impact['dependency_class']=='unknown' and impact['potentially_affected']


def test_application_and_data_ci_share_declared_routing(tmp_path,monkeypatch):
    from sourceroi.live.engine import evaluate_variant
    from sourceroi.live.data_ci import run_data_ci
    from sourceroi.live.evidence_contract import abstention
    tasks=[{'id':'threshold','question':'CURRENT threshold?','expected':'12','scoring':'numeric','requires_grounding':True,
        'evidence_contract':{'version':1,'subject_aliases':[['threshold']]},'evidence':[{'document_id':'current::policy.txt','quote':'Threshold is 12 units.'}]}]
    old=workspace(tmp_path/'src','Threshold is 12 units.',tasks=tasks,extras={'archive':'Threshold is 10 units.'},settings={'retrieval_contract':ROUTE})
    freeze(old,tmp_path/'old');before=read_config(tmp_path/'old')
    after=workspace(tmp_path/'new','Threshold is 14 units.',tasks=tasks,extras={'archive':'Threshold is 10 units.'},settings={'retrieval_contract':ROUTE})
    calls=[]
    def fixture(question,context,cfg):
        calls.append([c['id'] for c in context]);assert {c['source_id'] for c in context}=={'current'}
        result=abstention(cfg['_grounding_precheck'],cfg)
        return {**result,'answer':'12','citations':[context[0]['id']]}
    monkeypatch.setattr('sourceroi.live.engine.run_chat',fixture)
    for cfg in (before,after):evaluate_variant(cfg,load_benchmark(cfg),scan_sources(cfg)[1],[])
    report=run_data_ci(before,after,max_tasks=1)
    assert calls[:2]==calls[2:] and len(calls)==4
    assert all(r['tasks'][0]['selection']['routing_contract']['matched_rule_indices']==[0] for r in (report['baseline'],report['candidate']))


def test_forged_evidence_proposal_rejected_before_dispatch(tmp_path):
    before,after,spec=pair(tmp_path)
    spec=deepcopy(spec);proposal=spec['evidence_proposals'][0]
    proposal['replacement_evidence'][0]['quote']='Unrelated is 21 days.'
    proposal['id']=digest({k:v for k,v in proposal.items() if k!='id'})
    spec['id']=digest({k:v for k,v in spec.items() if k!='id'})
    review=a.review(spec,reviewer='Fixture',rationale='Not independent',evidence_updates={'warranty':{'proposal_id':proposal['id'],'semantic_equivalence':True,'rationale':'Forged fixture'}})
    with pytest.raises(ValueError,match='not canonical'):
        a.execute(before,after,spec,approval=review,callback=lambda *args:pytest.fail('No forged dispatch'),persist=False)


@pytest.mark.parametrize('changes',[{'jurisdiction':'CA'},{'effective_from':'2030-01-01','effective_to':'2031-01-01'},{'authority':None}])
def test_evidence_proposal_rejects_inapplicable_or_unattributed_source(tmp_path,changes):
    before,after,_=pair(tmp_path)
    after['sources'][0].update(changes)
    tasks=load_benchmark(before);tasks[0]['scope']={'jurisdiction':'US','as_of':'2025-06-01'}
    from sourceroi.live.maintenance_evidence import evidence_proposals
    assert not evidence_proposals(before,after,tasks)


def test_independent_registered_evidence_is_explained_not_guessed(tmp_path):
    tasks=[{'id':'other','question':'What is the independent warranty?','expected':'21','evidence':[{'document_id':'archive::extra.txt','quote':'Independent warranty is 21 days.'}]}]
    old=workspace(tmp_path/'src','A primary fact.',tasks=tasks,extras={'archive':'Independent warranty is 21 days.'});freeze(old,tmp_path/'old')
    new=workspace(tmp_path/'new','A changed primary fact.',tasks=tasks,extras={'archive':'Independent warranty is 21 days.'})
    row=a.propose(read_config(tmp_path/'old'),new)['impact'][0]
    assert row['dependency_class']=='unrelated_registered_evidence' and not row['potentially_affected']
    assert row['selection_status']=='retain_for_full_release'


def test_frozen_value_proposal_cases_do_not_use_gold():
    from tools.replay_evaluation_hardening import proposal_cases
    frozen=json.loads(Path('docs/artifacts/evaluation-hardening/frozen-proposal-cases.json').read_text())
    result=proposal_cases(frozen['cases'])
    assert result['supported_proposals']==3 and result['wrong_proposals']==0 and result['negative_abstentions']==3
    assert all(r['matched'] for r in result['cases'])


@pytest.mark.parametrize('contract',[
    {'version':1,'rules':[{'contains':'CURRENT','source_ids':['unregistered']}]},
    {'version':1,'rules':[{'contains':'','source_ids':['current']}]},
    {'version':1,'rules':[{'contains':'CURRENT','source_ids':['current'],'case_sensitive':'false'}]},
])
def test_invalid_routing_contract_fails_at_configuration(tmp_path,contract):
    with pytest.raises(ValueError):workspace(tmp_path/'app','Threshold is 12.',settings={'retrieval_contract':contract})


def test_comparative_harness_rejects_mismatch_before_runtime(tmp_path,monkeypatch):
    import hashlib
    from tools import run_empirical_experiment as harness
    before,after,spec=pair(tmp_path)
    for cfg in (before,after):
        path=Path(cfg['_root'])/'project.json';data=json.loads(path.read_text())
        data['settings']['retrieval_contract']=ROUTE;path.write_text(json.dumps(data))
    # Fresh deterministic fixture snapshot for the newly declared contract.
    # No old snapshot or historical experiment is edited.
    from shutil import rmtree
    # Freeze from source also needs the same declared contract.
    path=tmp_path/'source/project.json';data=json.loads(path.read_text());data['settings']['retrieval_contract']=ROUTE;path.write_text(json.dumps(data))
    rmtree(tmp_path/'accepted');freeze(read_config(tmp_path/'source'),tmp_path/'accepted')
    before=read_config(tmp_path/'accepted');after=read_config(tmp_path/'candidate');spec=a.propose(before,after)
    review=a.review(spec,reviewer='Fixture only',rationale='Deterministic input parity test',protected_tasks=['warranty'])
    (tmp_path/'change-plan.json').write_text(json.dumps(spec));rp=tmp_path/'review.json';rp.write_text(json.dumps(review))
    manifest={str(p.relative_to(tmp_path)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('accepted','candidate') for p in (tmp_path/folder).rglob('*') if p.is_file()}
    (tmp_path/'freeze-manifest.json').write_text(json.dumps(manifest))
    auth=tmp_path/'fixture-authorization.json';auth.write_text(json.dumps({'scope':'benchmark','status':'approved'}))
    packets={name:packet(cfg,maintained_tasks(load_benchmark(cfg),spec,review) if name=='candidate' else load_benchmark(cfg),spec=spec,approval=review) for name,cfg in [('accepted',before),('candidate',after)]}
    packets['candidate']['scope']={'tampered':True};cp=tmp_path/'conventional.json';cp.write_text(json.dumps(packets))
    monkeypatch.setattr(harness,'Experiment',lambda *args,**kwargs:pytest.fail('No runtime startup for mismatched comparison'))
    with pytest.raises(ValueError,match='input mismatch'):
        harness.execute(tmp_path,tmp_path/'output',auth,review_path=rp,conventional_packet=cp)
    assert not (tmp_path/'output').exists()
