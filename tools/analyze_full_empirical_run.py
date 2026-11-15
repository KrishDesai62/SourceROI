"""Read-only analysis of authorized actual traces. No providers or inference."""
import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.run_empirical_experiment import check_freeze,conventional,metrics
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.experiment import reconcile,audit_native_log
from sourceroi.live import assurance


def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False)


def analyze(benchmark,run,output):
    benchmark=Path(benchmark).resolve();run=Path(run).resolve();output=Path(output)
    if output.exists():raise ValueError('Choose a fresh analysis output')
    output.mkdir(parents=True);check_freeze(benchmark)
    result=json.loads((run/'results.json').read_text());audit=reconcile(run/'runtime')
    if audit['status']!='RECONCILED':raise ValueError('Native accounting is not reconciled')
    ci=json.loads((run/'data-ci.json').read_text());sr=json.loads((run/'strict-release.json').read_text())
    annotations=json.loads((benchmark/'frozen-labels.json').read_text())['annotations']
    labels={(a['version'],a['task_id']):a for a in annotations}
    native=[json.loads(l) for l in (run/'runtime/native-events.jsonl').read_text().splitlines()]
    dispatch=[r for r in native if r['event']=='dispatched'];cursor=0;all_evidence=[];phases={};contexts={};rawrows={}
    for phase in ('primary','data_ci'):
        phases[phase]={}
        for version,year in [('accepted',2024),('candidate',2025)]:
            cfg=read_config(benchmark/version);docs,chunks=scan_sources(cfg);known={c['id']:c for c in chunks}
            tasks=load_benchmark(cfg);taskmap={t['id']:t for t in tasks}
            rows=([json.loads((run/(version+'-'+t['id']+'.json')).read_text())['row'] for t in tasks]
                  if phase=='primary' else ci['baseline' if version=='accepted' else 'candidate']['tasks'])
            mapped={};byid={}
            for row in rows:
                task=taskmap[row['id']];label=labels.get((year,row['id']))
                evidence=[known[c] for c in row['retrieved_chunk_ids']]
                before_ids=(row.get('selection') or {}).get('before_grounding_ids',row['retrieved_chunk_ids'])
                item={'phase':phase,'version':year,'task_id':row['id'],'question':task['question'],'category':task['category'],
                      'original_frozen_expectation':task['expected'],'maintained_development_expectation':label['expected'] if label else task['expected'],
                      'actual_answer':row['actual'],'answer_origin':row.get('answer_origin'),'usage_source':row.get('usage_source'),
                      'citations':row.get('citations'),'invalid_citations':row.get('invalid_citations'),
                      'retrieved_evidence':evidence,'before_grounding_evidence':[known[c] for c in before_ids if c in known],
                      'grounding_precheck':row.get('grounding_precheck'),'row':row,'source_evidence_annotation':label,
                      'native_request_id':None,'raw_request':None,'raw_response':None}
                if row.get('usage_source')=='provider_reported':
                    event=dispatch[cursor];cursor+=1
                    requestpath=run/f'runtime/requests/{cursor:03d}-request.json';responsepath=run/f'runtime/requests/{cursor:03d}-response.json'
                    request=json.loads(requestpath.read_text());response=json.loads(responsepath.read_text());body=json.loads(response['body'])
                    assert hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()==row['request_shape_sha256']
                    assert body['choices'][0]['message']['content']==row['raw_response']
                    assert body['usage']['prompt_tokens']==row['prompt_tokens'] and body['usage']['completion_tokens']==row['completion_tokens']
                    item.update(native_request_id=event['request_id'],native_task_id=event['task_id'],raw_request=str(requestpath.relative_to(run)),raw_response=str(responsepath.relative_to(run)))
                all_evidence.append(item);mapped[row['id']]=evidence;byid[row['id']]=row
            maintained=deepcopy(tasks)
            for t in maintained:
                label=labels.get((year,t['id']))
                if label:t.update(expected=label['expected'],evidence=[{'document_id':'current::notice.pdf','quote':label['quote']}])
            timing=[r['model_latency_ms'] for r in rows if r.get('usage_source')=='provider_reported']
            phases[phase][version]={'metrics_against_maintained_labels':metrics(rows,maintained),
                'actual_generations':len(timing),'prompt_tokens':sum(r['prompt_tokens'] or 0 for r in rows),
                'completion_tokens':sum(r['completion_tokens'] or 0 for r in rows),'mean_generation_ms':statistics.mean(timing) if timing else None,
                'sum_generation_ms':sum(timing),'sum_retrieval_ms':sum(r.get('retrieval_latency_ms') or 0 for r in rows),
                'end_to_end_ms':sum(r.get('end_to_end_latency_ms') or 0 for r in rows),
                'software_abstention_ids':[r['id'] for r in rows if r.get('usage_source')!='provider_reported'],
                'human_semantic_review':None}
            if phase=='primary':contexts[version]=mapped;rawrows[version]=byid
    assert cursor==len(dispatch)==audit['dispatched_attempts']==18
    dump(output/'all-40-logical-task-traces.json',all_evidence)
    dump(output/'phase-metrics.json',phases)
    # Audit the actual prepared comparator's reference inputs. Do not rewrite its
    # result: publish a separately labelled input-parity replay with the same
    # unchanged conventional checker and exact references used by SourceROI.
    tasks=load_benchmark(read_config(benchmark/'accepted'));review=sr['review'];same_requirements=deepcopy(tasks)
    mismatches=[]
    for t in same_requirements:
        if t['id'] in review['expected_changes']:
            t.update(expected=review['expected_changes'][t['id']],evidence=review['expected_evidence'][t['id']])
        label=labels.get((2025,t['id']))
        original_conventional_refs=[{'document_id':'current::notice.pdf','quote':label['quote']}] if label else t.get('evidence',[])
        if original_conventional_refs!=t.get('evidence',[]):mismatches.append({'id':t['id'],'sourceroi_references':t.get('evidence',[]),'initial_conventional_references':original_conventional_refs})
    t0=time.perf_counter()
    parity=conventional(read_config(benchmark/'candidate'),same_requirements,list(rawrows['candidate'].values()),contexts['candidate'])
    parity_ms=(time.perf_counter()-t0)*1000
    sr_blocks={r['task_id'] for r in sr['tasks'] if not r['candidate_correct'] or r['grounding_checks']['citation_status']=='BLOCK'}
    cv_blocks={r['id'] for r in parity['tasks'] if r['status']=='BLOCK'}
    primary_cv_blocks={r['id'] for r in result['comparison']['candidate']['tasks'] if r['status']=='BLOCK'}
    reference_audit={'primary_as_run_reference_parity':'FAIL' if mismatches else 'PASS','mismatches':mismatches,
        'primary_as_run_sourceroi_blocks':sorted(sr_blocks),'primary_as_run_conventional_blocks':sorted(primary_cv_blocks),
        'supplementary_identical_requirement_replay':parity,'supplementary_replay_ms':parity_ms,
        'supplementary_sourceroi_blocked_ids':sorted(sr_blocks),'supplementary_conventional_blocked_ids':sorted(cv_blocks),
        'supplementary_detection_tie':sr_blocks==cv_blocks,
        'methodology':'Existing comparator unchanged. Only its input tasks are replayed offline with exactly the frozen original protected references and explicitly revised references actually used by SourceROI. Primary as-run comparison is not overwritten.',
        'independent_semantics':None,'human_effort_savings':None}
    dump(output/'comparison-input-parity-audit.json',reference_audit)
    plan=json.loads((benchmark/'change-plan.json').read_text())
    intended=set(review['expected_changes']);predicted={r['task_id'] for r in plan['impact'] if r['potentially_affected']}
    affected={'declared_changed_expectation_ids':sorted(intended),'predicted_affected_ids':sorted(predicted),'declared_update_coverage':len(intended&predicted)/len(intended),
        'independent_fact_dependency_precision':None,'limitation':'All ten tasks marked; intended answer changes are not an exhaustive semantic dependency oracle. Coverage 3/3 does not establish precise localization.'}
    dump(output/'impact-audit.json',affected)
    investigation=[]
    for phase in ('primary','data_ci'):
        for item in all_evidence:
            if item['phase']!=phase or item['task_id'] not in ('business','charity','depreciation'):continue
            label=item['source_evidence_annotation'];text='\n'.join(c['text'] for c in item['retrieved_evidence'])
            investigation.append({'phase':phase,'version':item['version'],'task_id':item['task_id'],'expected':item['maintained_development_expectation'],'actual':item['actual_answer'],
                'generation_executed':item['native_request_id'] is not None,'correct_quote_in_context':bool(label and label['quote'] in text),
                'medical_21_text_in_context':'21 cents per mile' in text,'raw_answer_json':item['row'].get('raw_response'),
                'citation_ids':item['citations'],'request_id':item['native_request_id'],
                'interpretation':'Observed association/predicate/year selection failure when support is present; causal attention/schema mechanism not demonstrated. No prompt/source/label changes or extra inference.'})
    dump(output/'failure-investigation.json',investigation)
    source_log=audit_native_log((run/'runtime/server.log').read_text(),18)
    assert source_log['generation_task_count']==18
    worker=json.loads((run/'runtime/worker-exit.json').read_text());ledger=json.loads((run/'runtime/authorization-ledger.json').read_text())
    assert ledger['state']=='closed' and len(ledger['attempts'])==18 and worker['elapsed_seconds']<90 and ledger['elapsed_seconds']<90
    summary={'status':'COMPLETED_AUTHORIZED_DEVELOPMENT_EXPERIMENT','native_accounting':audit,'native_process_seconds':worker['elapsed_seconds'],
        'authorization_session_seconds':ledger['elapsed_seconds'],'phases':phases,'primary_reference_parity':reference_audit['primary_as_run_reference_parity'],
        'same_requirement_comparison':'TIE' if sr_blocks==cv_blocks else 'DIFFERENCE_REQUIRES_REVIEW','impact':affected,
        'strict_release':sr['verdict'],'data_ci':ci['verdict'],'real_retries':0,'external_spend_usd':0,
        'independent_semantic_correctness':None,'customer_value':None,'extra_model_calls_for_analysis':0,
        'overall_answer_reliability':'FAIL','differentiated_detection_value':'NOT_DEMONSTRATED','independent_commercial_value':'INCONCLUSIVE'}
    dump(output/'summary.json',summary)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('benchmark','run','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(json.dumps(analyze(a.benchmark,a.run,a.output),indent=2))
