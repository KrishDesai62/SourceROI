"""Reviewable retrieval-only knowledge decisions. No generation or source mutation.

Literal evidence coverage is not answer correctness. All removal proposals require
review; this module cannot grant semantic, generation or release authority.
"""
from copy import deepcopy
import math
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator
from .data_ci import digest


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)


class Alternative(Strict):
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,47}$')
    corpus: Literal['baseline','candidate']='candidate'
    exclude_sources: list[str]=Field(default_factory=list,max_length=64)
    exclude_documents: list[str]=Field(default_factory=list,max_length=128)
    exclude_passages: list[str]=Field(default_factory=list,max_length=256)
    policy: dict | None=None


class Requirements(Strict):
    min_reference_coverage: float=Field(default=1.0,ge=0,le=1)
    max_reference_regressions: int=Field(default=0,ge=0,le=50)
    protected_tasks: list[str]=Field(default_factory=list,max_length=50)


class DecisionRequest(Strict):
    snapshot_id: str=Field(pattern=r'^[a-f0-9]{32}$')
    alternatives: list[Alternative]=Field(min_length=1,max_length=8)
    requirements: Requirements=Field(default_factory=Requirements)
    intent: dict | None=None
    ablation_run_ids: list[str]=Field(default_factory=list,max_length=8)

    @model_validator(mode='after')
    def unique(self):
        names=[a.name for a in self.alternatives]
        if len(set(names))!=len(names) or 'original' in names:raise ValueError('Alternative names must be unique and cannot be original')
        if any(not isinstance(i,str) or not 1<=len(i)<=64 for i in self.ablation_run_ids) or len(set(self.ablation_run_ids))!=len(self.ablation_run_ids):raise ValueError('Invalid historical ablation run identities')
        return self


def historical_ablations(candidate,baseline,tasks,manifest,ids):
    """Link existing runs only with exact corpus/config/full-benchmark identities.

    Stored endpoint/fixture provenance stays a declaration; never new semantic
    authority. Do not merge historical usage into this run's zero generations.
    """
    from . import db
    result=[]
    for ident in ids:
        row=db.get(candidate,ident);report=row and row.get('report')
        if not report or row['status']!='completed' or report.get('mode') not in ('ablation','document_ablation'):raise ValueError('Historical ablation must be a completed existing run')
        if report.get('manifest')!=manifest or report.get('benchmark_sha256')!=digest(tasks) or report.get('config_hash')!=baseline['_config_hash']:raise ValueError('Historical ablation source/config/benchmark mismatch')
        variants=report.get('variants',[])
        if not variants or len(variants)>65 or variants[0].get('excluded_sources') or variants[0].get('excluded_documents'):raise ValueError('Historical ablation lacks a bounded full baseline')
        if any({r['id'] for r in v.get('tasks',[])}!={t['id'] for t in tasks} or len(v.get('tasks',[]))!=len(tasks) for v in variants):raise ValueError('Historical ablation does not cover the same frozen full evaluation set')
        for variant in variants:
            metrics=variant.get('metrics',{})
            if any(type(r.get('correct')) is not bool for r in variant['tasks']) or any(type(metrics.get(k)) not in (int,float) or not math.isfinite(metrics[k]) for k in ('accuracy','mean_latency_ms')) or not 0<=metrics['accuracy']<=1 or metrics['mean_latency_ms']<0:
                raise ValueError('Historical ablation lacks valid observed task/quality/latency metrics')
            cost=metrics.get('total_cost_usd')
            if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0):raise ValueError('Invalid historical cost; missing cost must remain null')
        from .analysis_boundary import call
        result.append({'run_id':ident,'report_hash':digest(report),'measurement_kind':report.get('measurement_kind','UNKNOWN'),
            'comparisons':call('knowledge_history',variants=variants),
            'reported_usage':[{k:v.get('metrics',{}).get(k) for k in ('provider_reported_prompt_tokens','provider_reported_completion_tokens','total_tokens','context_tokens','total_cost_usd','cost_type')} for v in variants],
            'authority':'Historical stored observations only; not newly executed or independently authenticated semantic evidence'})
    return result


