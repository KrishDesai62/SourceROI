"""Authored deterministic scenario checks; not independent model/customer validation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from examples.knowledge_change.demo import workspace, external_agent
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,evidence_coverage
from sourceroi.live.grade import grade

SCENARIOS=['legitimate_change','numerical_change','protected_regression','outdated_policy','effective_date',
           'essential_removed','redundant_removed','contradiction','multi_source','ranking_change',
           'correct_without_support','new_content_new_dependency','ambiguous_intent']
# Author-defined oracle, separate from agent response. NOT independently reviewed labels.
BLOCKING={'protected_regression','outdated_policy','essential_removed','contradiction','multi_source',
          'ranking_change','correct_without_support','new_content_new_dependency'}
REVIEW={'effective_date','ambiguous_intent'}


def scenario(root,name):
    source=workspace(root/'source')
    if name=='multi_source':
        p=root/'source/benchmark.jsonl'
        with p.open('a') as f:f.write(json.dumps({'id':'bundle','question':'What are returns_days and warranty_days together?', 'expected':'30/365','evidence':[{'document_id':'policy::returns.json','quote':'30'},{'document_id':'policy::warranty.json','quote':'365'}]})+'\n')
    if name=='redundant_removed':
        (root/'source/sources/policy/z_redundant.json').write_text('{"returns_days":30}')
    freeze(source,root/'baseline');before=read_config(root/'baseline')
    shutil.copytree(root/'source',root/'candidate');after=read_config(root/'candidate')
    folder=root/'candidate/sources/policy'
    if name in ('legitimate_change','numerical_change','outdated_policy','ambiguous_intent'):
        (folder/'returns.json').write_text(json.dumps({'returns_days':45 if name=='numerical_change' else 14}))
    if name=='protected_regression':(folder/'warranty.json').write_text('{"warranty_days":1}')
    if name in ('essential_removed','correct_without_support'):(folder/'returns.json').unlink()
    if name=='redundant_removed':(folder/'z_redundant.json').unlink()
    if name in ('contradiction','ranking_change','new_content_new_dependency'):
        (folder/'aa_new.json').write_text('{"warranty_days":7}')
    if name=='multi_source':(folder/'warranty.json').unlink()
    if name=='effective_date':
        p=root/'candidate/project.json';obj=json.loads(p.read_text());obj['sources'][0]['effective_date']='2030-01-01';p.write_text(json.dumps(obj));after=read_config(root/'candidate')
    if name=='ranking_change':
        p=root/'candidate/project.json';obj=json.loads(p.read_text());obj['settings']['max_chunks']=1;p.write_text(json.dumps(obj));after=read_config(root/'candidate')
    def callback(cfg,tasks):
        result=external_agent(cfg,tasks)
        if name=='multi_source':
            for row in result['tasks']:
                if row['id']=='bundle':
                    values=[];retrieved=[]
                    for filename,key in [('returns.json','returns_days'),('warranty.json','warranty_days')]:
                        path=Path(cfg['_root'])/'sources/policy'/filename
                        values.append(str(json.loads(path.read_text())[key]) if path.exists() else 'Unknown')
                        if path.exists():retrieved.append('policy::'+filename+'#chunk0')
                    row.update(answer='/'.join(values),retrieved_chunk_ids=retrieved)
        if name=='correct_without_support' and cfg['_root']==after['_root']:
            for r in result['tasks']:
                if r['id']=='returns':r['answer']='30' # explicitly simulates prior knowledge
        if name=='outdated_policy' and cfg['_root']==after['_root']:
            for r in result['tasks']:
                if r['id']=='returns':r['answer']='30' # explicitly simulates stale interpretation
        return result
    spec=a.propose(before,after)
    expected={'returns':'45' if name=='numerical_change' else '14'} if name in ('legitimate_change','numerical_change','outdated_policy') else {}
    refs={'returns':[{'document_id':'policy::returns.json','quote':expected['returns']}]} if expected else {}
    approval=None if name in REVIEW else a.review(spec,reviewer='authored scenario oracle',rationale='Deterministic engineering fixture decision; not independent validation',
          expected_changes=expected,protected_tasks=['warranty'] if expected else ['returns','warranty']+(['bundle'] if name=='multi_source' else []),expected_evidence=refs)
    return before,after,spec,approval,callback


def main(output):
    output=Path(output)
    if output.exists():raise ValueError('Existing evidence must not be overwritten')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='knowledge-validation-') as temp:
        for name in SCENARIOS:
            start=time.perf_counter();before,after,spec,approval,callback=scenario(Path(temp)/name,name)
            tasks=a.load_benchmark(before);inputs=[{'id':t['id'],'question':t['question']} for t in tasks]
            old=callback(before,inputs);new=callback(after,inputs)
            oldrows={r['id']:r for r in old['tasks']};newrows={r['id']:r for r in new['tasks']}
            _,oldchunks=a.inventory(before);_,newchunks=a.inventory(after)
            failed={t['id'] for t in tasks if grade(oldrows[t['id']]['answer'],t) and not grade(newrows[t['id']]['answer'],t)}
            coverage={t['id'] for t in tasks if evidence_coverage(t,newrows[t['id']],newchunks)<evidence_coverage(t,oldrows[t['id']],oldchunks)}
            changed={c['document_id'] for c in spec['changes']}
            simple={t['id'] for t in tasks if any(e['document_id'] in changed for e in t['evidence'])}
            report=a.execute(before,after,spec,approval=approval,callback=callback,max_calls=2*len(tasks),max_seconds=10,persist=False)
            actualaffected=failed|coverage|({'returns'} if name in ('legitimate_change','numerical_change','outdated_policy') else set())
            selected={i['task_id'] for i in spec['impact'] if i['potentially_affected']}
            updates=[p for p in spec['evaluation_proposals'] if p['suggested_expected'] is not None]
            expected=(approval or {}).get('expected_changes',{})
            known_expected={t['id']:expected.get(t['id'],t['expected']) for t in tasks} if name not in REVIEW else {}
            correct=sum(p['suggested_expected']==known_expected.get(p['task_id']) for p in updates)
            incorrect=sum(p['task_id'] in known_expected and p['suggested_expected']!=known_expected[p['task_id']] for p in updates)
            baseline_verdicts={'A_answer_regression':'BLOCK' if failed else 'ACCEPT',
                'B_reference_coverage':'BLOCK' if coverage else 'ACCEPT',
                'C_diff_full_regression':'BLOCK' if failed else 'ACCEPT',
                'D_reference_selection':'BLOCK' if failed&simple else 'ACCEPT', 'SourceROI':report['verdict']}
            repair_result=None
            if name=='essential_removed':
                repaired=workspace(Path(temp)/name/'repair');rspec=a.propose(before,repaired)
                rapproval=a.review(rspec,reviewer='authored scenario oracle',rationale='Restore original fixture knowledge',protected_tasks=['returns','warranty'])
                repair_result=a.verify_repair(before,after,spec,repaired,rspec,approval=approval,repair_approval=rapproval,callback=callback,max_calls=8,max_seconds=10)
            rows.append({'scenario':name,'oracle':'BLOCK' if name in BLOCKING else 'REVIEW' if name in REVIEW else 'ACCEPT',
                'verdicts':baseline_verdicts,'affected_task_oracle':sorted(actualaffected),
                'missed_affected_tasks':{'SourceROI':sorted(actualaffected-selected),'D_reference_selection':sorted(actualaffected-simple)},
                'evaluation_calls':{'A_answer_regression':2*len(tasks),'B_reference_coverage':2*len(tasks),'C_diff_full_regression':2*len(tasks),'D_reference_selection':2*len(simple),'SourceROI':report['execution']['calls']},
                'proposed_update_count':len(updates),'proposed_updates_matching_authored_oracle':correct,
                'known_incorrect_proposals':incorrect,'unknown_intent_proposals':sum(p['task_id'] not in known_expected for p in updates),
                'manual_correction_or_review_count':len(updates)-correct,
                'localization_candidates':{r['task_id']:r['candidate_causes'] for r in report['tasks']},
                'repair_verified':repair_result and repair_result['restored_registered_suite'],
                'wall_seconds_including_all_comparators':round(time.perf_counter()-start,6), 'report':report})
    confusion={}
    for method in rows[0]['verdicts']:
        confusion[method]={truth:{pred:sum(r['oracle']==truth and r['verdicts'][method]==pred for r in rows) for pred in ('ACCEPT','BLOCK','REVIEW','INCONCLUSIVE')} for truth in ('ACCEPT','BLOCK','REVIEW')}
    result={'kind':'knowledge_assurance_deterministic_validation','scenario_count':len(rows),
        'validation_level':'Authored deterministic engineering fixtures; no independent annotation, unseen held-out or real-model claim.',
        'development_final_separation':'These fixtures are exposed regression scenarios. Independent document-disjoint final validation remains unfinished.',
        'external_spend_usd':0,'model_inference_calls':0,'actual_callback_task_executions':sum(2*r['evaluation_calls']['SourceROI'] for r in rows)+8,
        'call_accounting_note':'A/B/C/D reuse the same baseline/candidate outputs. Per-method counts are equivalent task executions, not separately executed LLM calls. SourceROI executes its own pair; the repair adds eight callback task executions.','human_time_saved':None,'confusion_matrices':confusion,'scenarios':rows,
        'limitations':['Callbacks are deterministic JSON applications, not LLMs.','Baseline C is a source diff plus ordinary old-label full rerun; a human-maintained C can avoid the same false alarms.',
                      'Baseline D uses annotated dependencies; stronger lexical selection may match SourceROI.',
                      'SourceROI uses explicit authored approval decisions unavailable to unmaintained baselines. Benefit is reviewed workflow, not superior detection.',
                      'Candidate localization is a heuristic list; top-1/top-3 accuracy not independently adjudicated.',
                      'Thirteen small scenarios are not a statistical estimate of customer failure rates.']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'scenarios':len(rows),'confusion_matrices':confusion,'model_calls':0,'output':str(output)},indent=2))
    return result

if __name__=='__main__':main(sys.argv[1])
