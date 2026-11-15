"""Frozen, clearly synthetic non-IRS development cases; zero model calls.

Supported table values are scored as failures when the binder cannot extract them.
Safety refusals are a separate denominator from supported numerical accuracy.
"""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from sourceroi.live import facts
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources
from sourceroi.live.answer_contract import check

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'docs/artifacts/final-hardening';BASE=ROOT/'workspace/final-hardening-numerics'


def declaration(operation,operands):return {'version':1,'operation':operation,'operands':[{'subject':s,'predicate':p,'unit':u,'period':t} for s,p,u,t in operands]}


def cases():
    revenue=lambda period:('Orion','revenue','USD',period)
    docs={'old.txt':'Orion revenue for FY2024 is 1200 USD.','new.txt':'Orion revenue for FY2025 is 1350 USD.'}
    sub=declaration('subtract',[revenue('FY2025'),revenue('FY2024')])
    rows=[]
    def add(id,documents,contract,expected,kind='supported_numeric',**extra):
        rows.append({'id':id,'documents':documents,'contract':contract,'expected':expected,'kind':kind,
                     'question':extra.pop('question','Declared development '+id+'?'),**extra})
    add('financial_lookup',docs,declaration('lookup',[revenue('FY2024')]),'1200')
    add('two_document_financial_difference',docs,sub,'150')
    add('paraphrased_difference',docs,sub,'150',question='By how much did Orion revenue rise from FY2024 to FY2025?')
    add('pricing_lookup',{'price.txt':'Plan Pro price is 24 dollars for Q2.'},declaration('lookup',[('Plan Pro','price','dollars','Q2')]),'24')
    add('multi_product_addition',{'base.txt':'Plan Base price is 10 dollars for Q1.','addon.txt':'Plan Addon price is 4 dollars for Q1.'},
        declaration('add',[('Plan Base','price','dollars','Q1'),('Plan Addon','price','dollars','Q1')]),'14')
    add('pricing_comparison',{'price.txt':'Plan Pro price is 20 dollars for Q1, and 24 dollars for Q2.'},
        declaration('greater_than',[('Plan Pro','price','dollars','Q2'),('Plan Pro','price','dollars','Q1')]),'true',answer_type='boolean')
    add('decimal_difference',{'price.txt':'Plan Pro price is 12.25 dollars for Q1, and 24.5 dollars for Q2.'},
        declaration('subtract',[('Plan Pro','price','dollars','Q2'),('Plan Pro','price','dollars','Q1')]),'12.25')
    add('historical_csv_table',{'history.csv':'company,attribute,period,value,unit\nOrion,revenue,FY2024,1200,USD\nOrion,revenue,FY2025,1350,USD\n'},declaration('lookup',[revenue('FY2025')]),'1350')
    add('pricing_markdown_table',{'prices.md':'| Plan | Period | Price USD |\n|---|---|---|\n| Pro | Q2 | 24 |\n'},declaration('lookup',[('Plan Pro','price','USD','Q2')]),'24')
    add('missing_period',docs,declaration('lookup',[revenue('FY2027')]),'INSUFFICIENT_EVIDENCE','safety')
    add('wrong_units',{'other.txt':'Orion revenue is 1200 EUR for FY2024.'},declaration('lookup',[revenue('FY2024')]),'INSUFFICIENT_EVIDENCE','safety')
    add('conflicting_values',{'a.txt':'Orion revenue is 1200 USD for FY2024.','b.txt':'Orion revenue is 1250 USD for FY2024.'},declaration('lookup',[revenue('FY2024')]),'INSUFFICIENT_EVIDENCE','safety')
    add('jurisdiction_mismatch',docs,sub,'INSUFFICIENT_EVIDENCE','safety',scope={'jurisdiction':'CA','policy_scope':'synthetic'})
    add('expired_source',docs,sub,'INSUFFICIENT_EVIDENCE','safety',metadata={'effective_from':'2024-01-01','effective_to':'2025-01-01'},scope={'jurisdiction':'US','policy_scope':'synthetic','as_of':'2026-01-01'})
    add('irrelevant_numerical_evidence',{'other.txt':'OtherCo profit is 1350 USD for FY2025.'},declaration('lookup',[revenue('FY2025')]),'INSUFFICIENT_EVIDENCE','safety')
    add('conditional_eligibility',{'policy.txt':'Staff reimbursement is 40 USD for FY2025 if permanent.'},declaration('lookup',[('Staff','reimbursement','USD','FY2025')]),'INSUFFICIENT_EVIDENCE','safety')
    add('unknown_requested_jurisdiction',docs,sub,'INSUFFICIENT_EVIDENCE','safety',metadata={'jurisdiction':None})
    invalid=deepcopy(sub);invalid['operation']='(a+b)/c'
    add('unsupported_multistep_formula',docs,invalid,None,'unsupported_contract',expect_validation_error=True)
    add('nonnumeric_eligibility',{'policy.txt':'Permanent staff are eligible for training.'},declaration('eligibility',[('Permanent staff','eligibility','boolean','FY2025')]),None,'unsupported_contract',expect_validation_error=True)
    return rows


