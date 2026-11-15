from copy import deepcopy
import json
from pathlib import Path
import pytest
from sourceroi.live.answer_contract import check,validate
from sourceroi.live.evidence_contract import precheck
from sourceroi.live.release_policy import resolve,inspect
from sourceroi.live.provider import run_chat

NUM={'version':1,'type':'numeric'}
EVIDENCE={'version':1,'subject_aliases':[['return','returns','returned','sent back']]}

def chunk(text,id='policy::probe#chunk0',**metadata):
    return {'id':id,'document_id':id.split('#')[0],'source_id':'policy','title':'Policy','text':text,**metadata}

def cfg():
    return {'model':{'name':'mock','base_url':'http://127.0.0.1:8788/v1','local_only':True},'sources':[{'id':'policy'}],'settings':{'release_policy':'strict_grounded'}}

@pytest.mark.parametrize('value,kind,valid',[(14,'numeric',True),('14','numeric',True),('14 days','numeric',False),(True,'numeric',False),
    (True,'boolean',True),('true','boolean',True),('yes','boolean',False),('14','text',True),(14,'text',False)])
def test_declared_scalar_types_do_not_change_truth(value,kind,valid):
    assert check(value,{'version':1,'type':kind})[0] is valid

def test_guard_abstains_without_model_when_declared_subject_is_missing(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *a:pytest.fail('No model request expected'))
    result=run_chat('Return period?',[chunk('Warranty coverage lasts 14 days.')],{**cfg(),'_answer_contract':NUM,'_evidence_contract':EVIDENCE})
    assert result['answer']=='INSUFFICIENT_EVIDENCE' and result['answer_origin']=='evidence_precheck'
    assert result['raw_response'] is None and result['input_tokens']==0
    assert result['grounding_precheck']['entailment']=='unverified'

def test_paraphrase_alias_is_not_rejected_but_not_proven_semantic():
    eligible,trace=precheck('Return period?',[chunk('Items can be sent back within a fortnight.')],cfg(),EVIDENCE)
    assert eligible and not trace['abstain'] and trace['entailment']=='unverified'

def test_scope_filters_only_explicitly_inapplicable_information():
    context=[chunk('Return within 30 days.','policy::old#chunk0',jurisdiction='US',effective_to='2020-01-01'),
        chunk('Return within 14 days.','policy::new#chunk0',jurisdiction='US',effective_from='2025-01-01')]
    eligible,trace=precheck('Return period?',context,cfg(),EVIDENCE,{'jurisdiction':'US','as_of':'2026-11-13'})
    assert [c['id'] for c in eligible]==['policy::new#chunk0']
    assert trace['excluded_inapplicable_ids']==['policy::old#chunk0']
    assert not trace['potential_conflicts']

def test_conflicting_same_predicate_abstains_without_resolving_truth():
    _,trace=precheck('Return period?',[chunk('Returns are allowed for 14 days.'),chunk('Returns are allowed for 30 days.','policy::other#chunk0')],cfg(),EVIDENCE)
    assert trace['abstain'] and trace['potential_conflicts']

def test_raw_and_normalized_answer_preserved_without_unit_stripping(monkeypatch):
    raw='{"answer":"14 days","citations":["policy::probe#chunk0"]}'
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *a:{'choices':[{'message':{'content':raw},'finish_reason':'stop'}]})
    result=run_chat('Return period?',[chunk('Return within 14 days.')],{**cfg(),'_answer_contract':NUM})
    assert result['raw_response']==raw and result['raw_answer']=='14 days' and result['normalized_answer']=='14 days'
    assert result['json_format_valid'] and not result['answer_contract_valid']

