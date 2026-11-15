"""Small, explicit local-only plan for evidence selection and fallback validation."""
from copy import deepcopy
import hashlib
import csv
import json
from pathlib import Path
import statistics
import time

from . import db
from .config import read_config
from .datasets import verify_public_snapshot
from .engine import evaluate_variant, compare_variants, _objective_score
from .ingest import load_benchmark,scan_sources
from .validation import Budget,split_tasks
from .provider import count_context_tokens
from .uncertainty import objective_interval
from .diagnosis import diagnose


def choices(cfg, previous):
    k=cfg.get('settings',{}).get('max_chunks',5)
    return [('original',{'name':'original'})]+[
        ('top_k',{'name':'top_k','k':n}) for n in (2,k)]+[
        ('threshold',{'name':'threshold','ratio':r}) for r in (.25,.5)]+[
        ('context_budget',{'name':'context_budget','chars':n}) for n in (2000,6000)]+[
        ('simple_task_aware',{'name':'simple_strong','k':k,'lookup_k':n}) for n in (2,k)]+[
        ('previous_optimizer',previous)]+[
        ('evidence_aware',{'name':'evidence_aware','k':k,'coverage_floor':r,'max_context_tokens':2500}) for r in (.5,.8)]+[
        ('evidence_with_fallback',{'name':'evidence_aware','k':k,'coverage_floor':r,'fallback':True,'max_context_tokens':2500}) for r in (.5,.8)]


def run_reliability_study(cfg, previous, *, budget=None, notify=None):
    if not cfg.get('model',{}).get('local_only') or cfg['model'].get('runtime')!='llama_cpp' or cfg['model'].get('context_tokenizer')!='llama_cpp':
        raise ValueError('Reliability evaluation requires the approved local llama.cpp model')
    cfg=deepcopy(cfg)
    tasks=load_benchmark(cfg);dev,held=split_tasks(tasks);docs,chunks=scan_sources(cfg)
    verify_public_snapshot(cfg,docs)
    options=choices(cfg,previous); families=sorted({name for name,_ in options})
    required=len(dev)*len(options)+len(held)*len(families)
    budget=budget or Budget(cfg['settings'])
    if budget.calls+required>budget.limit:raise ValueError('Reliability study exceeds shared call cap before inference')
    calls_at_start=budget.calls
    report={'kind':'reliability_study','version':1,'status':'running','measurement_kind':'local_generation',
        'external_api_spend_usd':0,'groundedness_review':'pending','calls_planned':required,
        'benchmark_sha256':hashlib.sha256(json.dumps(tasks,sort_keys=True).encode()).hexdigest(),
        'corpus_sha256':{d['id']:d['fingerprint'] for d in docs},'model':cfg['model'],
        'partitions':{'development':[t['id'] for t in dev],'heldout':[t['id'] for t in held]},
        'experiment_plan':options,'frozen_policies':{},'experiments':[],'review_items':[],
        'quality_rule':'Zero newly failed tasks relative to original; diagnostic relative preservation, not deployment-grade absolute accuracy.',
        'limits':{'max_calls':budget.limit,'max_seconds':budget.max_seconds,'model_slots':1,'context_size':4096}}
    rid=db.begin(cfg,'reliability_study',[]); started=time.perf_counter(); pending=[]
    def execute(name,partition,selected,policy):
        local=deepcopy(cfg);local['settings']['retrieval_policy']=policy
        local['_experiment_budget']=budget;local['_review_items']=pending;local['_partial_tasks']=[]
        local['_context_token_counter']=lambda ctx: count_context_tokens(ctx,local)
        entry={'name':name,'partition':partition,'policy':policy,'partial_tasks':local['_partial_tasks']}
        report['experiments'].append(entry)
        if notify:notify({'event':'configuration_started','name':name,'partition':partition,'calls':budget.calls})
        variant=evaluate_variant(local,selected,chunks,[]);entry['variant']=variant;entry.pop('partial_tasks')
        db.checkpoint(cfg,rid,report)
        return entry
    def eligible(entry,baseline):
        return not compare_variants(baseline['variant'],entry['variant'])['lost_tasks']
    def score(entry):return _objective_score(entry['variant']['metrics'],'token_budget')
    try:
        evaluated=[execute(n,'development',dev,p) for n,p in options]; original=evaluated[0]
        report['development_selection_status']={}
        for family in families:
            entries=[e for e in evaluated if e['name']==family];valid=[e for e in entries if eligible(e,original)]
            chosen=min(valid,key=score) if valid else min(entries,key=lambda e:(-e['variant']['metrics']['accuracy'],len(compare_variants(original['variant'],e['variant'])['lost_tasks']),score(e)))
            report['frozen_policies'][family]=chosen['policy']
            report['development_selection_status'][family]='qualified' if valid else 'infeasible_quality_first_diagnostic'
        report['frozen_policy_sha256']=hashlib.sha256(json.dumps(report['frozen_policies'],sort_keys=True).encode()).hexdigest()
        final={n:execute(n,'heldout',held,report['frozen_policies'][n]) for n in families}
        baseline=final['original']['variant']
        report['comparisons']={n:compare_variants(baseline,e['variant']) for n,e in final.items()}
        report['objective_ci95']={n:objective_interval({'runs':[baseline]},{'runs':[e['variant']]},held,'token_budget') for n,e in final.items()}
        report['quality_pass']={n:not c['lost_tasks'] for n,c in report['comparisons'].items()}
        report['diagnostics']={n:[diagnose(t,next(r for r in e['variant']['tasks'] if r['id']==t['id']),chunks,cfg)
            for t in held if t['id'] in report['comparisons'][n]['lost_tasks']] for n,e in final.items()}
        simple=('top_k','threshold','context_budget','simple_task_aware')
        report['benefit_over_qualified_simple']={}
        for n in ('previous_optimizer','evidence_aware','evidence_with_fallback'):
            c=final[n]['variant']; gains=[]
            for s in simple:
                base=final[s]['variant']
                if report['development_selection_status'][s]=='qualified' and report['quality_pass'][s] and not compare_variants(base,c)['lost_tasks'] and c['metrics']['total_tokens']<base['metrics']['total_tokens']:
                    gains.append(s)
            report['benefit_over_qualified_simple'][n]=gains if report['quality_pass'][n] else []
        report['verdict']='Inconclusive / insufficient evidence' if report['quality_pass']['evidence_with_fallback'] else 'Rejected due to quality regression'
        report['limitation']='Heuristic sufficiency and tiny grouped samples do not prove safety. Claim-level groundedness remains pending; no production change is authorized.'
        report['review_items']=list({i['key']:i for i in pending}.values())
        report.update(status='completed',run_id=rid,generation_calls=budget.calls-calls_at_start,session_calls=budget.calls,elapsed_ms=round((time.perf_counter()-started)*1000,2))
        db.finish(cfg,rid,report);return report
    except Exception as exc:
        report.update(status='incomplete',verdict='inconclusive',error_type=type(exc).__name__,generation_calls=budget.calls-calls_at_start,session_calls=budget.calls)
        report['review_items']=list({i['key']:i for i in pending}.values())
        db.finish(cfg,rid,report,type(exc).__name__);raise


