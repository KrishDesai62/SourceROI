"""Frozen-corpus Data CI with controlled comparisons and bounded rollback tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from . import db
from .config import read_config,secure_path
from .engine import evaluate_variant,compare_variants
from .ingest import load_benchmark,scan_sources
from .validation import Budget
from .diagnosis import diagnose


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def freeze(cfg, destination):
    docs,_=scan_sources(cfg); tasks=load_benchmark(cfg)
    manifest={d['id']:d['fingerprint'] for d in docs}
    identity=digest({'manifest':manifest,'benchmark':tasks,'model':cfg.get('model'), 'settings':cfg.get('settings'), 'agent':cfg.get('agent'),'runner':cfg.get('runner','rag_chat'),'source_metadata':[{k:v for k,v in s.items() if k!='path'} for s in cfg['sources']]})
    destination=Path(destination).resolve()
    if destination.exists():
        raise ValueError('Frozen destination already exists; snapshots are immutable')
    source=Path(cfg['_root'])
    if destination==source or source.is_relative_to(destination):
        raise ValueError('Snapshot must not contain/replace the source workspace')
    if any(destination.is_relative_to(secure_path(source,s['path'])) for s in cfg['sources']):
        raise ValueError('Snapshot destination must not be inside a registered source folder')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='ci-freeze-') as directory:
        root=Path(directory)/'snapshot';root.mkdir()
        public={k:v for k,v in cfg.items() if not k.startswith('_')}
        public['sources']=[{**s,'path':secure_path(source,s['path']).relative_to(source).as_posix()} for s in cfg['sources']]
        public['benchmark']=secure_path(source,cfg.get('benchmark','benchmark.jsonl')).relative_to(source).as_posix()
        if cfg.get('data_provenance'):
            public['data_provenance']=secure_path(source,cfg['data_provenance']).relative_to(source).as_posix()
        (root/'project.json').write_text(json.dumps(public,indent=2)+'\n')
        target=root/public['benchmark'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(secure_path(source,cfg.get('benchmark','benchmark.jsonl')),target)
        if cfg.get('data_provenance'):
            target=root/public['data_provenance'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(secure_path(source,cfg['data_provenance']),target)
        for s in public['sources']:
            target=root/s['path'];target.mkdir(parents=True,exist_ok=True)
        for doc in docs:
            target=root/doc['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(secure_path(source,doc['path']),target)
        copied_manifest={d['id']:d['fingerprint'] for d in scan_sources(read_config(root))[0]}
        if copied_manifest!=manifest:
            raise ValueError('Corpus changed during freeze; no snapshot was published')
        (root/'snapshot.json').write_text(json.dumps({'version':1,'identity':identity,'manifest':manifest,'benchmark_sha256':digest(tasks)},indent=2)+'\n')
        root.replace(destination)
    return {'path':str(destination),'identity':identity,'document_count':len(docs)}


def _evidence_coverage_in_process(task,row,chunks):
    refs=task.get('evidence',[])
    if not refs:return None
    by_id={c['id']:c for c in chunks}
    context=[by_id[cid] for cid in row['retrieved_chunk_ids'] if cid in by_id]
    return sum(any(c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in context) for e in refs)/len(refs)


def run_data_ci(baseline_cfg,candidate_cfg,*,max_tasks=20,max_regressions=0,max_accuracy_drop=0,
                max_evidence_drop=0,affected_only=False,repair=False,ablate=False,budget=None,task_ids=None):
    if not candidate_cfg.get('model',{}).get('local_only') or candidate_cfg.get('runner','rag_chat')!='rag_chat':
        raise ValueError('This Data CI execution requires an explicitly local-only RAG model')
    if type(max_tasks) is not int or type(max_regressions) is not int or max_tasks<1 or max_regressions<0 or not 0<=max_accuracy_drop<=1 or not 0<=max_evidence_drop<=1:
        raise ValueError('Invalid Data CI thresholds')
    for key in ('model','settings','runner','agent'):
        if baseline_cfg.get(key)!=candidate_cfg.get(key):
            raise ValueError('Frozen model/retrieval settings differ; controlled data-only comparison is invalid')
    tasks=load_benchmark(baseline_cfg)
    full_benchmark_sha=digest(tasks)
    total_benchmark_tasks=len(tasks)
    if digest(tasks)!=digest(load_benchmark(candidate_cfg)):
        raise ValueError('Frozen benchmark changed; comparisons would be misleading')
    a_docs,a_chunks=scan_sources(baseline_cfg); b_docs,b_chunks=scan_sources(candidate_cfg)
    a={d['id']:d['fingerprint'] for d in a_docs}; b={d['id']:d['fingerprint'] for d in b_docs}
    snapshot=Path(baseline_cfg['_root'])/'snapshot.json'
    expected_identity=digest({'manifest':a,'benchmark':tasks,'model':baseline_cfg.get('model'),'settings':baseline_cfg.get('settings'),'agent':baseline_cfg.get('agent'),'runner':baseline_cfg.get('runner','rag_chat'),'source_metadata':[{k:v for k,v in s.items() if k!='path'} for s in baseline_cfg['sources']]})
    if not snapshot.exists() or json.loads(snapshot.read_text())['manifest']!=a or json.loads(snapshot.read_text())['identity']!=expected_identity:
        raise ValueError('Baseline is not a verified immutable snapshot')
    changed=sorted(k for k in set(a)&set(b) if a[k]!=b[k]);removed=sorted(set(a)-set(b));added=sorted(set(b)-set(a))
    changed_set=set(changed+removed+added)
    source_a={s['id']:digest({k:v for k,v in s.items() if k!='path'}) for s in baseline_cfg['sources']}
    source_b={s['id']:digest({k:v for k,v in s.items() if k!='path'}) for s in candidate_cfg['sources']}
    source_metadata_changed=sorted(sid for sid in set(source_a)|set(source_b) if source_a.get(sid)!=source_b.get(sid))
    if task_ids is not None:
        requested=set(task_ids)
        if not requested <= {t['id'] for t in tasks}:raise ValueError('Unknown task IDs')
        tasks=[t for t in tasks if t['id'] in requested]
    affected=[t for t in tasks if any(e['document_id'] in changed_set for e in t.get('evidence',[]))]
    selected=(affected if affected_only else tasks)[:max_tasks]
    if not selected:raise ValueError('No selected tasks; use full audit for unannotated changes')
    budget=budget or Budget(candidate_cfg.get('settings',{}))
    calls_before=budget.calls
    required=2*len(selected)+(len(selected) if repair else 0)+(len(selected) if ablate else 0)
    if budget.calls+required>budget.limit:raise ValueError('Data CI would exceed shared model-call cap')
    cfg_a={**baseline_cfg,'_experiment_budget':budget};cfg_b={**candidate_cfg,'_experiment_budget':budget}
    report={'kind':'data_ci','version':1,'status':'running','changed_documents':changed,'removed_documents':removed,
            'added_documents':added,'changed_sources':sorted({i.split('::')[0] for i in changed_set}|set(source_metadata_changed)),
            'source_metadata_changed':source_metadata_changed,
            'selected_task_ids':[t['id'] for t in selected], 'selection_mode':'annotated_affected_subset' if affected_only else 'explicit_task_subset' if task_ids is not None else 'full_audit' if len(selected)==total_benchmark_tasks else 'bounded_prefix_subset',
            'total_benchmark_tasks':total_benchmark_tasks,'evaluated_tasks':len(selected),
            'untested_task_count':total_benchmark_tasks-len(selected),'task_coverage_fraction':len(selected)/total_benchmark_tasks,
            'affected_selection_limitation':'Reference-based shortlisting is not exhaustive; full audit is the default.',
            'baseline_manifest':a,'candidate_manifest':b,'benchmark_sha256':full_benchmark_sha,
            'thresholds':{'max_regressions':max_regressions,'max_accuracy_drop':max_accuracy_drop,'max_evidence_drop':max_evidence_drop},
            'execution_limits':{'max_calls':budget.limit,'max_seconds':budget.max_seconds},
            'repairs':[],'ablation':None,'automatically_applied':False}
    rid=db.begin(candidate_cfg,'data_ci',[])
    try:
        report['baseline']=evaluate_variant(cfg_a,selected,a_chunks,[])
        db.checkpoint(candidate_cfg,rid,report)
        report['candidate']=evaluate_variant(cfg_b,selected,b_chunks,[])
        comparison=compare_variants(report['baseline'],report['candidate']);report['comparison']=comparison
        from .uncertainty import objective_interval
        report['objective_delta_ci95']=objective_interval({'runs':[report['baseline']]},{'runs':[report['candidate']]},selected,'token_budget')
        report['uncertainty_note']='Small selected samples and paired bootstrap intervals do not prove equivalence or unique causality.'
        before={r['id']:r for r in report['baseline']['tasks']};after={r['id']:r for r in report['candidate']['tasks']}
        changes=[]
        for task in selected:
            old=evidence_coverage(task,before[task['id']],a_chunks);new=evidence_coverage(task,after[task['id']],b_chunks)
            evidence_loss=old is not None and new is not None and old-new>max_evidence_drop
            plausibly_related=sorted(changed_set & ({c.split('#chunk')[0] for c in before[task['id']]['retrieved_chunk_ids']} | {e['document_id'] for e in task.get('evidence',[])}))
            loss=task['id'] in comparison['lost_tasks']
            changes.append({'task_id':task['id'],'new_failure':loss,'baseline_evidence_coverage':old,'candidate_evidence_coverage':new,
                'evidence_regression':evidence_loss,'retrieval_nonempty':bool(after[task['id']]['retrieved_chunk_ids']),
                'severity':'critical' if loss and task.get('critical') else 'high' if loss else 'evidence_warning' if evidence_loss else 'none',
                'plausibly_related_documents':plausibly_related,
                'diagnosis':diagnose(task,after[task['id']],b_chunks,candidate_cfg) if loss or evidence_loss else None})
        report['task_changes']=changes
        evidence_failures=[r['task_id'] for r in changes if r['evidence_regression']]
        failed=len(comparison['lost_tasks'])>max_regressions or comparison['delta_accuracy_points'] < -100*max_accuracy_drop or bool(evidence_failures)
        report['verdict']='blocked' if failed else 'no_detected_regression'
        report['severity']='critical' if any(t['severity']=='critical' for t in changes) else 'high' if comparison['lost_tasks'] else 'evidence_warning' if evidence_failures else 'none'
        report['simple_check_comparison']={'answer_accuracy_new_failures':comparison['lost_tasks'],
            'reference_coverage_failures':evidence_failures,'nonempty_retrieval_failures':[r['task_id'] for r in changes if not r['retrieval_nonempty']],
            'note':'Data CI shares answer and reference-coverage signals; no unique detection superiority is claimed. Localization and rollback experiments add context.'}
        if repair and changed_set:
            with tempfile.TemporaryDirectory(prefix='ci-rollback-') as directory:
                root=Path(directory)/'repair'
                # Restore only data in a temporary candidate copy, never production/user sources.
                root.mkdir(); repair_cfg={**candidate_cfg,'sources':baseline_cfg['sources'],'_root':str(root),'_experiment_budget':budget}
                for s in candidate_cfg['sources']:(root/s['path']).mkdir(parents=True,exist_ok=True)
                for doc in b_docs:
                    target=root/doc['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(secure_path(Path(candidate_cfg['_root']),doc['path']),target)
                for doc in a_docs:
                    if doc['id'] in changed_set:
                        target=root/doc['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(secure_path(Path(baseline_cfg['_root']),doc['path']),target)
                for doc in b_docs:
                    if doc['id'] in added: (root/doc['path']).unlink(missing_ok=True)
                if baseline_cfg.get('data_provenance'):
                    repair_cfg['data_provenance']=baseline_cfg['data_provenance']
                    target=root/baseline_cfg['data_provenance'];target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(secure_path(Path(baseline_cfg['_root']),baseline_cfg['data_provenance']),target)
                rows=[t for t in selected if t['id'] in comparison['lost_tasks'] or t['id'] in evidence_failures]
                if rows:
                    repaired=evaluate_variant(repair_cfg,rows,scan_sources(repair_cfg)[1],[])
                    report['repairs'].append({'type':'temporary_changed_document_rollback','tasks':repaired,
                        'note':'All changed data restored together; repair association is not unique single-source causal attribution.'})
        if ablate and report['changed_sources']:
            variant=evaluate_variant(cfg_a,selected,a_chunks,[s for s in report['changed_sources'] if s in {x['id'] for x in baseline_cfg['sources']}])
            report['ablation']={'variant':variant,'comparison':compare_variants(report['baseline'],variant),
                               'note':'Existing source-ablation baseline; removes entire changed sources, potentially broader than the document edit.'}
        original_titles={d['id']:d['title'] for d in a_docs}
        related={doc for item in changes if item['new_failure'] or item['evidence_regression'] for doc in item['plausibly_related_documents']}
        report['suggested_actions']=[{'action':'review_frozen_version_or_repair','document_id':doc,'title':original_titles.get(doc,doc),
            'frozen_fingerprint':a.get(doc),'candidate_fingerprint':b.get(doc),
            'joint_rollback_tested':bool(report['repairs']),'automatically_applied':False,
            'note':'Review currentness and annotations before restoring; association is not conclusive causal attribution.'} for doc in sorted(related)]
        report.update(status='completed',run_id=rid,model_calls=budget.calls-calls_before,session_calls=budget.calls)
        db.finish(candidate_cfg,rid,report)
        return report
    except Exception as exc:
        report.update(status='incomplete',verdict='inconclusive',error_type=type(exc).__name__)
        db.finish(candidate_cfg,rid,report,type(exc).__name__)
        raise


def evidence_coverage(task,row,chunks):
    from .analysis_boundary import active,call
    if active():return _evidence_coverage_in_process(task,row,chunks)
    if not task.get('evidence'):return None
    return call('coverage',task={'evidence':task['evidence']},row={'retrieved_chunk_ids':row['retrieved_chunk_ids']},chunks=chunks)