def test_closed_flat_structured_answer_is_explicit(monkeypatch):
    contract={'version':1,'type':'structured','schema':{'type':'object','properties':{'days':{'type':'number'},'eligible':{'type':'boolean'}},'required':['days','eligible'],'additionalProperties':False}}
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *a:{'choices':[{'message':{'content':'{"answer":{"eligible":true,"days":14},"citations":[]}'},'finish_reason':'stop'}]})
    result=run_chat('Policy?', [chunk('Policy')],{**cfg(),'_answer_contract':contract})
    assert result['raw_answer']=={'eligible':True,'days':14} and result['answer']=='{"days":14,"eligible":true}' and result['answer_contract_valid']
    assert not check({'days':14,'eligible':True,'extra':1},contract)[0]
    from sourceroi.live.grade import grade
    task={'expected':'{"days":14,"eligible":true}','scoring':'structured_exact','answer_contract':contract}
    assert grade(result['answer'],task)
    assert not grade('{"days":true,"eligible":true}',task)

def test_strict_workspace_cannot_be_downgraded():
    with pytest.raises(ValueError,match='downgraded'):resolve(cfg(),'legacy_exact')

def test_contract_is_not_a_ground_truth_label():
    _,trace=precheck('Return period?',[chunk('Returns are not permitted.')],cfg(),EVIDENCE)
    assert not trace['abstain'] # Topic match is insufficient; this remains a model/review case.
    assert trace['entailment']=='unverified'

def test_format_violation_blocks_even_contains_grader(tmp_path):
    from examples.knowledge_change.demo import workspace,external_agent
    from sourceroi.live.data_ci import freeze
    from sourceroi.live.config import read_config
    from sourceroi.live import assurance as a
    source=workspace(tmp_path/'source');p=Path(source['_root'])/'benchmark.jsonl'
    tasks=[json.loads(x) for x in p.read_text().splitlines()]
    tasks[0].update(answer_contract=NUM,scoring='contains')
    p.write_text('\n'.join(json.dumps(t) for t in tasks));freeze(source,tmp_path/'accepted');before=read_config(tmp_path/'accepted')
    spec=a.propose(before,source);approval=a.review(spec,reviewer='unit fixture',rationale='Protect registered values',protected_tasks=['returns','warranty'])
    def callback(c,ts):
        result=external_agent(c,ts)
        for r in result['tasks']:
            if r['id']=='returns':r['answer']='30 days'
        return result
    result=a.execute(before,source,spec,approval=approval,callback=callback)
    assert result['verdict']=='BLOCK' and result['check_statuses']['answer_format']=='BLOCK'

def test_task_annotations_do_not_weaken_grounding(tmp_path):
    from examples.knowledge_change.demo import workspace
    from sourceroi.live.ingest import load_benchmark
    c=workspace(tmp_path/'src');p=Path(c['_root'])/'benchmark.jsonl';tasks=[json.loads(x) for x in p.read_text().splitlines()]
    tasks[0].update(answer_contract=NUM,evidence_contract=EVIDENCE,requires_grounding=True)
    p.write_text('\n'.join(json.dumps(t) for t in tasks))
    loaded=load_benchmark(c)[0]
    assert loaded['expected']=='30' and loaded['answer_contract']==NUM and loaded['evidence_contract']==EVIDENCE

def owner_bundle():
    return {'version':1,'owner':'unit fixture, not actual human','labels_established_at':'2020-01-01T00:00:00Z','labels_from_evaluated_model':False,
        'before_documents':[{'source_id':'policy','name':'returns.txt','text':'Return within 30 days.','metadata':{'authority':'unit owner'}}],
        'after_documents':[{'source_id':'policy','name':'returns.txt','text':'Return within 14 days.','metadata':{'authority':'unit owner'}}],
        'tasks':[{'id':'returns','question':'Return period?','expected_before':'30','expected_after':'14','intended_change':True,
            'answer_contract':NUM,'evidence_contract':EVIDENCE,'evidence_before':[{'document_id':'policy::returns.txt','quote':'30 days'}],
            'evidence_after':[{'document_id':'policy::returns.txt','quote':'14 days'}]}]}

def test_owner_onboarding_runs_without_editing_internals_or_approving_labels(tmp_path):
    from tools.source_owner_onboarding import materialize
    from sourceroi.live.config import read_config
    from sourceroi.live.ingest import load_benchmark
    from sourceroi.live import assurance as a
    out=tmp_path/'pilot';result=materialize(owner_bundle(),out)
    assert result['model_calls']==0 and result['review_status']=='pending explicit approval'
    before=read_config(out/'accepted');after=read_config(out/'candidate')
    assert load_benchmark(before)==load_benchmark(after) and load_benchmark(after)[0]['expected']=='30'
    spec=a.propose(before,after,intent=json.loads((out/'intent.json').read_text()))
    assert spec['evaluation_proposals'][0]['suggested_expected']=='14'
    assert not (out/'approval.json').exists()
    with pytest.raises(ValueError):materialize(owner_bundle(),out)