def export_reliability(report,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if report.get('status')!='completed':
        return
    rows=['# Reliability-first local comparison','',report.get('verdict','incomplete'),'',
          '| Policy | Correct | Prompt | Output | Total | Context | Mean ms | Median ms | p95 ms | Fallback | New losses |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for e in report['experiments']:
        if e['partition']=='heldout' and e.get('variant'):
            m=e['variant']['metrics'];c=report['comparisons'][e['name']]
            rows.append(f"| {e['name']} | {m['passed']}/{m['task_count']} | {m['input_tokens']} | {m['output_tokens']} | {m['total_tokens']} | {m['context_tokens']} | {m['mean_latency_ms']} | {m['median_latency_ms']} | {m['p95_latency_ms']} | {m['fallback_rate']:.2f} | {len(c['lost_tasks'])} |")
    with path.with_suffix('.csv').open('w',newline='') as output:
        fields=['policy','partition','accuracy','input_tokens','output_tokens','total_tokens','context_tokens','median_latency_ms','p95_latency_ms','fallback_rate','selection_check_ms']
        writer=csv.DictWriter(output,fields);writer.writeheader()
        for entry in report['experiments']:
            if entry.get('variant'):
                metrics=entry['variant']['metrics']
                writer.writerow({'policy':entry['name'],'partition':entry['partition'],**{k:metrics.get(k) for k in fields[2:]}})
    path.with_suffix('.md').write_text('\n'.join(rows)+'\n')
    path.with_suffix('.review.json').write_text(json.dumps({'version':1,'items':report['review_items']},indent=2)+'\n')