def measure_worker(p):
    """Fixed worker operation. Retrieval receives questions/config, never labels."""
    from .policies import select_context
    from .routing import restrict
    from .evidence_contract import precheck
    from .data_ci import evidence_coverage
    results=[]
    for alternative in p['alternatives']:
        side=p[alternative['corpus']];cfg=deepcopy(side['cfg']);pool=side['chunks']
        for field,key in (('source_id','exclude_sources'),('document_id','exclude_documents'),('id','exclude_passages')):
            disabled=set(alternative[key]);pool=[c for c in pool if c[field] not in disabled]
        if alternative['policy'] is not None:cfg.setdefault('settings',{})['retrieval_policy']=alternative['policy']
        rows=[]
        for task in p['tasks']:
            candidates,routing=restrict(task['question'],pool,cfg)
            candidates,_=precheck(task['question'],candidates,cfg,None,task.get('scope'))
            selected,selection=select_context(task['question'],candidates,{**cfg,'_calculation_contract':task.get('calculation_contract'),'_task_scope':task.get('scope')})
            _,screen=precheck(task['question'],selected,cfg,task.get('evidence_contract'),task.get('scope'))
            ids=[c['id'] for c in selected]
            coverage=evidence_coverage(task,{'retrieved_chunk_ids':ids},selected)
            version_mismatches=[e['document_id'] for e in task.get('evidence',[]) if e.get('document_version') is not None and side['manifest'].get(e['document_id'])!=e['document_version']]
            if version_mismatches:
                valid=[e for e in task['evidence'] if e['document_id'] not in version_mismatches]
                coverage=sum(any(c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in selected) for e in valid)/len(task['evidence'])
            rows.append({'task_id':task['id'],'retrieved_chunk_ids':ids,'reference_coverage':coverage,
                'context_characters':sum(len(c['text']) for c in selected),
                'estimated_context_tokens':sum(math.ceil(len(c['text'])/4) for c in selected),
                'potential_conflicts':screen['potential_conflicts'],'unknown_applicability_ids':screen['unknown_applicability_ids'],
                'reference_version_mismatches':sorted(set(version_mismatches)),
                'evidence_screen_abstain':screen['abstain'],'selection':selection,'routing':routing})
        results.append({'name':alternative['name'],'corpus':alternative['corpus'],'tasks':rows})
    return results


def conventional(rows, baseline, requirements, protected):
    """Equally maintained ordinary quote/citation-identity/version/scope checks.

    No answer tests are possible without generated answers. Unknown references
    remain unknown. Both workflows use these same observations and authority.
    """
    before={r['task_id']:r for r in baseline};losses=[];failed=[];unknown=[]
    for row in rows:
        ident=row['task_id'];coverage=row['reference_coverage'];old=before[ident]['reference_coverage']
        if coverage is None:unknown.append(ident)
        elif coverage<requirements.min_reference_coverage or row['reference_version_mismatches']:failed.append(ident)
        if coverage is not None and old is not None and coverage<old:losses.append(ident)
        if row['unknown_applicability_ids']:unknown.append(ident)
        if row['potential_conflicts'] or row['evidence_screen_abstain']:unknown.append(ident)
    protected_loss=sorted(set(losses)&protected)
    verdict='BLOCK' if failed or protected_loss or len(losses)>requirements.max_reference_regressions else 'INCONCLUSIVE' if any(r['reference_coverage'] is None for r in rows) else 'REVIEW'
    return {'verdict':verdict,'failed_reference_tasks':sorted(failed),'reference_regressions':sorted(losses),
        'protected_reference_regressions':protected_loss,'uncertain_tasks':sorted(set(unknown)),
        'reason':'Evidence-only results cannot establish answer quality or authorize release'}


def binary_metrics(predicted, actual, universe):
    if actual is None:return {'precision':None,'recall':None,'false_alarms':None,'missed':None,'label_status':'UNKNOWN'}
    actual=set(actual);predicted=set(predicted)
    if not actual<=set(universe):raise ValueError('Impact labels contain unknown task identities')
    tp=len(actual&predicted)
    return {'precision':tp/len(predicted) if predicted else None,'recall':tp/len(actual) if actual else None,
        'false_alarms':sorted(predicted-actual),'missed':sorted(actual-predicted),'label_status':'supplied_development_labels_not_independent'}


