"""Reproducible authored offline development comparison; zero model calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.knowledge_decision import run,binary_metrics


def workspace(root,*,changed=False,conflict=False,unsupported=False):
    root=Path(root);root.mkdir(parents=True)
    for sid in ('policy','warranty','duplicate','conflict'):(root/'sources'/sid).mkdir(parents=True)
    (root/'sources/policy/returns.txt').write_text('Returns period is 30 days.\n')
    (root/'sources/warranty/warranty.txt').write_text('Warranty duration is 365 days.\n')
    (root/'sources/duplicate/returns-copy.txt').write_text('Returns period is 30 days.\n')
    tasks=[{'id':'returns','question':'What is the returns period?','expected':'30',
        'behavior_constraint':'protected','evidence':[{'document_id':'policy::returns.txt','quote':'Returns period is 30 days.'}]},
        {'id':'warranty','question':'What is the warranty duration?','expected':'365','behavior_constraint':'protected',
        'evidence':[{'document_id':'warranty::warranty.txt','quote':'Warranty duration is 365 days.'}]},
        {'id':'combined','question':'What are the returns period and warranty duration together?','expected':'30 and 365',
        'evidence':[{'document_id':'policy::returns.txt','quote':'Returns period is 30 days.'},
                    {'document_id':'warranty::warranty.txt','quote':'Warranty duration is 365 days.'}]}]
    if unsupported:tasks.append({'id':'unsupported','question':'What is the lunar insurance coverage?','expected':'INSUFFICIENT_EVIDENCE','evidence':[]})
    for t in tasks:t.update(split='development',review_status='codex_authored_development',reviewer='')
    (root/'benchmark.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in tasks))
    config={'id':'decision-fixture','name':'Authored offline decision fixture','sources':[{'id':sid,'path':'sources/'+sid,'authority':'Authored development fixture'} for sid in ('policy','warranty','duplicate','conflict')],
        'model':{'name':'DISABLED','base_url':'http://127.0.0.1:1/v1','local_only':True},'settings':{'max_chunks':8,'chunk_chars':1000,'overlap_chars':0}}
    (root/'project.json').write_text(json.dumps(config,indent=2)+'\n')
    cfg=read_config(root);snapshot='a'*32;frozen=root/'.sourceroi/snapshots'/snapshot;freeze(cfg,frozen)
    if changed:
        (root/'sources/policy/returns.txt').write_text('Returns period is 14 days.\n')
        (root/'sources/duplicate/returns-copy.txt').write_text('Returns period is 14 days.\n')
    if conflict:(root/'sources/conflict/disagreement.txt').write_text('Returns period is 99 days.\n')
    request={'snapshot_id':snapshot,'alternatives':[
        {'name':'without_duplicate','corpus':'baseline','exclude_sources':['duplicate']},
        {'name':'without_policy','corpus':'baseline','exclude_sources':['policy']},
        {'name':'without_warranty','corpus':'baseline','exclude_sources':['warranty']},
        {'name':'without_both','corpus':'baseline','exclude_sources':['policy','warranty']},
        {'name':'updated','corpus':'candidate'},
        {'name':'top_one','corpus':'baseline','policy':{'name':'top_k','k':1}}]}
    return read_config(frozen),read_config(root),request


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);summaries=[]
    for name,kwargs in [('redundant',{}),('changed',{'changed':True}),('conflicting',{'conflict':True}),('missing_labels',{'unsupported':True})]:
        old,new,request=workspace(args.output/name,**kwargs)
        expected_recommendations={'policy':'KEEP','warranty':'KEEP','duplicate':'UPDATE' if kwargs.get('changed') else 'REVIEW' if kwargs.get('conflict') or kwargs.get('unsupported') else 'REMOVE','conflict':'REVIEW'}
        actual={'returns','combined'} if kwargs.get('changed') or kwargs.get('conflict') else set()
        reference_losses={'returns','combined'} if kwargs.get('changed') else set()
        expected_flags=actual|({'unsupported'} if kwargs.get('unsupported') else set())
        protocol={'label_origin':'Codex-authored exposed development only','expected_affected_tasks':sorted(actual),
            'expected_reference_losses':sorted(reference_losses),'expected_evidence_flags':sorted(expected_flags),
            'expected_recommendations':expected_recommendations,'request':request,
            'frozen_snapshot':json.loads((Path(old['_root'])/'snapshot.json').read_text()),
            'candidate_source_sha256':{str(p.relative_to(Path(new['_root']))):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in (Path(new['_root'])/'sources').rglob('*.txt')}}
        protocol['hash']=digest(protocol)
        (args.output/name/'development-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
        report=run(old,new,request);(args.output/(name+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
        updated=next(e for e in report['experiments'] if e['name']=='updated')
        predictions=report['impact_prediction']['predicted_tasks']
        # These are independently specified relative to this invocation's outputs,
        # but authored by Codex, exposed development labels, NOT independent review.
        detection=updated['conventional']['failed_reference_tasks']
        summaries.append({'case':name,'label_origin':'Codex-authored exposed development expectations, frozen before run',
            'independent_heldout':False,'expected_affected_tasks':sorted(actual),
            'source_roi_verdict':updated['verdict'],'conventional_verdict':updated['conventional']['verdict'],
            'reference_loss_detection_metrics':binary_metrics(detection,reference_losses,[t['task_id'] for t in updated['tasks']]),
            'evidence_flag_detection_metrics':binary_metrics(set(detection)|set(updated['conventional']['uncertain_tasks']),expected_flags,[t['task_id'] for t in updated['tasks']]),
            'impact_metrics':binary_metrics(predictions,actual,[t['task_id'] for t in updated['tasks']]),
            'recommendations':{r['id']:r['recommendation'] for r in report['recommendations']},
            'recommendation_development_expectations':expected_recommendations,
            'recommendation_matches':sum(r['recommendation']==expected_recommendations[r['id']] for r in report['recommendations']),
            'recommendation_count':len(report['recommendations']),
            'unsupported_removal_proposals':sum(r['recommendation']=='REMOVE' and expected_recommendations[r['id']]!='REMOVE' for r in report['recommendations']),
            'estimated_context_deltas':{e['name']:e['delta_estimated_context_tokens'] for e in report['experiments']},
            'overhead':report['overhead'],'answer_accuracy':None,'unsupported_answer_rejection':None,
            'actual_token_savings':None,'acceptable_answer_quality_savings':None,'developer_effort':None,
            'extra_detection_over_conventional':0})
    result={'classification':'AUTHORED_OFFLINE_DEVELOPMENT_RETRIEVAL_ONLY','cases':summaries,
        'real_model_generations':0,'external_spend_usd':0,'differentiated_technical_value':'Not established; conventional detection ties. Traceable decisions/interventions implemented; independent effort benefit pending.'}
    result['content_hash']=digest(result)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
