"""Equivalent-authority comparison on EXPOSED authored regression fixtures.

All methods receive identical approvals, revised labels, reviewed replacement
references and unresolved-intent information. No independent validation claim.
"""
import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.validate_knowledge_assurance import SCENARIOS,scenario,BLOCKING,REVIEW
from sourceroi.live import assurance as a
from sourceroi.live.data_ci import evidence_coverage
from sourceroi.live.grade import grade

METHODS=['A_updated_answers','B_updated_coverage','C_maintained_full_suite','D_strong_selection','E_SourceROI']


def select_strong(tasks,spec,traces):
    changed={c['document_id'] for c in spec['changes']}
    result=set()
    for task in tasks:
        refs={e['document_id'] for e in task.get('evidence',[])}
        history={p.split('#chunk')[0] for p in traces.get(task['id'],[])}
        topic=a.terms(task['question']+' '+task.get('category',''))
        topical=any(len(topic&a.terms(' '.join(c['removed_passages']+c['added_passages'])))>=2 for c in spec['changes'])
        if (refs|history)&changed or topical:result.add(task['id'])
    if spec['baseline_configuration']!=spec['candidate_configuration'] or any(c['kind']=='updated' and c['before_metadata']!=c['after_metadata'] for c in spec['changes']):
        result={t['id'] for t in tasks}
    return result


def verdict(name,rows,approval,unresolved,subset=False,confounded=False,conflict=False):
    if name=='A_updated_answers':failure=any(not r['correct'] for r in rows)
    elif name=='B_updated_coverage':failure=any(r['coverage'] is not None and r['coverage']<1 for r in rows)
    else:failure=any(not r['correct'] or r['coverage'] is not None and r['coverage']<1 for r in rows)
    if approval is None or unresolved:return 'REVIEW' # Same authority restriction for all methods.
    if failure:return 'BLOCK'
    if subset:return 'INCONCLUSIVE'
    if confounded or conflict:return 'REVIEW'
    return 'ACCEPT'


