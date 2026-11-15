"""Clearly synthetic development fixtures; no independent human review claims."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from sourceroi.live import facts
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.validation import Budget
from sourceroi.live.policies import select_context


def setup(tmp_path,documents=None):
    root=tmp_path/'source';root.mkdir();(root/'sources').mkdir()
    for name,text in (documents or {'finance.txt':'ExampleCo revenue is 900 dollars for Q1, and 1040 dollars for Q2.'}).items():
        (root/'sources'/name).write_text(text)
    cfg={'_root':str(root),'id':'authored','runner':'rag_chat','benchmark':'benchmark.jsonl',
         'model':{'name':'unused','base_url':'http://127.0.0.1:9/v1','local_only':True},
         'settings':{'chunk_strategy':'sentences','max_chunks':3,'answering_mode':'source_calculation','calculation_reviewers':['development-operator'],
                     'retrieval_policy':{'name':'predicate'}},
         'sources':[{'id':'data','path':'sources','jurisdiction':'US','policy_scope':'finance','authority':'synthetic fixture'}]}
    return cfg


def contract(operation='subtract',periods=('Q2','Q1'),subject='ExampleCo',predicate='revenue',unit='dollars'):
    return {'version':1,'operation':operation,'operands':[{'subject':subject,'predicate':predicate,'unit':unit,'period':p} for p in periods]}


def task(spec=None):
    spec=spec or contract();q='What is ExampleCo revenue for Q2 minus Q1?';scope={'jurisdiction':'US','policy_scope':'finance'}
    return {'id':'gap','question':q,'expected':'140','scoring':'numeric','category':'synthetic','scope':scope,'requires_grounding':True,
            'answer_contract':{'version':1,'type':'numeric'},'calculation_contract':spec,
            'calculation_authorization':facts.authorize(q,scope,spec,reviewer='development-operator',rationale='Authored fixture operation, not human semantic approval')}


def test_source_bound_execution_uses_no_model_and_does_not_read_expected(tmp_path,monkeypatch):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg);t=task();cfg['_experiment_budget']=Budget({'max_model_calls_per_run':1})
    monkeypatch.setattr('sourceroi.live.engine.run_chat',lambda *a:pytest.fail('Explicit deterministic mode must not generate'))
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert row['actual']=='140' and row['correct'] and row['answer_origin']=='source_calculation'
    assert row['prompt_tokens']==row['completion_tokens']==cfg['_experiment_budget'].calls==0
    assert row['groundedness'] is None and row['calculation']['semantic_approval'] is None
    t['expected']='999999'
    again=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert again['actual']=='140' and not again['correct']
    assert len(row['calculation']['operands'])==2
    text=(Path(cfg['_root'])/'sources/finance.txt').read_text()
    for operand in row['calculation']['operands']:
        for fact in operand['facts']:
            assert text[fact['quote_start']:fact['quote_end']]==fact['quote']
            assert fact['source_version']==hashlib.sha256(text.encode()).hexdigest()
            assert fact['subject']=='ExampleCo' and fact['predicate']=='revenue'


@pytest.mark.parametrize('operation,periods,value',[
    ('lookup',('Q1',),'900'),('add',('Q1','Q2'),'1940'),('subtract',('Q2','Q1'),'140'),
    ('greater_than',('Q2','Q1'),'true'),('less_than',('Q2','Q1'),'false'),('equal',('Q1','Q1'),'true')])
def test_operations_and_period_front_grammar(tmp_path,operation,periods,value):
    cfg=setup(tmp_path,{'old.txt':'ExampleCo revenue for Q1 is 900 dollars.','new.txt':'ExampleCo revenue for Q2 is 1040 dollars.'})
    _,chunks=scan_sources(cfg);result=facts.calculate(chunks,contract(operation,periods),cfg)
    assert result['value']==value and result['status']=='REVIEW'
    assert all(o['facts'] for o in result['operands'])


def test_correct_number_under_other_predicate_is_not_support(tmp_path):
    cfg=setup(tmp_path,{'finance.txt':'ExampleCo revenue is 900 dollars for Q1, and OtherCo revenue is 1040 dollars for Q2.'})
    _,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract('lookup',('Q2',)),cfg)['value'] is None


def test_conflicts_are_retained_and_block_calculation(tmp_path):
    cfg=setup(tmp_path,{'a.txt':'ExampleCo revenue is 900 dollars for Q1.','b.txt':'ExampleCo revenue is 910 dollars for Q1.'})
    _,chunks=scan_sources(cfg);spec=contract('lookup',('Q1',));r=facts.calculate(chunks,spec,cfg)
    assert r['binding_status']=='conflict' and r['value'] is None
    assert {f['value'] for f in r['operands'][0]['facts']}=={'900','910'}
    selected,trace=select_context('revenue?',chunks,{**cfg,'_calculation_contract':spec})
    assert len(selected)==2


@pytest.mark.parametrize('mutation',['question','scope','formula','reviewer','missing'])
def test_task_authorization_cannot_be_reused(tmp_path,mutation):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg);t=task()
    if mutation=='question':t['question']='What is ExampleCo revenue for Q1 minus Q2?'
    if mutation=='scope':t['scope']['jurisdiction']='global'
    if mutation=='formula':t['calculation_contract']['operation']='add'
    if mutation=='reviewer':t['calculation_authorization']['reviewer']='unknown'
    if mutation=='missing':t.pop('calculation_authorization')
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert row['actual']=='INSUFFICIENT_EVIDENCE'
    assert not row['calculation']['operation_authorized']


def test_provenance_tampering_rejected_even_with_recomputed_id(tmp_path):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg);c=deepcopy(chunks[0]);c['text']=c['text'].replace('1040','1090')
    c['id']=f"{c['document_id']}#chunk-p{c['start']}-{c['end']}-{hashlib.sha256(c['text'].encode()).hexdigest()[:12]}"
    assert facts.calculate([c],contract(),cfg)['binding_status']=='invalid_provenance'
    forged=deepcopy(chunks);forged[0]['jurisdiction']='CA'
    assert facts.calculate(forged,contract(),cfg,{'jurisdiction':'CA'})['value'] is None


@pytest.mark.parametrize('text',[
    'ExampleCo revenue is not 900 dollars for Q1.',
    'ExampleCo revenue is 900 dollars for Q1. However, contractors are excluded.',
    'ExampleCo revenue is 900 dollars for Q1 if eligibility is met.',
    'ExampleCo revenue is approximately 900 dollars for Q1.',
    'Eligibility is granted to permanent staff.'])
def test_qualified_or_non_numeric_claims_not_promoted(tmp_path,text):
    cfg=setup(tmp_path,{'policy.txt':text});_,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract('lookup',('Q1',)),cfg)['value'] is None


def test_scope_missing_period_and_units(tmp_path):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(),cfg,{'jurisdiction':'CA'})['binding_status']=='out_of_scope'
    assert facts.calculate(chunks,contract('lookup',('Q3',)),cfg)['binding_status']=='missing'
    cfg['sources'][0]['effective_from']='2025-01-01';cfg['sources'][0]['effective_to']='2026-01-01'
    assert facts.calculate(chunks,contract(),cfg,{'as_of':'2024-12-31'})['value'] is None
    cfg['sources'][0].pop('effective_from');cfg['sources'][0].pop('effective_to')
    assert facts.calculate(chunks,contract(),cfg,{'as_of':'2025-06-01'})['value'] is None
    spec=contract();spec['operands'][0]['unit']='euros'
    with pytest.raises(ValueError,match='units differ'):facts.calculate(chunks,spec,cfg)


def test_model_default_remains_separate_and_binding_budget_abstains(tmp_path,monkeypatch):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg);t=task();cfg['settings']['answering_mode']='model'
    calls=[]
    def model(q,ctx,c):
        calls.append(q)
        from sourceroi.live.evidence_contract import abstention
        return abstention({'abstain':True,'reasons':['test model refusal']},c)
    monkeypatch.setattr('sourceroi.live.engine.run_chat',model)
    evaluate_variant(cfg,[t],chunks,[]);assert len(calls)==1
    cfg['settings']['max_context_chars']=5
    selected,trace=select_context(t['question'],chunks,{**cfg,'_calculation_contract':t['calculation_contract']})
    assert selected==[] and trace['budget_fact_abstention']


def test_numeric_citation_binding_is_separate_from_independent_semantics(tmp_path):
    from sourceroi.live.release_policy import inspect
    cfg=setup(tmp_path,{'good.txt':'ExampleCo revenue is 900 dollars for Q1, and 1040 dollars for Q2.',
                        'wrong.txt':'OtherCo expenses is 140 dollars for Q2.'})
    _,chunks=scan_sources(cfg);t=task();good=next(c for c in chunks if c['document_id'].endswith('good.txt'));bad=next(c for c in chunks if c['document_id'].endswith('wrong.txt'))
    row={'actual':'140','raw_answer':140,'retrieved_chunk_ids':[c['id'] for c in chunks],'citations':[bad['id']],
         'answer_contract_valid':True,'json_format_valid':True}
    judged=inspect(t,row,chunks,cfg,'development',builtin=True)
    assert judged['numeric_evidence_status']=='BLOCK'
    row['citations']=[good['id']]
    judged=inspect(t,row,chunks,cfg,'development',builtin=True)
    assert judged['numeric_evidence_status']=='PASS' and judged['semantic_status']=='REVIEW'
    row['actual']='139'
    assert inspect(t,row,chunks,cfg,'development',builtin=True)['numeric_evidence_status']=='BLOCK'


def test_multi_step_formula_and_values_in_contract_are_rejected():
    spec=contract();spec['operation']='(a-b)/a'
    with pytest.raises(ValueError):facts.validate(spec)
    spec=contract();spec['operands'][0]['value']='1040'
    with pytest.raises(ValueError):facts.validate(spec)


def test_callback_bridge_never_supplies_labels_and_rejects_fake_versions(tmp_path):
    from sourceroi.live.adapter import callback_for
    from sourceroi.live.data_ci import digest
    cfg=setup(tmp_path);docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
    def app(**kwargs):
        assert 'expected' not in kwargs and 'evidence' not in kwargs
        assert set(kwargs)=={'question','task_id','snapshot_root','knowledge_manifest','scope','contracts'}
        return {'answer':140,'citations':[chunks[0]['id']],'retrieved_chunk_ids':[chunks[0]['id']],
                'knowledge_manifest':manifest,'knowledge_version':digest(manifest),'response_complete':True}
    t={k:v for k,v in task().items() if k not in ('expected','scoring','category')}
    row=callback_for(app)(cfg,[t])['tasks'][0]
    assert row['answer']=='140' and row['prompt_tokens'] is None
    def wrong(**kwargs):return {**app(**kwargs),'knowledge_version':'stale'}
    with pytest.raises(ValueError,match='manifest/version'):callback_for(wrong)(cfg,[t])


def test_comparison_answer_type_and_missing_evidence_diagnostics(tmp_path):
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg)
    t=task(contract('greater_than',('Q2','Q1')));t['answer_contract']={'version':1,'type':'boolean'};t['expected']='true';t['scoring']='exact'
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert row['actual']=='true' and row['correct']
    t['answer_contract']={'version':1,'type':'numeric'}
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert row['actual']=='INSUFFICIENT_EVIDENCE' and row['grounding_precheck']['abstain']
    t=task(contract('lookup',('Q3',)));t['evidence_contract']={'version':1,'subject_aliases':[['ExampleCo']]}
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    assert row['actual']=='INSUFFICIENT_EVIDENCE' and row['calculation']['binding_status']=='missing'


def test_calculation_failure_is_not_misdiagnosed_as_model_failure(tmp_path):
    from sourceroi.live.diagnosis import diagnose
    cfg=setup(tmp_path);_,chunks=scan_sources(cfg);t=task();t['expected']='999'
    row=evaluate_variant(cfg,[t],chunks,[])['tasks'][0]
    result=diagnose(t,row,chunks,cfg)
    assert result['classification']=='calculation_or_label_mismatch'
    assert result['model_generation_executed'] is False


def test_external_release_cli_runs_existing_callback_without_invented_reviews(tmp_path,monkeypatch):
    import types,sys
    from examples.knowledge_change.demo import workspace
    from sourceroi.live.config import read_config
    from sourceroi.live.data_ci import freeze,digest
    from sourceroi.live import assurance as a
    from tools.check_external_release import main
    source=workspace(tmp_path/'original');freeze(source,tmp_path/'accepted')
    before=read_config(tmp_path/'accepted');after=workspace(tmp_path/'candidate',days=14)
    spec=a.propose(before,after)
    approval=a.review(spec,reviewer='synthetic development fixture operator',rationale='Authored fixture, no human approval',
        expected_changes={'returns':'14'},protected_tasks=['warranty'],
        expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    mod=types.ModuleType('synthetic_existing_app')
    def application(**kwargs):
        cfg=read_config(kwargs['snapshot_root']);docs,chunks=scan_sources(cfg)
        key=kwargs['question'].split()[-1].rstrip('?');match=next(c for c in chunks if key in json.loads(c['text']))
        manifest={d['id']:d['fingerprint'] for d in docs}
        return {'answer':str(json.loads(match['text'])[key]),'citations':[match['id']],'retrieved_chunk_ids':[match['id']],
                'knowledge_manifest':manifest,'knowledge_version':digest(manifest),'response_complete':True}
    mod.answer=application;monkeypatch.setitem(sys.modules,mod.__name__,mod)
    for name,data in [('spec',spec),('approval',approval)]: (tmp_path/(name+'.json')).write_text(json.dumps(data))
    output=tmp_path/'release.json'
    argv=['--authorize-execution','--baseline',before['_root'],'--candidate',after['_root'],'--spec',str(tmp_path/'spec.json'),
          '--approval',str(tmp_path/'approval.json'),'--adapter','synthetic_existing_app:answer','--output',str(output)]
    assert main(argv)==a.EXIT_CODES['REVIEW']
    result=json.loads(output.read_text())
    assert result['check_statuses']['exact_answer']=='PASS' and result['check_statuses']['semantic_review']=='REVIEW'
    assert output.with_suffix('.md').exists()
    with pytest.raises(SystemExit):main(argv)


def test_regression_fixture_blocks_real_model_socket():
    import socket
    with socket.socket() as connection:
        with pytest.raises(OSError,match='Live inference endpoint blocked'):
            connection.connect(('127.0.0.1',8788))
