"""Authored engineering cases, not independent semantic validation."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from sourceroi.live import facts
from sourceroi.live.ingest import scan_sources,extract_document
from sourceroi.live.engine import evaluate_variant


def setup(tmp_path,text,name='data.csv'):
    (tmp_path/'sources').mkdir();(tmp_path/'sources'/name).write_text(text)
    cfg={'_root':str(tmp_path),'id':'table-fixture','model':{'name':'unused','local_only':True,'base_url':'http://127.0.0.1:1/v1'},
         'sources':[{'id':'data','path':'sources','jurisdiction':'US','policy_scope':'fixture','authority':'synthetic fixture'}],
         'settings':{'table_evidence':True,'chunk_strategy':'sentences','chunk_chars':1100,'answering_mode':'source_calculation',
                     'calculation_reviewers':['fixture-author'],'retrieval_policy':{'name':'predicate'}}}
    return cfg


def contract(subject='Orion',predicate='revenue',unit='USD',period='FY2025'):
    return {'version':1,'operation':'lookup','operands':[{'subject':subject,'predicate':predicate,'unit':unit,'period':period}]}


def test_long_csv_exact_cell_and_source_provenance(tmp_path):
    text='company,attribute,period,value,unit\nOrion,revenue,FY2024,1200,USD\nOrion,revenue,FY2025,"1,350",USD\n'
    cfg=setup(tmp_path,text);docs,chunks=scan_sources(cfg);result=facts.calculate(chunks,contract(),cfg)
    assert result['value']=='1350'
    fact=result['operands'][0]['facts'][0]
    assert text[fact['quote_start']:fact['quote_end']]==fact['quote']
    for cell in fact['cells']:assert text[cell['start']:cell['end']]==cell['quote']
    assert fact['source_version']==docs[0]['fingerprint']
    assert any(c['role']=='value' and c['quote']=='"1,350"' for c in fact['cells'])
    assert result['semantic_approval'] is None


def test_markdown_product_header_unit_and_non_table_text(tmp_path):
    text='A preamble.\n\n| Plan | Period | Price USD |\n|---|---|---|\n| Pro | Q2 | 24 |\n\nA closing statement.'
    cfg=setup(tmp_path,text,'pricing.md');_,chunks=scan_sources(cfg)
    result=facts.calculate(chunks,contract('Plan Pro','price','USD','Q2'),cfg)
    assert result['value']=='24'
    assert len([c for c in chunks if c['chunk_strategy']=='table'])==1
    assert any('preamble' in c['text'] for c in chunks if c['chunk_strategy']!='table')


def test_wide_historical_periods_and_comparison(tmp_path):
    cfg=setup(tmp_path,'company,attribute,unit,FY2024,FY2025\nOrion,revenue,USD,1200,1350\n')
    _,chunks=scan_sources(cfg);spec=contract();spec['operation']='subtract';spec['operands'].append({**spec['operands'][0],'period':'FY2024'})
    assert facts.calculate(chunks,spec,cfg)['value']=='150'


@pytest.mark.parametrize('text',[
 'company,attribute,period,value,unit\nOrion,revenue,FY2025,,USD\n',
 'company,attribute,period,value,value,unit\nOrion,revenue,FY2025,12,13,USD\n',
 'company,entity,attribute,period,value,unit\nOrion,Orion,revenue,FY2025,12,USD\n',
 'company,attribute,period,value,unit\nOrion,revenue,FY2025,12\n',
 'company,attribute,period,value,unit,condition\nOrion,revenue,FY2025,12,USD,if eligible\n',
 'company,attribute,period,value,unit\nOrion,revenue,FY2025,12 or 13,USD\n',
])
def test_ambiguous_missing_and_conditional_cells_refuse(tmp_path,text):
    cfg=setup(tmp_path,text);_,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(),cfg)['value'] is None


def test_conflicting_rows_and_wrong_units_are_preserved(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\nOrion,revenue,FY2025,13,USD\n')
    _,chunks=scan_sources(cfg);result=facts.calculate(chunks,contract(),cfg)
    assert result['binding_status']=='conflict' and len(result['operands'][0]['facts'])==2
    assert facts.calculate(chunks,contract(unit='EUR'),cfg)['value'] is None
    assert facts.calculate(chunks,contract(subject='OtherCo'),cfg)['value'] is None
    assert facts.calculate(chunks,contract(period='FY2027'),cfg)['value'] is None


def test_table_metadata_tamper_and_applicability(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\n')
    _,chunks=scan_sources(cfg);tampered=deepcopy(chunks);tampered[0]['table']['rows'][0][3]['text']='99'
    assert facts.calculate(tampered,contract(),cfg)['binding_status']=='invalid_provenance'
    assert facts.calculate(chunks,contract(),cfg,{'jurisdiction':'CA'})['value'] is None
    cfg['sources'][0].update(effective_from='2025-01-01',effective_to='2026-01-01')
    assert facts.calculate(chunks,contract(),cfg,{'as_of':'2024-01-01'})['value'] is None


def test_old_csv_fingerprints_remain_opt_in(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\n')
    raw=scan_sources(cfg)[0][0]['fingerprint'];cfg['settings'].pop('table_evidence')
    assert scan_sources(cfg)[0][0]['fingerprint']!=raw
    assert all(c['chunk_strategy']=='sentences' for c in scan_sources(cfg)[1])


def test_markdown_split_subject_works_through_engine_and_keeps_review(tmp_path):
    from sourceroi.live.release_policy import inspect
    cfg=setup(tmp_path,'| Plan | Period | Price USD |\n|---|---|---|\n| Pro | Q2 | 24 |\n','price.md')
    spec=contract('Plan Pro','price','USD','Q2');scope={'jurisdiction':'US','policy_scope':'fixture'};q='Price for Plan Pro in Q2?'
    task={'id':'price','question':q,'expected':'24','scoring':'numeric','category':'synthetic','scope':scope,'requires_grounding':True,
          'answer_contract':{'version':1,'type':'numeric'},'evidence_contract':{'version':1,'subject_aliases':[['Plan Pro']]},
          'calculation_contract':spec,'calculation_authorization':facts.authorize(q,scope,spec,reviewer='fixture-author',rationale='Synthetic task contract only')}
    _,chunks=scan_sources(cfg);row=evaluate_variant(cfg,[task],chunks,[])['tasks'][0]
    assert row['actual']=='24' and row['correct']
    judged=inspect(task,row,chunks,cfg,'test-version',builtin=True)
    assert judged['numeric_evidence_status']=='PASS' and judged['relevance_status']=='REVIEW' and judged['semantic_status']=='REVIEW'


def test_quoted_csv_and_escaped_markdown_entities(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\n"Orion, Inc",revenue,FY2025,"1,350",USD\n')
    _,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(subject='Orion, Inc'),cfg)['value']=='1350'


def test_unrelated_malformed_table_cannot_supply_or_replace_target_fact(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\n')
    (tmp_path/'sources/other.csv').write_text('unrelated,broken,headers\nOtherCo,99,foo\n')
    _,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(),cfg)['value']=='12'


def test_table_facts_follow_intent_data_ci_and_strict_release(tmp_path):
    from sourceroi.live.config import read_config
    from sourceroi.live.data_ci import freeze,run_data_ci
    from sourceroi.live import assurance as a
    import shutil
    source=tmp_path/'source';source.mkdir();cfg=setup(source,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\n')
    spec=contract();q='Orion revenue FY2025?';scope={'jurisdiction':'US','policy_scope':'fixture'}
    task={'id':'revenue','question':q,'expected':'12','scoring':'numeric','requires_grounding':True,'scope':scope,
          'answer_contract':{'version':1,'type':'numeric'},'calculation_contract':spec,
          'calculation_authorization':facts.authorize(q,scope,spec,reviewer='fixture-author',rationale='Synthetic operation only'),
          'evidence':[{'document_id':'data::data.csv','quote':'Orion,revenue,FY2025,12,USD'}]}
    cfg['settings'].update(max_model_calls_per_run=8,max_run_seconds=30,release_policy='strict_grounded')
    (source/'project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}));(source/'benchmark.jsonl').write_text(json.dumps(task)+'\n')
    freeze(read_config(source),tmp_path/'accepted');shutil.copytree(source,tmp_path/'candidate')
    (tmp_path/'candidate/sources/data.csv').write_text('company,attribute,period,value,unit\nOrion,revenue,FY2025,14,USD\n')
    before=read_config(tmp_path/'accepted');after=read_config(tmp_path/'candidate');plan=a.propose(before,after)
    review=a.review(plan,reviewer='synthetic fixture reviewer',rationale='Known authored source change, not human validation',expected_changes={'revenue':'14'},
        expected_evidence={'revenue':[{'document_id':'data::data.csv','quote':'Orion,revenue,FY2025,14,USD'}]})
    release=a.execute(before,after,plan,approval=review,max_calls=2,policy='strict_grounded')
    assert release['verdict']=='REVIEW' and release['check_statuses']['exact_answer']=='PASS'
    assert release['check_statuses']['numeric_evidence']=='PASS' and release['check_statuses']['semantic_review']=='REVIEW'
    assert release['execution']['model_generation_calls']==0
    assert run_data_ci(before,after,max_tasks=1)['verdict']=='blocked'


def test_csv_preserves_crlf_unicode_and_byte_fingerprint(tmp_path):
    import hashlib
    text='company,attribute,period,value,unit\r\nOríon,revenue,FY2025,12,USD\r\n'
    cfg=setup(tmp_path,text);raw=('\ufeff'+text).encode('utf-8');(tmp_path/'sources/data.csv').write_bytes(raw)
    _,chunks=scan_sources(cfg);fact=facts.calculate(chunks,contract(subject='Oríon'),cfg)['operands'][0]['facts'][0]
    assert fact['raw_source_sha256']==hashlib.sha256(raw).hexdigest()
    for cell in fact['cells']:assert text[cell['start']:cell['end']]==cell['quote']


def test_missing_subject_or_attribute_cannot_hide_competing_row(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\nOrion,revenue,FY2025,12,USD\n,revenue,FY2025,13,USD\n')
    _,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(),cfg)['value'] is None


def test_surrounding_eligibility_qualification_requires_review(tmp_path):
    cfg=setup(tmp_path,'Only permanent staff may use this table.\n\n| Plan | Period | Price USD |\n|---|---|---|\n| Pro | Q2 | 24 |\n','price.md')
    _,chunks=scan_sources(cfg)
    result=facts.calculate(chunks,contract('Plan Pro','price','USD','Q2'),cfg)
    assert result['value'] is None and result['binding_status']=='ambiguous'


def test_oversized_table_is_not_sent_to_model_or_partially_selected(tmp_path):
    from sourceroi.live.policies import select_context
    cfg=setup(tmp_path,'company,attribute,period,value,unit\n'+''.join(f'Orion,revenue,FY{2000+i},12,USD\n' for i in range(20)))
    cfg['settings']['chunk_chars']=250;cfg['settings']['retrieval_policy']={'name':'original'}
    _,chunks=scan_sources(cfg);selected,trace=select_context('Orion revenue FY2025?',chunks,cfg)
    assert selected==[] and trace['excluded_oversized_table_ids']==[chunks[0]['id']]


def test_multiline_csv_and_escaped_markdown_keep_original_cells(tmp_path):
    cfg=setup(tmp_path,'company,attribute,period,value,unit\n"Orion\nSubsidiary",revenue,FY2025,12,USD\n')
    markdown='| Product | Period | Price USD |\n|---|---|---|\n| Pro\\|Enterprise | Q2 | 24 |\n'
    (tmp_path/'sources/pricing.md').write_text(markdown)
    _,chunks=scan_sources(cfg)
    assert facts.calculate(chunks,contract(subject='Orion Subsidiary'),cfg)['value']=='12'
    result=facts.calculate(chunks,contract('Product Pro|Enterprise','price','USD','Q2'),cfg)
    assert result['value']=='24'
    for cell in result['operands'][0]['facts'][0]['cells']:
        assert markdown[cell['start']:cell['end']]==cell['quote']