def _recommendations(entities,alternatives,experiments,original,protected,changes,conflicts):
    """Entity intervention observations; never add single-source contributions."""
    rows=[];base={r['task_id']:r for r in original}
    for entity in entities:
        field={'source':'exclude_sources','document':'exclude_documents','passage':'exclude_passages'}[entity['level']]
        observations=[]
        for alternative,experiment in zip(alternatives,experiments):
            if alternative['corpus']!='baseline':continue
            all_exclusions=sum(len(alternative[k]) for k in ('exclude_sources','exclude_documents','exclude_passages'))
            if entity['id'] not in alternative[field]:continue
            observations.append({'experiment':experiment['name'],'joint_intervention':all_exclusions>1,
                'lost_reference_tasks':experiment['conventional']['reference_regressions'],
                'uncertain_tasks':experiment['conventional']['uncertain_tasks'],
                'delta_estimated_context_tokens':experiment['delta_estimated_context_tokens'],
                'quality_impact':'UNKNOWN; literal-reference difference only','verdict':experiment['verdict']})
        single=[o for o in observations if not o['joint_intervention']]
        protected_loss=any(set(o['lost_reference_tasks'])&protected for o in single)
        changed=any(d in changes for d in entity['document_ids'])
        conflict=any(d in conflicts for d in entity['document_ids'])
        if protected_loss:action='KEEP';reason='Direct individual ablation loses registered protected evidence'
        elif conflict:action='REVIEW';reason='Potential conflicting evidence; no safe removal inferred'
        elif changed:action='UPDATE';reason='Verified version difference requires reviewed replacement; not proof the newer text is correct'
        elif single and all(o['verdict']=='REVIEW' and not o['lost_reference_tasks'] and not o['uncertain_tasks'] for o in single) and all(r['reference_coverage']==1 for r in original):action='REMOVE';reason='Potential redundancy under tested individual intervention only; answer quality and combined removal unverified'
        else:action='REVIEW';reason='Insufficient direct ablation/reference coverage to justify a change'
        exposed={r['task_id'] for r in original if any(c['id']==entity['id'] if entity['level']=='passage' else c['document_id'] in entity['document_ids'] for c in r['retrieved_evidence'])}
        rows.append({**entity,'recommendation':action,'reason':reason,'observations':observations,
            'affected_tasks':sorted({t for o in observations for t in o['lost_reference_tasks']}|set(entity['referenced_tasks'])|exposed),
            'observed_retrieval_tasks':sorted(exposed),
            'estimated_answer_quality_impact':None,'estimated_monetary_impact_usd':None,
            'uncertainty':'Development evidence only; exact quotes do not prove semantic adequacy',
            'automatically_applied':False,'review_required':True})
    return rows