def main():
    if BASE.exists() or (ART/'numerical-results.json').exists():raise ValueError('Use a new destination; existing evidence immutable')
    frozen=cases()
    with (ART/'numerical-frozen-cases.json').open('x') as f:json.dump({'created_at':datetime.now(timezone.utc).isoformat(),'labels':'Codex-authored synthetic development cases, not independent semantic truth','cases':frozen},f,indent=2)
    BASE.mkdir();results=[]
    for case in frozen:
        root=BASE/case['id'];(root/'sources').mkdir(parents=True)
        for name,text in case['documents'].items():(root/'sources'/name).write_text(text)
        meta={'jurisdiction':'US','policy_scope':'synthetic','authority':'Explicit synthetic development fixture',**case.get('metadata',{})}
        meta={k:v for k,v in meta.items() if v is not None};scope=case.get('scope',{'jurisdiction':'US','policy_scope':'synthetic'})
        cfg={'id':case['id'].replace('_','-'),'benchmark':'benchmark.jsonl','model':{'name':'not_called','base_url':'http://127.0.0.1:1/v1','local_only':True},
             'settings':{'chunk_strategy':'sentences','answering_mode':'source_calculation','calculation_reviewers':['Codex development author']},
             'sources':[{'id':'fixture','path':'sources',**meta}]}
        (root/'project.json').write_text(json.dumps(cfg));(root/'benchmark.jsonl').write_text('')
        cfg=read_config(root);started=time.perf_counter();_,chunks=scan_sources(cfg);ingestion_ms=(time.perf_counter()-started)*1000
        try:
            approval=facts.authorize(case['question'],scope,case['contract'],reviewer='Codex development author',rationale='Explicit frozen synthetic task operation; no human approval')
            started=time.perf_counter();row=facts.answer(case['question'],chunks,case['contract'],approval,{**cfg,'_answer_contract':{'version':1,'type':case.get('answer_type','numeric')}},scope)
            elapsed=(time.perf_counter()-started)*1000
            result={'id':case['id'],'kind':case['kind'],'expected':case['expected'],'actual':row['answer'],'passed':row['answer']==case['expected'],
                    'binding_status':row['calculation']['binding_status'],'calculation':row['calculation'],'citations':row['citations'],
                    'invalid_citations':[c for c in row['citations'] if c not in {c['id'] for c in chunks}],
                    'false_abstention':case['kind']=='supported_numeric' and row['answer']=='INSUFFICIENT_EVIDENCE',
                    'ingestion_ms':ingestion_ms,'answer_and_source_recheck_ms':elapsed,'model_calls':0,'tokens':0,'independent_semantic_correctness':None}
        except ValueError as exc:
            if not case.get('expect_validation_error'):raise
            result={'id':case['id'],'kind':case['kind'],'passed':True,'status':'unsupported_contract_rejected','reason':str(exc),'model_calls':0,'tokens':0}
        results.append(result)
    supported=[r for r in results if r['kind']=='supported_numeric'];safety=[r for r in results if r['kind']=='safety']
    report={'kind':'deterministic_numerical_generalization','cases':results,'supported_correct':sum(r['passed'] for r in supported),'supported_n':len(supported),
            'supported_false_abstentions':sum(r['false_abstention'] for r in supported),'safety_pass':sum(r['passed'] for r in safety),'safety_n':len(safety),
            'unsupported_contracts_rejected':sum(r['kind']=='unsupported_contract' and r['passed'] for r in results),
            'actual_model_calls':0,'external_spend_usd':0,'independent_semantic_correctness':None,'limitation':'Synthetic development grammar coverage, not external semantic validation; unsupported table formats remain supported-question failures.'}
    with (ART/'numerical-results.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))


if __name__=='__main__':main()