def main(output):
    output=Path(output)
    if output.exists():raise ValueError('Refusing to overwrite evidence')
    records=[];actual_executions=0
    with tempfile.TemporaryDirectory(prefix='fair-source-') as tmp:
        for name in SCENARIOS:
            before,after,spec,approval,callback=scenario(Path(tmp)/name,name)
            if approval is not None:
                intent={'expected_tasks':list(approval['expected_changes']),'protected_tasks':approval['protected_tasks'],'declared_by':approval['reviewer'],'rationale':approval['rationale']}
                spec=a.propose(before,after,intent=intent)
                approval=a.review(spec,**{k:approval[k] for k in ('reviewer','rationale','expected_changes','protected_tasks','expected_evidence')})
            tasks=a.load_benchmark(before);inputs=[{'id':t['id'],'question':t['question']} for t in tasks]
            start=time.perf_counter();old=callback(before,inputs);new=callback(after,inputs)
            paired_ms=(time.perf_counter()-start)*1000;actual_executions+=2*len(tasks)
            traces={r['id']:r['retrieved_chunk_ids'] for r in old['tasks']};newrows={r['id']:r for r in new['tasks']}
            _,chunks=a.inventory(after);expected=(approval or {}).get('expected_changes',{})
            reviewed=set(expected)|set((approval or {}).get('protected_tasks',[]))
            unresolved={r['task_id'] for r in spec['impact'] if r['potentially_affected']}-reviewed
            start=time.perf_counter();selected=select_strong(tasks,spec,traces);selection_ms=(time.perf_counter()-start)*1000
            scored=[]
            for task in tasks:
                revised=deepcopy(task)
                if task['id'] in expected:
                    revised.update(expected=expected[task['id']],accepted_answers=[expected[task['id']]],scoring='exact',evidence=approval['expected_evidence'][task['id']])
                row=newrows[task['id']]
                scored.append({'id':task['id'],'correct':grade(row['answer'],revised),'coverage':evidence_coverage(revised,row,chunks)})
            truth_affected={r['id'] for r in scored if not r['correct'] or r['coverage'] is not None and r['coverage']<1}|set(expected)
            srstart=time.perf_counter();sr=a.execute(before,after,spec,approval=approval,callback=callback,max_calls=2*len(tasks),max_seconds=10,persist=False)
            srms=(time.perf_counter()-srstart)*1000;actual_executions+=sr['execution']['calls']
            methods={}
            for method in METHODS:
                start=time.perf_counter()
                subset=[r for r in scored if r['id'] in selected] if method=='D_strong_selection' else scored
                prediction=sr['verdict'] if method=='E_SourceROI' else verdict(method,subset,approval,unresolved,
                    subset=method=='D_strong_selection' and len(selected)<len(tasks),
                    confounded=spec['baseline_configuration']!=spec['candidate_configuration'],conflict=bool(spec['potential_conflicts']))
                methods[method]={'verdict':prediction,'equivalent_task_executions':sr['execution']['calls'] if method=='E_SourceROI' else 2*len(subset),
                    'decision_overhead_ms':(time.perf_counter()-start)*1000,
                    'missed_affected_task_ids':sorted(truth_affected-selected) if method=='D_strong_selection' else [],
                    'manual_expected_answer_text_edits':len(expected) if method!='E_SourceROI' else sum(next((p['suggested_expected'] for p in spec['evaluation_proposals'] if p['task_id']==tid),None)!=value for tid,value in expected.items()),
                    'authority':'Identical explicit authored approval, expected answer revisions and reference revisions'}
            proposals=[p for p in spec['evaluation_proposals'] if p['suggested_expected'] is not None]
            gold={t['id']:expected.get(t['id'],t['expected']) for t in tasks} if approval else {}
            records.append({'scenario':name,'oracle':'BLOCK' if name in BLOCKING else 'REVIEW' if name in REVIEW else 'ACCEPT',
                'methods':methods,'authoritative_approval':approval,'approved_expected_changes':expected,'scored_tasks':scored,
                'strong_selected_tasks':sorted(selected),'all_affected_task_ids':sorted(truth_affected),'paired_application_ms':paired_ms,
                'strong_selector_ms':selection_ms,'source_roi_whole_workflow_ms':srms,
                'suggestions':{'review_items':len(proposals),'known_incorrect':sum(p['task_id'] in gold and p['suggested_expected']!=gold[p['task_id']] for p in proposals),
                    'unknown_intent':sum(p['task_id'] not in gold for p in proposals),'observed_human_corrections':None,
                    'authored_required_corrections_or_rejections':sum(p['task_id'] in gold and p['suggested_expected']!=gold[p['task_id']] for p in proposals)},
                'source_roi':sr})
    matrices={m:{truth:{pred:sum(r['oracle']==truth and r['methods'][m]['verdict']==pred for r in records) for pred in ('ACCEPT','BLOCK','REVIEW','INCONCLUSIVE')} for truth in ('ACCEPT','BLOCK','REVIEW')} for m in METHODS}
    result={'kind':'equivalent_authority_comparison','independently_validated':False,'fixtures':'13 previously exposed Codex-authored scenarios; regression validation only',
        'confusion_matrices':matrices,'actual_shared_callback_task_executions':actual_executions,'model_inference_calls':0,'external_spend_usd':0,
        'measurement_note':'A/B/C/D share actual paired outputs; per-method task counts are equivalent executions. D selection is replay-scored, not a separately timed end-to-end inference run. Timings are local deterministic overhead, not human time.',
        'human_time_saved':None,'maintenance_measurement_basis':'Label-edit counts are fixture-derived answer-field entries without prefill, not observed human actions. SourceROI still needs review of five suggestions including one known bad and one ambiguous. No total labor reduction is established.','scenarios':records}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'matrices':matrices,'output':str(output),'actual_callback_tasks':actual_executions},indent=2))
    return result

if __name__=='__main__':main(sys.argv[1])
