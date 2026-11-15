"""Cost-bounded, counterfactual source evaluation on real docs and live model/agent calls."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import statistics
import time
from typing import Callable
from .config import read_config
from .ingest import load_benchmark, scan_sources
from .retrieve import search
from .provider import run_chat, run_external
from .grade import grade, wilson_interval


def preflight(cfg: dict) -> dict:
    docs, _ = scan_sources(cfg, include_text=False)
    tasks = load_benchmark(cfg)
    return {'project_id': cfg['id'], 'project': cfg['name'], 'document_count': len(docs),
            'task_count': len(tasks), 'source_count': len(cfg['sources']),
            'sources': [{**{k:s.get(k) for k in ('id','name')}, 'document_count':sum(d['source_id']==s['id'] for d in docs)}
                        for s in cfg['sources']], 'documents': docs,
            'benchmark_ready': bool(tasks), 'corpus_ready': bool(docs)}


def run(cfg: dict, *, exclude_sources: list[str] | None = None,
        exclude_documents: list[str] | None = None, document_ids: list[str] | None = None,
        mode: str = 'baseline', max_tasks: int | None = None,
        notify: Callable[[str], None] | None = None) -> dict:
    disabled = list(dict.fromkeys(exclude_sources or []))
    excluded_docs = list(dict.fromkeys(exclude_documents or []))
    known = {s['id'] for s in cfg['sources']}
    if not set(disabled).issubset(known):
        raise ValueError('Unrecognized excluded source')
    if mode not in ('baseline', 'ablation', 'document_ablation'):
        raise ValueError('Mode must be baseline, ablation or document_ablation')
    documents, chunks = scan_sources(cfg)
    known_docs = {d['id'] for d in documents}
    if not set(excluded_docs).issubset(known_docs):
        raise ValueError('Unrecognized excluded document')
    if not documents:
        raise ValueError('No documents found. Add files to a workspace source folder.')
    tasks = load_benchmark(cfg)
    if not tasks:
        raise ValueError('No benchmark tasks. Add independent expected answers to benchmark.jsonl.')
    settings = cfg.get('settings', {})
    task_limit = int(settings.get('max_tasks_per_run', 50))
    limit = min(task_limit, max_tasks if max_tasks is not None else task_limit)
    if limit <= 0:
        raise ValueError('max_tasks must be positive')
    tasks = tasks[:limit]
    variants = [(disabled, excluded_docs)]
    if mode in ('ablation','document_ablation'):
        if disabled or excluded_docs:
            raise ValueError('Ablation studies start from all sources and documents')
        if mode == 'ablation':
            variants = [([],[])] + [([source['id']],[]) for source in cfg['sources']]
        else:
            requested = list(dict.fromkeys(document_ids or []))
            maximum_docs = int(settings.get('max_documents_per_study', 8))
            if not requested or len(requested) > maximum_docs or not set(requested).issubset(known_docs):
                raise ValueError(f'Select 1..{maximum_docs} known document IDs for a document study')
            variants = [([],[])] + [([],[id]) for id in requested]
    call_count = len(tasks) * len(variants)
    maximum = int(settings.get('max_model_calls_per_run', 100))
    if call_count > maximum:
        raise ValueError(f'Request would call model {call_count} times, above cap {maximum}. Reduce tasks or adjust project settings.')
    manifest = {d['id']: d['fingerprint'] for d in documents}
    # The complete agent and retrieval configuration must remain stable for data-only comparisons.
    controlled = {'runner':cfg.get('runner','rag_chat'), 'model':cfg.get('model',{}),
                  'agent':cfg.get('agent',{}),
                  'retrieval':{k:settings.get(k) for k in ('max_chunks','chunk_chars','chunk_strategy','table_evidence','overlap_chars','max_context_chars','deduplicate_passages','retrieval_policy','retrieval_contract','answering_mode','calculation_reviewers')}}
    experiment_spec_sha = hashlib.sha256(json.dumps(controlled, sort_keys=True).encode()).hexdigest()
    benchmark_sha = hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
    from .validation import Budget
    cfg = {**cfg, '_experiment_budget': Budget(settings)}
    started = time.perf_counter()
    results = []
    for i, (excluded, doc_excluded) in enumerate(variants):
        if notify: notify(f'Running configuration {i+1}/{len(variants)}')
        variant = evaluate_variant(cfg, tasks, chunks, excluded, doc_excluded)
        results.append(variant)
    result = {'version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
              'project': {'id':cfg['id'], 'name':cfg['name']},
              'runner': cfg.get('runner', 'rag_chat'),
              'model': cfg.get('model', {}).get('name') if cfg.get('runner', 'rag_chat')=='rag_chat' else 'customer-agent',
              'config_hash':cfg['_config_hash'], 'experiment_spec_sha256':experiment_spec_sha,
              'benchmark_sha256':benchmark_sha,
              'manifest':manifest, 'document_count':len(documents), 'source_count':len(cfg['sources']),
              'mode':mode, 'api_calls':call_count, 'variants':results,
              'evaluation_elapsed_ms':round((time.perf_counter()-started)*1000,2),
              'measurement_kind':cfg.get('measurement_kind', 'unverified_endpoint'),
              'disclaimer':'Actual wall time and provider-reported tokens; model USD cost is estimated from user-configured token rates when provided. Exact ground truth is user supplied. Source importance is benchmark-conditional.'}
    if mode in ('ablation','document_ablation'):
        base = results[0]
        result['impacts'] = [compare_variants(base, v) for v in results[1:]]
    return result


def evaluate_variant(cfg: dict, tasks: list[dict], chunks: list[dict], excluded: list[str],
                     excluded_documents: list[str] | None = None, *,
                     exclude_passages: list[str] | None = None) -> dict:
    if not tasks:
        raise ValueError('Evaluation requires tasks')
    excluded_documents = excluded_documents or []
    disabled=set(excluded);disabled_documents=set(excluded_documents);disabled_passages=set(exclude_passages or [])
    filtered = [x for x in chunks if x['source_id'] not in disabled and x['document_id'] not in disabled_documents and x['id'] not in disabled_passages]
    allowed_sources = sorted({x['source_id'] for x in filtered})
    rows = cfg.get('_partial_tasks', [])
    for task in tasks:
        if cfg.get('_active_request') is not None:
            cfg['_active_request'].update(task_id=task['id'], status='in_progress')
        budget_guard = cfg.get('_experiment_budget')
        if budget_guard:
            budget_guard.check_time()
        start = time.perf_counter()
        if cfg.get('runner', 'rag_chat') == 'rag_chat':
            t0 = time.perf_counter()
            from .policies import select_context
            from .routing import restrict
            pool, routing_trace = restrict(task['question'],filtered,cfg)
            scope_trace = None
            if (cfg.get('settings', {}).get('retrieval_policy') or {}).get('name') in ('passage_coverage','predicate'):
                from .evidence_contract import precheck
                pool, scope_trace = precheck(task['question'], pool, cfg, None, task.get('scope'))
            retrieved, selection = select_context(task['question'], pool, {**cfg,'_calculation_contract':task.get('calculation_contract'),'_task_scope':task.get('scope')})
            selection['routing_contract']=routing_trace
            if scope_trace is not None:
                selection['pre_ranking_scope'] = scope_trace
            retrieval_ms = round((time.perf_counter()-t0)*1000, 2)
            from .release_policy import citation_required
            needs_citations=citation_required(cfg,task)
            from .evidence_contract import precheck,abstention
            if needs_citations:
                selection['before_grounding_ids']=[c['id'] for c in retrieved]
                retrieved,guard=precheck(task['question'],retrieved,cfg,task.get('evidence_contract'),task.get('scope'))
            else:guard=None
            if cfg.get('settings', {}).get('answering_mode','model')=='source_calculation':
                from .facts import answer
                # This explicitly selected non-LLM path verifies each declared
                # period/predicate and conflict; generic numeric-shape warnings
                # remain recorded instead of confusing distinct operand periods.
                result=answer(task['question'],retrieved,task.get('calculation_contract'),task.get('calculation_authorization'),
                              {**cfg,'_answer_contract':task.get('answer_contract')},task.get('scope'))
                result['calculation']['necessary_evidence_screen']=guard
                if guard and guard['missing_declared_alias_groups']:
                    from .facts import unresolved_table_subjects
                    calculation=result['calculation']
                    unresolved=unresolved_table_subjects(guard['missing_declared_alias_groups'],calculation) if calculation.get('operation_authorized') else guard['missing_declared_alias_groups']
                    if unresolved:
                        calculation['answer_suppressed']='declared_evidence_subject_missing'
                        result={**abstention(guard,cfg),'calculation':calculation,'answer_origin':'source_calculation','usage_source':'not_called_source_calculation'}
                    else:calculation['table_cell_subjects_resolve_lexical_groups']=True
            elif guard and guard['abstain']:
                result=abstention(guard,cfg)
            elif not retrieved and (selection.get('abstain_without_context') or needs_citations):
                result = {'answer':'INSUFFICIENT_EVIDENCE','citations':[],'invalid_citations':[],
                          'json_format_valid':True,'input_tokens':0,'output_tokens':0,'context_tokens':0,
                          'model_cost_usd':0.0,'data_cost_usd':0.0,'model_latency_ms':0.0,
                          'cost_type':'not_called','usage_source':'not_called_no_context','model_name':cfg['model']['name']}
            else:
                if budget_guard:
                    budget_guard.before()
                result = run_chat(task['question'], retrieved, {**cfg,'_require_citations':needs_citations,'_answer_contract':task.get('answer_contract'),'_evidence_contract':task.get('evidence_contract'),'_task_scope':task.get('scope'),'_grounding_precheck':guard})
        else:
            settings = cfg.get('settings', {})
            if settings.get('retrieval_contract') is not None:
                raise ValueError('External adapters must implement their own declared routing; built-in retrieval_contract is supported only by rag_chat')
            if settings.get('retrieval_policy'):
                raise ValueError('External adapter does not support arbitrary retrieval policies')
            controls = dict(settings.get('agent_retrieval_controls', {}))
            for name in ('max_context_chars', 'deduplicate_passages'):
                if settings.get(name) is not None:
                    controls[name] = settings[name]
            if exclude_passages:
                controls['excluded_passage_ids'] = exclude_passages
            retrieved = []
            retrieval_ms = None
            if budget_guard:
                budget_guard.before()
            result = run_external(task['question'], allowed_sources, excluded, excluded_documents, {**cfg,'_answer_contract':task.get('answer_contract')},
                                  task['id'], retrieval_controls=controls)
        if budget_guard:
            budget_guard.after(result)
        elapsed = round((time.perf_counter()-start)*1000, 2)
        correct = grade(result['answer'], task) and result.get('response_complete', True) and result.get('answer_contract_valid',True)
        ids = [r['id'] for r in retrieved] if cfg.get('runner','rag_chat')=='rag_chat' else result.get('retrieved_chunk_ids',[])
        retrieved_source_ids = list(dict.fromkeys(x['source_id'] for x in retrieved)) if cfg.get('runner','rag_chat')=='rag_chat' else list(dict.fromkeys(i.split('::')[0] for i in ids))
        source_cost = 0.0
        source_lookup = {s['id']: s for s in cfg.get('sources', [])}
        for source_id in retrieved_source_ids:
            price = source_lookup.get(source_id, {}).get('per_call_price_usd')
            if isinstance(price, (int, float)):
                source_cost += float(price)
        data_cost = (float(result['data_cost_usd']) + source_cost
                     if result['data_cost_usd'] is not None else None)
        from .grounding import score_review, review_item
        grounding = score_review(task['question'], result['answer'], retrieved, result['citations'], cfg.get('_grounding_reviews', {}))
        if cfg.get('_review_items') is not None:
            cfg['_review_items'].append(review_item(task['question'], result['answer'], retrieved))
        rows.append({**grounding, **({'calculation':result['calculation']} if 'calculation' in result else {}), 'selection': selection if cfg.get('runner', 'rag_chat') == 'rag_chat' else None, 'id': task['id'], 'question':task['question'], 'expected':task['expected'],
                     'actual':result['answer'],'normalized_answer':result.get('normalized_answer',result['answer']),'raw_answer':result.get('raw_answer'),'raw_response':result.get('raw_response'),'answer_contract_valid':result.get('answer_contract_valid',True),'answer_contract_reason':result.get('answer_contract_reason'),'answer_origin':result.get('answer_origin'),'grounding_precheck':result.get('grounding_precheck'), 'category':task['category'], 'scoring':task['scoring'],
                     'correct':correct, 'citations':result['citations'],
                     'invalid_citations':result['invalid_citations'],
                     'retrieved_chunk_ids':ids, 'retrieved_source_ids':retrieved_source_ids,
                     'retrieval_latency_ms':retrieval_ms, 'model_latency_ms':result['model_latency_ms'],
                     'end_to_end_latency_ms':elapsed, 'prompt_tokens':result['input_tokens'],
                     'completion_tokens':result['output_tokens'], 'context_tokens':result.get('context_tokens'),
                     'context_tokenizer_latency_ms':result.get('context_tokenizer_latency_ms'), 'model_cost_usd':result['model_cost_usd'],
                     'data_cost_usd': data_cost, 'cost_type':result['cost_type'],
                     'usage_source':result['usage_source'], 'json_format_valid':result['json_format_valid'],
                     'model':result['model_name'], 'response_complete': result.get('response_complete', True),
                     'prompt_sha256':result.get('prompt_sha256'),'response_schema_sha256':result.get('response_schema_sha256'),'request_shape_sha256':result.get('request_shape_sha256'),
                     'knowledge_version':result.get('knowledge_version'),'knowledge_manifest':result.get('knowledge_manifest'),'execution_identity':result.get('execution_identity'),
                     'finish_reason': result.get('finish_reason')})
        if cfg.get('_active_request') is not None:
            cfg['_active_request']['status'] = 'completed'
    passed = sum(r['correct'] for r in rows)
    n = len(rows)
    costs = [r['model_cost_usd'] for r in rows]
    data_costs = [r['data_cost_usd'] for r in rows]
    # No hidden invented costs; null means unavailable.
    cost_known = all(x is not None for x in costs)
    data_known = all(x is not None for x in data_costs)
    total_cost = round(sum(costs)+sum(data_costs), 8) if cost_known and data_known else None
    metrics = {'task_count':n, 'passed':passed, 'failed':n-passed,
               'accuracy':round(passed/n, 4), 'accuracy_ci95':wilson_interval(passed,n),
               'mean_latency_ms':round(statistics.mean(r['end_to_end_latency_ms'] for r in rows), 2),
               'median_latency_ms':round(statistics.median(r['end_to_end_latency_ms'] for r in rows), 2),
               'p95_latency_ms':round(sorted(r['end_to_end_latency_ms'] for r in rows)[max(0, math.ceil(.95*n)-1)],2),
               'mean_retrieval_ms':round(statistics.mean(r['retrieval_latency_ms'] for r in rows if r['retrieval_latency_ms'] is not None),2)
                   if any(r['retrieval_latency_ms'] is not None for r in rows) else None,
               'provider_reported_prompt_tokens':sum(r['prompt_tokens'] for r in rows if r['prompt_tokens'] is not None)
                   if all(r['prompt_tokens'] is not None for r in rows) else None,
               'provider_reported_completion_tokens':sum(r['completion_tokens'] for r in rows if r['completion_tokens'] is not None)
                   if all(r['completion_tokens'] is not None for r in rows) else None,
               'total_cost_usd':total_cost, 'cost_type':'estimated_from_observed_tokens' if total_cost is not None and
                     cfg.get('runner','rag_chat')=='rag_chat' else ('agent_reported' if total_cost is not None else 'unavailable'),
               'citation_format_rate':round(sum(bool(r['citations']) and not r['invalid_citations'] for r in rows)/n,4),
               'abstentions':sum(r['actual'].strip()=='INSUFFICIENT_EVIDENCE' for r in rows)}
    prompt = metrics['provider_reported_prompt_tokens']
    completion = metrics['provider_reported_completion_tokens']
    metrics['context_tokens'] = sum(r['context_tokens'] for r in rows) if all(r['context_tokens'] is not None for r in rows) else None
    metrics['fallback_rate'] = sum(bool(r.get('selection') and r['selection'].get('fallback_used')) for r in rows)/n
    metrics['selection_check_ms'] = sum(r['selection'].get('selection_check_ms',0) for r in rows if r.get('selection'))
    metrics['input_tokens'] = metrics['provider_reported_prompt_tokens']
    metrics['output_tokens'] = metrics['provider_reported_completion_tokens']
    metrics['token_usage_sources'] = sorted({r['usage_source'] for r in rows})
    metrics.update(total_tokens=prompt + completion if prompt is not None and completion is not None else None,
                   cost_per_task_usd=total_cost/n if total_cost is not None else None,
                   cost_per_success_usd=total_cost/passed if total_cost is not None and passed else None,
                   source_coverage=(len({sid for r in rows for sid in r['retrieved_source_ids']}) / max(1, len(cfg['sources']))
                                    if cfg.get('runner', 'rag_chat') == 'rag_chat' else None),
                   groundedness=(statistics.mean(r['groundedness'] for r in rows) if all(r['groundedness'] is not None for r in rows) else None),
                   unsupported_claims=(sum(r['unsupported_claims'] for r in rows) if all(r['unsupported_claims'] is not None for r in rows) else None))
    return {'excluded_sources':excluded, 'excluded_documents':excluded_documents, 'metrics':metrics, 'tasks':rows}


def paired_bootstrap_ci(base: dict, candidate: dict, draws: int = 2000) -> list[float] | None:
    a = {t['id']: t for t in base['tasks']}
    b = {t['id']: t for t in candidate['tasks']}
    ids = [id for id in a if id in b]
    if not ids:
        return None
    changes = [int(b[id]['correct']) - int(a[id]['correct']) for id in ids]
    generator = random.Random(1729)  # Reproducible intervals
    bootstrap = []
    for _ in range(draws):
        sample = [generator.choice(changes) for _ in range(len(changes))]
        bootstrap.append(100.0 * (sum(sample) / len(sample)))
    bootstrap.sort()
    return [round(bootstrap[int(.025 * (draws - 1))], 2), round(bootstrap[int(.975 * (draws - 1))], 2)]


def _objective_score(metrics: dict, objective: str) -> float:
    accuracy = metrics.get('accuracy', 0.0)
    cost = metrics.get('total_cost_usd')
    latency = metrics.get('mean_latency_ms')
    tokens = metrics.get('total_tokens')
    passed = metrics.get('passed', 0)
    cost_per_success = cost / passed if cost is not None and passed else float('inf')
    if objective == 'cost_per_success':
        return cost_per_success
    if objective == 'token_budget':
        return tokens if tokens is not None else float('inf')
    if objective == 'latency':
        return latency if latency is not None else float('inf')
    if objective == 'p95_latency':
        value = metrics.get('p95_latency_ms')
        return value if value is not None else float('inf')
    if objective == 'balanced':
        return cost_per_success * 1000 + (latency if latency is not None else float('inf')) + (1-accuracy)*10000
    raise ValueError('Unsupported objective')


def _percent_change(baseline: float | None, candidate: float | None) -> float | None:
    if baseline in (None, 0) or candidate is None:
        return None
    if baseline == 0:
        return 100.0 if candidate > 0 else 0.0
    return round((1.0 - (candidate / baseline)) * 100.0, 2)


def diagnose_missing_information(cfg: dict, *, tasks: list[dict] | None = None, chunks: list[dict] | None = None) -> list[dict]:
    tasks = tasks if tasks is not None else load_benchmark(cfg)
    chunks = chunks or scan_sources(cfg)[1]
    from .validation import Budget
    cfg = {**cfg, '_experiment_budget': Budget(cfg.get('settings', {}))}
    baseline = evaluate_variant(cfg, tasks, chunks, [], [])
    ablations = {source['id']: evaluate_variant(cfg, tasks, chunks, [source['id']], [])
                 for source in cfg['sources']} if any(not t['correct'] for t in baseline['tasks']) else {}
    source_ids = [source['id'] for source in cfg['sources']]
    findings = []
    for task in baseline['tasks']:
        if task['correct']:
            continue
        likely = {'task_id': task['id'], 'task_category': task.get('category', 'General'),
                  'potentially_conflicting_source_ids': [], 'reason': 'No single-source removal repairs this failure'}
        for source_id in source_ids:
            candidate = ablations[source_id]
            task_result = next((r for r in candidate['tasks'] if r['id'] == task['id']), None)
            if task_result and task_result['correct'] and not task['correct']:
                likely['potentially_conflicting_source_ids'].append(source_id)
        if likely['potentially_conflicting_source_ids']:
            likely['reason'] = 'The task becomes correct when the source is removed, suggesting the signal is source-dependent but not necessarily missing everywhere; inspect the missing evidence path.'
            if len(likely['potentially_conflicting_source_ids']) == 1:
                likely['reason'] = 'Removing this source repaired the task; this suggests interference, not missing evidence or causal proof.'
        findings.append(likely)
    return findings


def optimize_configurations(cfg: dict, *, quality_floor: float = 0.9, min_groundedness: float = 0.75,
                           objective: str = 'cost_per_success', max_tasks: int | None = None,
                           max_candidates: int = 8) -> dict:
    from .validation import optimize
    return optimize(cfg, quality_floor=quality_floor, min_citation_rate=min_groundedness,
                    objective=objective, max_tasks=max_tasks, max_candidates=max_candidates)


def compare_variants(base: dict, candidate: dict) -> dict:
    a = {t['id']:t for t in base['tasks']}
    b = {t['id']:t for t in candidate['tasks']}
    common = [id for id in a if id in b]
    lost = [id for id in common if a[id]['correct'] and not b[id]['correct']]
    gained = [id for id in common if not a[id]['correct'] and b[id]['correct']]
    bm = base['metrics']; cm = candidate['metrics']
    return {'excluded_sources':candidate['excluded_sources'],
            'excluded_documents':candidate.get('excluded_documents',[]), 'lost_tasks':lost,'gained_tasks':gained,
            'delta_accuracy_points':round(100*(cm['accuracy']-bm['accuracy']),2),
            'paired_delta_ci95_points':paired_bootstrap_ci(base,candidate),
            'delta_mean_latency_ms':round(cm['mean_latency_ms']-bm['mean_latency_ms'],2),
            'delta_cost_usd':round(cm['total_cost_usd']-bm['total_cost_usd'],8)
                if bm['total_cost_usd'] is not None and cm['total_cost_usd'] is not None else None,
            'baseline_accuracy':bm['accuracy'],'candidate_accuracy':cm['accuracy'],
            'note':'Paired benchmark sensitivity, not a guarantee of causal business impact. Small samples have high uncertainty.'}


def compare_runs(old: dict, new: dict) -> dict:
    if not old or not new or old['status']!='completed' or new['status']!='completed':
        raise ValueError('Both runs must be completed')
    first, second = old['report'], new['report']
    if first['project']['id'] != second['project']['id']:
        raise ValueError('Cannot compare different projects')
    if first['benchmark_sha256'] != second['benchmark_sha256']:
        raise ValueError('Benchmark changed between runs; comparisons would be misleading')
    if first['runner'] != second['runner'] or first['model'] != second['model']:
        raise ValueError('Runner/model changed; data-only regression attribution is not valid')
    if first.get('experiment_spec_sha256') != second.get('experiment_spec_sha256'):
        raise ValueError('Model or retrieval configuration changed; cannot attribute the difference to data only')
    a, b = first['manifest'], second['manifest']
    return {'baseline_id':old['id'], 'candidate_id':new['id'],
            'changed_documents':sorted(k for k in set(a)&set(b) if a[k]!=b[k]),
            'new_documents':sorted(set(b)-set(a)), 'removed_documents':sorted(set(a)-set(b)),
            'comparison':compare_variants(first['variants'][0],second['variants'][0]),
            'warnings':['Temperature 0 reduces but does not eliminate LLM nondeterminism.',
                        'Differences may also reflect retrieval or provider behavior, not just corpus changes.']}