def run(baseline,candidate,request: DecisionRequest | dict,*,persist=True):
    from . import assurance,db
    from .ingest import scan_sources,load_benchmark
    from .analysis_boundary import call,public
    from .policies import validate_policy
    from .workspace_lock import workspace_lock
    request=DecisionRequest.model_validate(request) if isinstance(request,dict) else request
    if not isinstance(request,DecisionRequest):raise ValueError('Typed decision request required')
    if Path(baseline['_root']).name!=request.snapshot_id:raise ValueError('Snapshot request identity does not match frozen baseline')
    started=time.perf_counter()
    with workspace_lock(candidate['_root']):
        tasks=load_benchmark(baseline)
        if not 1<=len(tasks)<=50:raise ValueError('Offline decision supports 1..50 frozen tasks; no silent subset')
        if digest(tasks)!=digest(load_benchmark(candidate)):raise ValueError('Frozen evaluation tasks must be identical')
        protected=set(request.requirements.protected_tasks)|{t['id'] for t in tasks if t.get('behavior_constraint')=='protected'}
        if not protected<={t['id'] for t in tasks}:raise ValueError('Unknown protected task')
        specification=assurance.propose(baseline,candidate,intent=request.intent)
        sides={}
        for name,cfg in (('baseline',baseline),('candidate',candidate)):
            docs,chunks=scan_sources(cfg)
            sides[name]={'cfg':{'sources':public(cfg)['sources'],'settings':cfg.get('settings',{})},'chunks':chunks,
                'manifest':{d['id']:d['fingerprint'] for d in docs}}
        if any(not e['quote'].strip() or e['document_id'] not in sides['baseline']['manifest'] for task in tasks for e in task.get('evidence',[])):
            raise ValueError('Reference evidence requires nonempty quotes and frozen registered document identities')
        alternatives=[a.model_dump() for a in request.alternatives]
        original=Alternative(name='original',corpus='baseline').model_dump()
        for alternative in alternatives:
            side=sides[alternative['corpus']]
            for key,known in (('exclude_sources',{s['id'] for s in side['cfg']['sources']}),('exclude_documents',set(side['manifest'])),('exclude_passages',{c['id'] for c in side['chunks']})):
                if len(set(alternative[key]))!=len(alternative[key]) or not set(alternative[key])<=known:raise ValueError('Unknown or duplicate alternative '+key)
            if alternative['policy'] is not None:validate_policy(alternative['policy'])
        history=historical_ablations(candidate,baseline,tasks,sides['baseline']['manifest'],request.ablation_run_ids)
        identity={'version':1,'request':request.model_dump(),'specification_id':specification['id'],'historical_report_hashes':[h['report_hash'] for h in history],
            'baseline_manifest':sides['baseline']['manifest'],'candidate_manifest':sides['candidate']['manifest'],'tasks':digest(tasks)}
        ident=digest(identity)
        if persist:
            saved=db.get(candidate,ident)
            if saved:return saved['report']
        measured=call('knowledge_measure',tasks=tasks,alternatives=[original]+alternatives,baseline=sides['baseline'],candidate=sides['candidate'])
        if not isinstance(measured,list) or len(measured)!=len(alternatives)+1:raise ValueError('Invalid decision worker experiment contract')
        for requested,result in zip([original]+alternatives,measured):
            side=sides[requested['corpus']];known={c['id']:c for c in side['chunks']}
            if result.get('name')!=requested['name'] or result.get('corpus')!=requested['corpus'] or [r['task_id'] for r in result['tasks']]!=[t['id'] for t in tasks]:raise ValueError('Decision worker changed experiment/task identities')
            for row in result['tasks']:
                ids=row['retrieved_chunk_ids'];coverage=row['reference_coverage']
                if len(ids)!=len(set(ids)) or not set(ids)<=set(known) or coverage is not None and (type(coverage) not in (float,int) or not math.isfinite(coverage) or not 0<=coverage<=1):raise ValueError('Invalid decision evidence contract')
                if any(known[i]['source_id'] in requested['exclude_sources'] or known[i]['document_id'] in requested['exclude_documents'] or i in requested['exclude_passages'] for i in ids):raise ValueError('Decision worker violated intervention exclusions')
                if row['context_characters']!=sum(len(known[i]['text']) for i in ids) or row['estimated_context_tokens']!=sum(math.ceil(len(known[i]['text'])/4) for i in ids):raise ValueError('Decision worker changed context accounting')
                row['retrieved_evidence']=[{**known[i],'document_version':side['manifest'][known[i]['document_id']]} for i in ids]
        # Recheck after analysis; never publish a result from a stale source/task snapshot.
        again=assurance.propose(baseline,candidate,intent=request.intent)
        if again['id']!=specification['id']:raise ValueError('Knowledge changed during decision evaluation')
        before=measured[0]['tasks'];experiments=[]
        for result in measured:
            evaluation=conventional(result['tasks'],before,request.requirements,protected)
            result.update(conventional=evaluation,verdict=evaluation['verdict'],
                delta_estimated_context_tokens=sum(r['estimated_context_tokens'] for r in result['tasks'])-sum(r['estimated_context_tokens'] for r in before),
                measurement_kind='retrieval_evidence_only',answer_accuracy=None,prompt_tokens=None,completion_tokens=None,total_tokens=None,
                model_cost_usd=None,cost_per_evaluated_question_usd=None,
                estimated_context_tokens=sum(r['estimated_context_tokens'] for r in result['tasks']),
                estimator='sum ceil(passage characters / 4); not tokenizer or prompt usage')
            known_coverage=[r['reference_coverage'] for r in result['tasks'] if r['reference_coverage'] is not None]
            result['reference_metrics']={'annotated_tasks':len(known_coverage),'total_tasks':len(tasks),
                'mean_literal_coverage':sum(known_coverage)/len(known_coverage) if known_coverage else None,
                'fully_covered_tasks':sum(v==1 for v in known_coverage),'semantic_correctness':None}
            price=(baseline if result['corpus']=='baseline' else candidate).get('model',{}).get('input_price_per_million_usd')
            result['configured_input_price_per_million_usd']=price
            result['estimated_context_input_cost_usd']=result['estimated_context_tokens']*price/1e6 if price is not None else None
            result['cost_estimate_scope']='Context-only character heuristic at configured input price; excludes prompt overhead, output and evaluation costs. Not measured savings.'
            experiments.append(result)
        refs={d:{t['id'] for t in tasks if any(e['document_id']==d for e in t.get('evidence',[]))} for d in sides['baseline']['manifest']}
        entities=[]
        for source in sides['baseline']['cfg']['sources']:
            docs=sorted(d for d in sides['baseline']['manifest'] if d.startswith(source['id']+'::'))
            entities.append({'level':'source','id':source['id'],'document_ids':docs,'versions':{d:sides['baseline']['manifest'][d] for d in docs},'referenced_tasks':sorted(set().union(*(refs[d] for d in docs)))})
        for alt in alternatives:
            for level,key in (('document','exclude_documents'),('passage','exclude_passages')):
                if alt['corpus']!='baseline':continue
                for i in alt[key]:
                    d=i if level=='document' else next(c['document_id'] for c in sides['baseline']['chunks'] if c['id']==i)
                    if not any(e['id']==i and e['level']==level for e in entities):entities.append({'level':level,'id':i,'document_ids':[d],'versions':{d:sides['baseline']['manifest'][d]},'referenced_tasks':sorted(refs[d])})
        changed={c['document_id'] for c in specification['changes']};conflicted={c[s]['document_id'] for c in specification['potential_conflicts'] for s in ('left','right')}
        recommendations=_recommendations(entities,alternatives,experiments[1:],before,protected,changed,conflicted)
        for row in recommendations:
            row['candidate_versions']={d:sides['candidate']['manifest'].get(d) for d in row['document_ids']}
            row['version_change_detected']=any(d in changed for d in row['document_ids'])
            row['update_requires_review']=row['version_change_detected']
            row['historical_ablation_observations']=[{'run_id':h['run_id'],'measurement_kind':h['measurement_kind'],'comparison':c} for h in history for c in h['comparisons'] if row['level']=='source' and row['id'] in c['excluded_sources'] or row['level']=='document' and row['id'] in c['excluded_documents']]
        eligible=[e for e in experiments[1:] if e['verdict']=='REVIEW' and not e['conventional']['uncertain_tasks'] and not e['conventional']['reference_regressions']]
        best=min(eligible,key=lambda e:(e['estimated_context_tokens'],e['name'])) if eligible else None
        report={'kind':'knowledge_decision','id':ident,'version':1,'identity':identity,'specification':specification,
            'requirements':request.requirements.model_dump(),'protected_tasks':sorted(protected),'experiments':experiments,
            'recommendations':recommendations,'recommended_experiment':best['name'] if best else None,
            'historical_ablations':history,
            'recommendation_scope':'Lowest estimated retrieved context among tested evidence-qualified alternatives; not answer-quality optimization',
            'verdict':'REVIEW' if best else 'INCONCLUSIVE','release_authorized':False,'automatically_applied':False,
            'conventional_comparison':{'same_outputs':True,'detection_ties':len(experiments),'additional_verified_detection':0,
                'conventional_selected_experiment':best['name'] if best else None,
                'selection_policy':'Ordinary exhaustive search over the identical alternatives, same reference/scope/conflict constraints, minimum estimated context size, deterministic name tie-break',
                'selection_tie':True,'shared_retrieval_evaluations':len(tasks)*len(experiments),
                'diagnosis_benefit':'Version/impact links and explicit intervention record available; human effort UNKNOWN'},
            'impact_prediction':{'predicted_tasks':sorted(r['task_id'] for r in specification['impact'] if r['potentially_affected']),
                'precision':None,'recall':None,'label_status':'Independent impact labels unavailable; predictions are not regressions'},
            'overhead':{'wall_ms':1000*(time.perf_counter()-started),'retrieval_evaluations':len(tasks)*len(experiments),
                'generation_attempts':0,'external_spend_usd':0,'actual_model_usage':None},
            'validation':{'labels':'registered declarations; independence not verified','semantic_review':'PENDING','heldout_validation':'PENDING',
                'real_model_evaluation':'DISABLED; fresh authorization and reviewed gate required'},
            'limitations':['Literal reference coverage does not establish answer correctness, unsupported-answer rejection or semantic citations.',
                'REMOVE means potential redundancy requiring explicit review; interactions must be tested jointly.',
                'No source, production configuration or authoritative evaluation label was modified.']}
        if persist:return db.save_decision(candidate,report)
        return report
