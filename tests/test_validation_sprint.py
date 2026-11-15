import json
import math
import pytest
from sourceroi.live.provider import _parse_answer,normalize_answer_value,ProviderError,run_chat

@pytest.mark.parametrize('value,expected',[(365,'365'),(14.5,'14.5'),(-3,'-3'),(True,'true'),(False,'false'),('0014','0014')])
def test_explicit_scalar_normalization(value,expected):
    assert _parse_answer(json.dumps({'answer':value,'citations':['source#0']}))==(expected,['source#0'],True)

@pytest.mark.parametrize('raw',['{"answer":null}','{"answer":[]}','{"answer":{}}','{"answer":NaN}',
 '{"answer":Infinity}','{"answer":1e999}','{"answer":"1","answer":"2"}',
 '{"answer":1,"citations":"x"}','{"answer":1,"citations":[1]}','{"answer":1,"citations":[""]}',
 '[{"answer":"1"}]','plain answer','{"citations":[]}','{"answer":" "}','{"answer":14,"expected":14}'])
def test_bad_schema_is_invalid_not_silently_repaired(raw):
    assert not _parse_answer(raw)[2]

def test_numeric_answer_without_citations_preserves_legacy_shape():
    assert _parse_answer('{"answer":365}')==('365',[],True)
    assert _parse_answer('```json\n{"answer":14,"citations":[]}\n```')==('14',[],True)

def test_invalid_schema_cannot_pass_provider_completion(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *args,**kw:{'choices':[{'finish_reason':'stop','message':{'content':'{"answer":null}'}}]})
    result=run_chat('Question',[],{'model':{'name':'mock','base_url':'http://127.0.0.1:8788/v1','local_only':True}})
    assert not result['response_complete'] and not result['json_format_valid']

def test_version_ack_and_manifest_fail_closed(tmp_path,monkeypatch):
    from examples.knowledge_change.demo import workspace
    from sourceroi.live.ingest import scan_sources
    from sourceroi.live.provider import run_external
    cfg=workspace(tmp_path/'app');manifest={d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}
    cfg['agent']={'url':'http://127.0.0.1:1/evaluate','api_key_env':'','protocol_version':2,'capabilities':[],'knowledge_manifest':manifest}
    def response(url,payload,*args):
        return {'answer':'30','filter_applied':True,'request_id':payload['request_id'],
            'enforced_restrictions':{k:payload[k] for k in ('allowed_source_ids','excluded_source_ids','excluded_document_ids')},
            'retrieval_controls_applied':{},'knowledge_version':'wrong','knowledge_manifest':manifest}
    monkeypatch.setattr('sourceroi.live.provider._post',response)
    with pytest.raises(ProviderError,match='knowledge version'):run_external('returns_days',['policy'],[],[],cfg,'task')
    def mismatch(url,payload,*args):
        result=response(url,payload,*args);result['knowledge_version']=payload['knowledge_version'];result['knowledge_manifest']={};return result
    monkeypatch.setattr('sourceroi.live.provider._post',mismatch)
    with pytest.raises(ProviderError,match='manifest'):run_external('returns_days',['policy'],[],[],cfg,'task')

def test_separate_application_rereads_actual_files(tmp_path):
    from examples.knowledge_change.demo import workspace
    from examples.external_record_rag.server import evaluate
    from sourceroi.live.adapter import attach_contract
    from sourceroi.live.ingest import scan_sources
    cfg=workspace(tmp_path/'app');manifest={d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}
    payload=attach_contract({'task_id':'t','question':'What is returns_days?','allowed_source_ids':['policy'],'excluded_source_ids':[],
        'excluded_document_ids':[],'request_filter_ack':True},{'protocol_version':2,'capabilities':[],'knowledge_manifest':manifest},{})
    assert evaluate(payload,[tmp_path/'app'])['answer']=='30'
    (tmp_path/'app/sources/policy/returns.json').write_text('{"returns_days":14}')
    with pytest.raises(ValueError,match='not available'):evaluate(payload,[tmp_path/'app'])

def test_external_retrieval_trace_is_preserved_in_engine(tmp_path,monkeypatch):
    from examples.knowledge_change.demo import workspace
    from sourceroi.live.engine import evaluate_variant
    from sourceroi.live.ingest import scan_sources,load_benchmark
    cfg=workspace(tmp_path/'app');cfg['runner']='http_agent'
    cfg['agent']={'url':'http://127.0.0.1:1/evaluate','api_key_env':'','protocol_version':2,'capabilities':[]}
    def response(url,payload,*args):
        cid='policy::returns.json#chunk0'
        return {'answer':30,'citations':[cid],'retrieved_chunk_ids':[cid],'filter_applied':True,'request_id':payload['request_id'],
            'enforced_restrictions':{k:payload[k] for k in ('allowed_source_ids','excluded_source_ids','excluded_document_ids')},'retrieval_controls_applied':{},'usage':{}}
    monkeypatch.setattr('sourceroi.live.provider._post',response)
    result=evaluate_variant(cfg,load_benchmark(cfg)[:1],scan_sources(cfg)[1],[])
    assert result['tasks'][0]['retrieved_chunk_ids']==['policy::returns.json#chunk0']
    assert result['tasks'][0]['correct']

def test_semantic_checks_do_not_fabricate_entailment():
    from tools.validate_semantic_citations import samples
    from sourceroi.live.reliability_review import evaluate
    records={s['id']:evaluate(s) for s in samples()}
    assert all(r['semantic_correctness'] is None and r['citation_correctness'] is None for r in records.values())
    for key in ('wrong_jurisdiction','outdated_policy','future_policy'):
        assert records[key]['deterministic']['explicit_applicability'][0]['applicable'] is False
    assert records['fabricated_citation']['deterministic']['invalid_citations']
    assert records['no_citation']['deterministic']['missing_citations']
    assert records['correct_number_wrong_support']['semantic_correctness'] is None