def test_owner_workflow_rejects_bad_labels_and_paths(tmp_path):
    from tools.source_owner_onboarding import materialize
    bundle=owner_bundle();bundle['tasks'][0]['expected_after']='14 days'
    with pytest.raises(ValueError,match='response type'):materialize(bundle,tmp_path/'bad-label')
    bundle=owner_bundle();bundle['after_documents'][0]['name']='../../secret.txt'
    with pytest.raises(ValueError,match='basenames'):materialize(bundle,tmp_path/'bad-path')
    bundle=owner_bundle();bundle['labels_from_evaluated_model']=True
    with pytest.raises(ValueError,match='provenance'):materialize(bundle,tmp_path/'circular')

def test_structured_grader_keeps_boolean_and_number_distinct():
    from sourceroi.live.grade import grade
    contract={'version':1,'type':'structured','schema':{'type':'object','properties':{'count':{'type':'number'}},'required':['count'],'additionalProperties':False}}
    assert grade('{"count":14}',{'expected':'{"count":14}','scoring':'structured_exact','answer_contract':contract})
    assert not grade('{"count":true}',{'expected':'{"count":1}','scoring':'structured_exact','answer_contract':contract})

def test_strict_empty_context_cannot_bypass_abstention_with_cached_trace(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *a:pytest.fail('Empty-context generation forbidden'))
    result=run_chat('Return period?',[],{**cfg(),'_answer_contract':NUM,'_grounding_precheck':{'abstain':False,'mode':'raw_control'}})
    assert result['answer']=='INSUFFICIENT_EVIDENCE' and result['raw_response'] is None
    assert result['answer_origin']=='evidence_precheck'

def test_declared_numeric_prompt_has_no_conflicting_string_or_yes_no_instruction(monkeypatch):
    c=cfg();c['model']['compact_source_ids']=True
    def post(url,body,*a):
        system=body['messages'][0]['content']
        assert 'a concise string' not in system and 'phrase or yes/no' not in system
        assert 'ONE matching alias suffices' in system
        return {'choices':[{'message':{'content':'{"answer":14,"citations":["1"]}'},'finish_reason':'stop'}]}
    monkeypatch.setattr('sourceroi.live.provider._post',post)
    result=run_chat('Return period?',[chunk('Return within 14 days.')],{**c,'_answer_contract':NUM,'_evidence_contract':EVIDENCE})
    assert result['raw_answer']==14 and result['answer_contract_valid']

def test_onboarding_draft_cannot_be_accidentally_approved(tmp_path):
    from tools.source_owner_onboarding import materialize
    from sourceroi.live import assurance as a
    from sourceroi.live.config import read_config
    out=tmp_path/'pilot';materialize(owner_bundle(),out)
    spec=a.propose(read_config(out/'accepted'),read_config(out/'candidate'),intent=json.loads((out/'intent.json').read_text()))
    decisions=json.loads((out/'review-decisions-DRAFT.json').read_text())
    with pytest.raises(ValueError,match='Draft'):a.review(spec,**decisions)
    decisions['rationale']='Unit test explicit review, not an actual human study'
    assert a.review(spec,**decisions)['spec_id']==spec['id']

def test_software_abstention_is_not_misdiagnosed_as_model_generation():
    from sourceroi.live.diagnosis import diagnose
    result=diagnose({'id':'t','question':'Return period?','evidence':[]},
        {'answer_origin':'evidence_precheck','grounding_precheck':{'abstain':True,'reasons':['declared_subject_requirement_missing']}},[])
    assert result['classification']=='declared_evidence_precheck_abstention'
    assert result['model_generation_executed'] is False and result['certainty']=='mechanism_observed_not_semantic_proof'
