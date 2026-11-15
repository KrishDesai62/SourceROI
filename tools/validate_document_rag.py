"""Bounded real document retrieval integration: 10 HTTP requests, zero model calls."""
import argparse
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from examples.knowledge_change.demo import workspace
from sourceroi.live import assurance as a
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.config import read_config
from sourceroi.live.provider import run_external,ProviderError


def make(root,days):
    workspace(root,days=days)
    shutil.rmtree(root/'sources')
    texts={'current':f'US online purchases: customers may return products within {days} days.',
        'archive':'Historical US policy: customers may return products within 30 days.',
        'regional':'EU retail purchases: customers may return products within 90 days.',
        'warranty':'US online purchases: warranty coverage lasts 365 days.'}
    sources=[]
    for sid,text in texts.items():
        folder=root/'sources'/sid;folder.mkdir(parents=True);(folder/'policy.txt').write_text(text)
        sources.append({'id':sid,'name':sid,'path':'sources/'+sid,'authority':'authored policy owner',
            'jurisdiction':'EU' if sid=='regional' else 'US','policy_scope':'online','effective_from':'2025-01-01' if sid!='archive' else '2010-01-01',**({'effective_to':'2020-01-01'} if sid=='archive' else {})})
    p=root/'project.json';obj=json.loads(p.read_text());obj['sources']=sources;p.write_text(json.dumps(obj,indent=2))
    tasks=[{'id':'returns','question':'What is the return period? Answer only the number.','expected':'30','scope':{'jurisdiction':'US','as_of':'2026-11-13','policy_scope':'online'},'evidence':[{'document_id':'current::policy.txt','quote':'30 days'}]},
        {'id':'warranty','question':'What is warranty coverage? Answer only the number.','expected':'365','scope':{'jurisdiction':'US','as_of':'2026-11-13','policy_scope':'online'},'evidence':[{'document_id':'warranty::policy.txt','quote':'365 days'}]}]
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')


def main(root,out):
    root=Path(root);out=Path(out)
    if root.exists() or out.exists():raise ValueError('Immutable evidence paths exist')
    start=time.monotonic()
    for name,days in [('source',30),('candidate',14),('regression',7)]:make(root/name,days)
    ranking=root/'ranking.json';ranking.write_text('{"ranking":"prefer_current"}')
    server=Path(__file__).resolve().parents[1]/'examples/document_rag/server.py'
    process=subprocess.Popen([sys.executable,'-u',str(server),'--root',str(root/'accepted'),'--root',str(root/'candidate'),'--root',str(root/'regression'),'--ranking-file',str(ranking)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    ready=queue.Queue();threading.Thread(target=lambda:ready.put(process.stdout.readline()),daemon=True).start();requests=0
    try:
        info=json.loads(ready.get(timeout=5))
        for name in ('source','candidate','regression'):
            p=root/name/'project.json';obj=json.loads(p.read_text());obj['agent']={'url':info['endpoint'],'api_key_env':'','protocol_version':2,'capabilities':[],'execution_identity':info['execution_identity'],'timeout_seconds':5};p.write_text(json.dumps(obj,indent=2))
        freeze(read_config(root/'source'),root/'accepted');before=read_config(root/'accepted')
        def callback(cfg,tasks):
            nonlocal requests
            docs,_=a.scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs};rows=[]
            for task in tasks:
                if requests>=12 or time.monotonic()-start>45:raise TimeoutError('Integration budget')
                requests+=1
                row=run_external(task['question'],[s['id'] for s in cfg['sources']],[],[],{**cfg,'agent':{**cfg['agent'],'knowledge_manifest':manifest}},task['id'])
                rows.append({'id':task['id'],**row})
            return {'tasks':rows,'metrics':{'tokens':None,'cost':None}}
        results=[]
        for name in ('candidate','regression'):
            after=read_config(root/name);spec=a.propose(before,after,intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'authored fixture owner','rationale':'Approved intended return answer is 14'})
            approval=a.review(spec,reviewer='authored fixture owner',rationale='Returns 14; warranty 365',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'current::policy.txt','quote':'14 days'}]})
            results.append(a.execute(before,after,spec,approval=approval,callback=callback,policy='strict_grounded',max_calls=4,max_seconds=15))
        after=read_config(root/'candidate');ranking.write_text('{"ranking":"prefer_archive"}')
        drift_rejected=False
        try:callback(after,[{'id':'drift','question':'What is the return period?'}])
        except ProviderError:drift_rejected=True
        ranking.write_text('{"ranking":"prefer_current"}');unknown_rejected=False
        requests+=1
        try:run_external('Return period?',list(s['id'] for s in after['sources']),[],[],{**after,'agent':{**after['agent'],'knowledge_manifest':{'current::policy.txt':'0'*64}}},'unknown')
        except ProviderError:unknown_rejected=True
        report={'kind':'document_rag_validation','authorship':'Codex-authored separate-process example, not independently developed or customer validated',
            'max_http_requests':12,'actual_http_requests':requests,'max_seconds':45,'elapsed_seconds':time.monotonic()-start,
            'model_calls':0,'external_spend_usd':0,'ranking_drift_rejected':drift_rejected,'unknown_version_rejected':unknown_rejected,'releases':results,
            'retrieval':'Actual lexical scoring over four overlapping/current/historical/regional policy documents; regex day-count extraction, not a semantic model'}
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
        for i,r in enumerate(results):out.with_name(out.stem+f'-{i}.md').write_text(a.markdown(r))
        print(json.dumps({'verdicts':[r['verdict'] for r in results],'drift_rejected':drift_rejected,'unknown_version_rejected':unknown_rejected,'requests':requests},indent=2))
        return report
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();main(args.root,args.output)