def test_external_semantic_review_bound_to_sample_and_cited_quotes():
    from tools.validate_semantic_citations import samples
    from sourceroi.live.reliability_review import packet,evaluate
    sample=next(s for s in samples() if s['id']=='correct_supported_literal')
    review=packet(sample)
    review.update(status='complete',reviewer='unit-test-reviewer',independent_of_generator=True,semantic_correctness=True,citation_correctness=True,
        scope_appropriate=True,uses_outdated_fact=False,claims=[{'start':0,'end':len(sample['answer']),'verdict':'supported',
            'evidence':[{'id':'policy#0','quote':sample['context'][0]['text']}]}])
    with pytest.raises(ValueError):evaluate(sample,review)
    assert evaluate(sample,review,allowed_reviewers=['unit-test-reviewer'])['groundedness']==1
    review['claims'][0]['evidence'][0]['quote']='invented'
    with pytest.raises(ValueError):evaluate(sample,review,allowed_reviewers=['unit-test-reviewer'])

def test_unannotated_final_validation_cannot_freeze(tmp_path):
    from tools.independent_validation import template,freeze
    with pytest.raises(ValueError,match='reviewers'):freeze(template(),tmp_path/'frozen.json')

def test_final_split_overlap_and_independence_safeguards(tmp_path):
    from tools.independent_validation import template,freeze,TOPICS
    from copy import deepcopy
    data=template();data['reviewers']=[{'id':'unit-test-external-reviewer','independent_of_implementation':True,'operator_verified':True}]
    def case(id,text):
        return {'id':id,'document_group':id,'topics':TOPICS,'before_documents':[{'id':id,'text':text}],
            'after_documents':[],'question':'Policy?','expected_before':'A','expected_after':'unknown','release_outcome':'REVIEW',
            'label_basis':'source_owner','reviewer':'unit-test-external-reviewer','review_status':'complete',
            'label_established_at':'2020-01-01T00:00:00Z','outputs_seen_by_labeler':False,
            'source_citations':[{'version':'before','document_id':id,'quote':text}]}
    data['development']=[case('dev','Internal handbook alpha')];data['final']=[case('final','External charter beta')]
    frozen=freeze(data,tmp_path/'valid.json');assert frozen['execution_state']=='not_run'
    leaked=deepcopy(data);leaked['final'][0]['before_documents'][0]['text']='Internal handbook alpha';leaked['final'][0]['source_citations'][0]['quote']='Internal handbook alpha'
    with pytest.raises(ValueError,match='overlap'):freeze(leaked,tmp_path/'leak.json')
    leaked=deepcopy(data);leaked['final'][0]['outputs_seen_by_labeler']=True
    with pytest.raises(ValueError,match='precede'):freeze(leaked,tmp_path/'exposed.json')

def test_equivalent_authority_comparison_has_no_manufactured_win(tmp_path,capsys):
    from tools.validate_fair_baselines import main
    result=main(tmp_path/'fair.json')
    assert result['confusion_matrices']['C_maintained_full_suite']==result['confusion_matrices']['E_SourceROI']
    assert result['confusion_matrices']['A_updated_answers']['ACCEPT']['BLOCK']==0
    assert all(r['methods']['C_maintained_full_suite']['authority']==r['methods']['E_SourceROI']['authority'] for r in result['scenarios'])
    assert sum(r['suggestions']['known_incorrect'] for r in result['scenarios'])==0

def test_version_proof_requires_v2():
    from sourceroi.live.adapter import attach_contract
    with pytest.raises(ValueError,match='v2'):attach_contract({}, {'protocol_version':1,'knowledge_manifest':{'d':'0'*64}}, {})

def test_real_release_packet_requires_exact_executed_source_version(tmp_path):
    from examples.knowledge_change.demo import workspace
    from tools.release_review_packet import export,score
    from sourceroi.live.assurance import inventory
    from sourceroi.live.data_ci import digest
    cfg=workspace(tmp_path/'app');version=digest(inventory(cfg)[0])
    row={'id':'returns','question':'What is returns_days?','actual':'30','citations':[],'retrieved_chunk_ids':['policy::returns.json#chunk0'],'json_format_valid':True}
    report={'spec_id':'test','versions':{'baseline_sources':version,'candidate_sources':version},'baseline':{'tasks':[row]},'candidate':{'tasks':[row]}}
    result=export(report,tmp_path/'app',tmp_path/'app')
    assert score(result,[])['semantic_correctness_rate'] is None
    (tmp_path/'app/sources/policy/returns.json').write_text('{"returns_days":14}')
    with pytest.raises(ValueError,match='Source version'):export(report,tmp_path/'app',tmp_path/'app')

def test_external_completion_flag_cannot_be_ignored(monkeypatch):
    from sourceroi.live.provider import run_external
    cfg={'agent':{'url':'http://127.0.0.1:1','api_key_env':''}}
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *args:{'answer':14,'filter_applied':True,'response_complete':False})
    assert run_external('q',['policy'],[],[],cfg,'task')['response_complete'] is False
    monkeypatch.setattr('sourceroi.live.provider._post',lambda *args:{'answer':14,'filter_applied':True,'response_complete':'false'})
    with pytest.raises(ProviderError):run_external('q',['policy'],[],[],cfg,'task')
