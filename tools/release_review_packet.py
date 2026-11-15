"""Export real release outputs for external semantic/citation review; validate imports."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.reliability_review import packet,evaluate
from sourceroi.live.assurance import inventory,configuration
from sourceroi.live.data_ci import digest


def export(report,baseline,candidate):
    items=[]
    for stage,root in [('baseline',baseline),('candidate',candidate)]:
        cfg=read_config(root);docs,chunks=inventory(cfg)
        if digest(docs)!=report['versions'][stage+'_sources']:raise ValueError('Source version changed since release execution')
        tasks={t['id']:t for t in load_benchmark(cfg)}
        if report['versions'].get('test_set_version') is not None and digest(list(tasks.values()))!=report['versions']['test_set_version']:raise ValueError('Benchmark version changed since release execution')
        if report['versions'].get(stage+'_configuration') is not None and configuration(cfg)!=report['versions'][stage+'_configuration']:raise ValueError('Configuration changed since release execution')
        known={c['id']:c for c in chunks}
        for row in report.get(stage,{}).get('tasks',[]):
            if row['id'] not in tasks:raise ValueError('Unknown release task identity')
            task=tasks[row['id']]
            if row.get('question',task['question'])!=task['question']:raise ValueError('Release question differs from frozen benchmark')
            if stage=='candidate':
                checks=next((t.get('grounding_checks') for t in report.get('tasks',[]) if t['task_id']==row['id']),None)
                if checks:
                    items.append(packet(checks['sample']));continue
            selected=row['retrieved_chunk_ids']
            if any(cid not in known for cid in selected):raise ValueError('Report contexts do not match supplied corpus')
            metadata={s['id']:s for s in cfg['sources']}
            sample={'stage':stage,'question':task['question'],'answer':row.get('answer',row.get('actual')),
                'citations':row.get('citations',[]),'context':[{**known[cid],**{k:metadata[known[cid]['source_id']][k] for k in ('authority','jurisdiction','policy_scope','effective_from','effective_to') if k in metadata[known[cid]['source_id']]}} for cid in selected],
                'scope':task.get('scope',{}),
                'source_version':report['versions'][stage+'_sources'],'response_contract_valid':row.get('json_format_valid')}
            items.append(packet(sample))
    return {'kind':'external_release_review_packet','source_spec_id':report['spec_id'],'items':items,
        'version_binding':{'sources':'verified','benchmark':'verified' if report['versions'].get('test_set_version') is not None else 'not_recorded_in_legacy_report',
                           'configuration':'verified' if all(report['versions'].get(s+'_configuration') is not None for s in ('baseline','candidate')) else 'not_recorded_in_legacy_report'},
        'independently_reviewed':False,'instructions':'External reviewers inspect answer meaning, claim support, applicability and stale facts; complete every dimension and exact claim spans. Operator must verify independence. Missing reviews stay unknown.'}


def score(data,reviewers):
    results=[evaluate(item['sample'],item if item.get('status')=='complete' else None,allowed_reviewers=reviewers) for item in data['items']]
    complete=[r for r in results if r['review_status']=='complete']
    return {'kind':'reviewed_release_reliability','results':results,'completed':len(complete),'total':len(results),
        'verdict':'BLOCK' if any(not r['semantic_correctness'] or not r['citation_correctness'] or not r['scope_appropriate'] or r['uses_outdated_fact'] for r in complete) else 'REVIEW' if len(complete)<len(results) or not results else 'checks_passed',
        'semantic_correctness_rate':sum(r['semantic_correctness'] for r in complete)/len(complete) if complete else None,
        'citation_correctness_rate':sum(r['citation_correctness'] for r in complete)/len(complete) if complete else None,
        'independence_note':'External operator authorizes reviewers; identity/independence is not authenticated by this tool.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('export');e.add_argument('--report',type=Path,required=True);e.add_argument('--baseline',type=Path,required=True);e.add_argument('--candidate',type=Path,required=True)
    s=sub.add_parser('score');s.add_argument('--packet',type=Path,required=True);s.add_argument('--reviewers',type=Path,required=True,help='Operator-supplied JSON list of authorized external reviewer identities')
    for action in (e,s):action.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise SystemExit('Evidence destination exists')
    result=export(json.loads(args.report.read_text()),args.baseline,args.candidate) if args.command=='export' else score(json.loads(args.packet.read_text()),json.loads(args.reviewers.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'items':len(result.get('items',result.get('results',[]))),'verdict':result.get('verdict','pending')},indent=2))
