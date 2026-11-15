"""Bounded local HTTP application integration; no models or paid APIs."""
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
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.provider import run_external,ProviderError


def main(root,output):
    root=Path(root);output=Path(output)
    if root.exists() or output.exists():raise ValueError('Evidence destinations exist')
    start=time.monotonic();source=workspace(root/'source');good=workspace(root/'candidate',days=14)
    bad=workspace(root/'regression',days=14,warranty=1)
    server=Path(__file__).resolve().parents[1]/'examples/external_record_rag/server.py'
    process=subprocess.Popen([sys.executable,'-u',str(server),'--baseline',str(root/'accepted'),'--candidate',str(root/'candidate'),'--candidate',str(root/'regression')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    ready=queue.Queue();threading.Thread(target=lambda:ready.put(process.stdout.readline()),daemon=True).start()
    http_calls=0
    try:
        endpoint=ready.get(timeout=5).strip()
        if not endpoint.startswith('http://127.0.0.1:'):raise ValueError('Local server did not start')
        for cfg in (source,good,bad):
            p=Path(cfg['_root'])/'project.json';obj=json.loads(p.read_text());obj['model']['name']='separate-record-rag-v1'
            obj['agent']={'url':endpoint,'protocol_version':2,'capabilities':[],'api_key_env':'','timeout_seconds':5}
            p.write_text(json.dumps(obj,indent=2))
        source=read_config(root/'source');good=read_config(root/'candidate');bad=read_config(root/'regression')
        freeze(source,root/'accepted');baseline=read_config(root/'accepted')
        def callback(cfg,tasks):
            nonlocal http_calls
            rows=[];docs,_=a.scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
            adapter={**cfg,'agent':{**cfg['agent'],'knowledge_manifest':manifest}}
            for task in tasks:
                if http_calls>=10 or time.monotonic()-start>45:raise TimeoutError('HTTP validation cap')
                http_calls+=1
                response=run_external(task['question'],['policy'],[],[],adapter,task['id'])
                rows.append({'id':task['id'],**response})
            return {'tasks':rows,'metrics':{'total_tokens':None,'total_cost_usd':None},'adapter_identity':'existing HTTP v2 with optional version/manifest checks'}
        results=[]
        for cfg in (good,bad):
            spec=a.propose(baseline,cfg)
            approval=a.review(spec,reviewer='authored application fixture owner',rationale='Returns changes to 14; warranty stays 365',
                expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
            result=a.execute(baseline,cfg,spec,approval=approval,callback=callback,max_calls=4,max_seconds=20)
            results.append(result)
        wrong_manifest={'policy::returns.json':'0'*64}
        stale_rejected=False
        try:
            http_calls+=1
            run_external('What is returns_days?',['policy'],[],[],{**good,'agent':{**good['agent'],'knowledge_manifest':wrong_manifest}},'wrong-version')
        except ProviderError:stale_rejected=True
        report={'kind':'external_record_rag_integration','validation_level':'Separate-process code implementation authored by Codex, not independently authored customer software',
            'max_http_requests':10,'actual_http_requests':http_calls,'max_seconds':45,'elapsed_seconds':time.monotonic()-start,
            'external_spend_usd':0,'model_inference_calls':0,'release_results':results,'unknown_version_rejected':stale_rejected,
            'proof_scope':'Application rereads registered files, computes normalized content hashes, selects requested version, returns manifest and actual retrieval IDs. Client checks version, manifest and trace membership. Not protection against a dishonest server.',
            'server_code_sha256':__import__('hashlib').sha256(server.read_bytes()).hexdigest()}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
        for i,r in enumerate(results):output.with_name(output.stem+f'-release-{i}.md').write_text(a.markdown(r))
        print(json.dumps({'verdicts':[r['verdict'] for r in results],'http_requests':http_calls,'wrong_version_rejected':stale_rejected},indent=2))
        return report
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();main(args.root,args.output)
