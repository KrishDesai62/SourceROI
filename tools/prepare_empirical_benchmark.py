"""Freeze authentic annual IRS notices and development expectations, no inference.

Previously exposed public corpus; Codex labels, never independent/held-out truth.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import extract_document
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.assurance import propose
ROOT=Path(__file__).resolve().parents[1]


def prepare(output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Benchmark destination exists; never refreeze exposed outputs')
    provenance=json.loads((ROOT/'workspace/irs-e2e/raw/provenance.json').read_text())
    for item in provenance['sources']:
        for key,hashkey in [('local_pdf','pdf_sha256'),('local_text','text_sha256')]:
            if hashlib.sha256((ROOT/item[key]).read_bytes()).hexdigest()!=item[hashkey]:raise ValueError('Historical authoritative source hash mismatch')
    output.mkdir(parents=True)
    annotations=[]
    specs=[
        ('business','What is the business standard mileage rate in the CURRENT annual notice, in cents per mile?', '67','70','changed',r'The standard mileage rate for transportation or travel expenses(?: for 2025)? is (?:67|70)\s+cents per\s+mile', ['business']),
        ('medical','What is the medical care mileage rate in the CURRENT annual notice, in cents per mile?','21','21','protected',r'The standard mileage rate(?: for 2025 is unchanged from 2024 at| is) 21 cents per mile[\s\S]{0,95}?medical care described in § 213', ['medical']),
        ('charity','What is the charitable organization mileage rate in the CURRENT annual notice, in cents per mile?','14','14','protected',r'The standard mileage rate is 14 cents per mile[\s\S]{0,100}?charitable organization under § 170', ['charitable']),
        ('favr','What maximum automobile cost in US dollars does the CURRENT annual notice set for a FAVR plan?','62000','61200','changed',r'For purposes of computing the allowance under a FAVR plan,[\s\S]{0,170}?\$6[12],[02]00[\s\S]{0,65}?vans\)\.', ['FAVR']),
        ('depreciation','What cents-per-mile depreciation basis reduction does the CURRENT annual notice prescribe for its own publication year?','30','33','changed',r'For automobiles a taxpayer uses for business purposes,[\s\S]{0,520}?cents per mile for 202[45]\.', ['depreciation']),
        ('parking','What flat daily overnight parking deduction in dollars does this collection specify?','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE','unsupported',None,['parking']),
        ('canada','What Canadian business standard mileage rate does this collection authorize in cents per mile?','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE','jurisdiction',None,['business']),
        ('future','What business mileage rate in cents per mile does this collection prescribe specifically for calendar year 2030?','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE','future_scope',None,['business']),
        ('past','What business mileage rate in cents per mile does this collection prescribe specifically for calendar year 2020?','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE','past_scope',None,['business']),
        ('cross_version','Do both the 2024 and 2025 notices support one identical business mileage rate? Return that single cents-per-mile value only if they do, otherwise INSUFFICIENT_EVIDENCE.','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE','cross_version_conflict',None,['business']),
    ]
    texts={}
    for name,year in [('source',2024),('candidate',2025)]:
        root=output/name;(root/'sources/current').mkdir(parents=True);(root/'sources/archive').mkdir(parents=True)
        shutil.copy2(ROOT/f'workspace/irs-e2e/raw/notice-{year}.pdf',root/'sources/current/notice.pdf')
        shutil.copy2(ROOT/'workspace/irs-e2e/raw/notice-2024.pdf',root/'sources/archive/notice.pdf')
        sources=[]
        for sid,edition in [('current',year),('archive',2024)]:
            sources.append({'id':sid,'path':'sources/'+sid,'authority':'United States Internal Revenue Service',
                'jurisdiction':'US','policy_scope':'IRS annual mileage schedule','effective_from':f'{edition}-01-01','effective_to':f'{edition+1}-01-01'})
        cfg={'id':'real-irs-controlled-development','name':'Authentic IRS annual notices, exposed development corpus',
            'runner':'rag_chat','benchmark':'benchmark.jsonl','sources':sources,
            'model':{'name':'qwen2.5-1.5b-instruct-q4_k_m','base_url':'http://127.0.0.1:1/v1','local_only':True,
                'runtime':'llama_cpp','seed':1729,'temperature':0,'max_output_tokens':192,'timeout_seconds':30,'compact_source_ids':True},
            'settings':{'release_policy':'strict_grounded','max_chunks':5,'chunk_chars':1800,'overlap_chars':200,
                'max_context_chars':9000,'max_tasks_per_run':20,'max_model_calls_per_run':20,'max_run_seconds':90}}
        (root/'project.json').write_text(json.dumps(cfg,indent=2))
        # Decode original PDF bytes with the existing ingestion path; no rewritten source facts.
        text=extract_document(root/'sources/current/notice.pdf',cfg);texts[year]=text
        (root/'original-extracted-text.txt').write_text(text)
        tasks=[]
        for tid,question,before,after,kind,pattern,aliases in specs:
            expected=before # original frozen labels; changes belong to reviewed maintenance decisions
            refs=[]
            if pattern:
                match=re.search(pattern,text)
                if match is None:raise ValueError('Exact authoritative evidence absent for '+tid+' '+str(year))
                refs=[{'document_id':'current::notice.pdf','quote':match[0]}]
                annotations.append({'task_id':tid,'version':year,'expected':before if year==2024 else after,
                    'quote':match[0],'quote_start':match.start(),'quote_end':match.end(),'document_text_sha256':hashlib.sha256(text.encode()).hexdigest()})
            scope={} if kind=='cross_version_conflict' else {'jurisdiction':'CA' if kind=='jurisdiction' else 'US','policy_scope':'IRS annual mileage schedule',
                'as_of':'2030-06-01' if kind=='future_scope' else '2020-06-01' if kind=='past_scope' else f'{year}-06-01'}
            # Keep a single frozen question/scope contract on both versions: annual CURRENT
            # selection is evaluated at 2024/2025 via separate registered task scope below.
            scope.pop('as_of',None) if kind not in ('future_scope','past_scope') else None
            tasks.append({'id':tid,'question':question,'expected':expected,'scoring':'numeric' if pattern else 'exact',
                'category':kind,'requires_grounding':True,'answer_contract':{'version':1,'type':'numeric'},
                'evidence_contract':{'version':1,'subject_aliases':[[a] for a in aliases]},'scope':scope,'evidence':refs})
        (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
    # Preserve original labels/evidence byte-for-byte for data-only CI; replacement evidence is reviewed separately.
    shutil.copy2(output/'source/benchmark.jsonl',output/'candidate/benchmark.jsonl')
    freeze(read_config(output/'source'),output/'accepted')
    intent={'expected_tasks':[s[0] for s in specs if s[4]=='changed'],'protected_tasks':[s[0] for s in specs if s[4]!='changed'],
        'declared_by':'Codex development label author; no source owner or independent review',
        'rationale':'Official annual rate changes; preserved protected expectations; exposed IRS development corpus'}
    plan=propose(read_config(output/'accepted'),read_config(output/'candidate'),intent=intent)
    replacements={s[0]:s[3] for s in specs if s[4]=='changed'}
    draft={'reviewer':'Codex development label author, not independent','rationale':'DRAFT: requires actual technical review before execution; no human approval',
        'expected_changes':replacements,'protected_tasks':intent['protected_tasks'],
        'expected_evidence':{a['task_id']:[{'document_id':'current::notice.pdf','quote':a['quote']}] for a in annotations if a['version']==2025 and a['task_id'] in replacements}}
    # Apparent conflict uses authentic editions, never invented contradictory policy.
    conflict=[]
    for year,text in texts.items():
        pattern=specs[0][5];m=re.search(pattern,text)
        conflict.append({'version':year,'quote':m[0],'quote_start':m.start(),'quote_end':m.end(),
            'interpretation':'Different annual applicability; not simultaneous same-period authoritative contradiction'})
    meta={'kind':'FROZEN_CODEX_DEVELOPMENT_BENCHMARK','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'independently_adjudicated':False,'previously_exposed_corpus':True,'authoritative_sources':provenance,
        'source_urls_verified_this_sprint':['https://www.irs.gov/pub/irs-drop/n-24-08.pdf','https://www.irs.gov/pub/irs-drop/n-25-05.pdf'],
        'applicability_window':'Registered annual evaluation windows inferred from notice titles/supersession; not claimed original legal expiration dates',
        'tasks':len(specs),'maximum_paired_generation_attempts_without_retries':2*len(specs),
        'annotations':annotations,'conflicting_cross_version_evidence':conflict,
        'unsupported_rationale':'Parking amount absent; Canada outside US authority; 2020/2030 business rates not established by annual 2024/2025 notices; both annual notices needed for cross-version equality',
        'model_outputs_observed_for_this_benchmark':False,'human_semantic_reviews':None}
    for name,value in [('intent.json',intent),('change-plan.json',plan),('review-decisions-DRAFT.json',draft),('frozen-labels.json',meta)]:
        (output/name).write_text(json.dumps(value,indent=2))
    hashes={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file() and '.sourceroi' not in p.parts}
    (output/'freeze-manifest.json').write_text(json.dumps(hashes,indent=2))
    return {'output':str(output),'tasks':len(specs),'paired_task_executions':20,'generation_calls':0,'labels':'Exposed Codex development only','benchmark_sha256':digest(hashes)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
