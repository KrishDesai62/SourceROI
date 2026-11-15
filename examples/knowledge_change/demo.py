"""Local external-agent callback demo. No models, network, credentials or spending.

The application reads its own knowledge files, not evaluation expected answers.
Replace external_agent with your application's read-only local callback.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.assurance import propose,review,execute,markdown


def workspace(root, *, days=30, warranty=365):
    root=Path(root);(root/'sources'/'policy').mkdir(parents=True)
    (root/'sources/policy/returns.json').write_text(json.dumps({'returns_days':days}))
    (root/'sources/policy/warranty.json').write_text(json.dumps({'warranty_days':warranty}))
    tasks=[{'id':'returns','question':'What is returns_days?','expected':'30','evidence':[{'document_id':'policy::returns.json','quote':'30'}]},
           {'id':'warranty','question':'What is warranty_days?','expected':'365','evidence':[{'document_id':'policy::warranty.json','quote':'365'}]}]
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
    (root/'project.json').write_text(json.dumps({'id':'knowledge-demo','name':'Knowledge demo','runner':'rag_chat',
        'sources':[{'id':'policy','name':'Policy','path':'sources/policy','authority':'Policy owner','scope':'US online purchases'}],
        'model':{'name':'deterministic-external-demo','base_url':'http://127.0.0.1:8788/v1','local_only':True},
        'settings':{'max_chunks':5,'chunk_chars':1100,'overlap_chars':100,'max_model_calls_per_run':40}}))
    return read_config(root)


def external_agent(cfg,tasks):
    """Existing application's answer function; receives question and ID only."""
    rows=[]
    for t in tasks:
        key=t['question'].split()[-1].rstrip('?');answer='Unknown';retrieved=[]
        for path in sorted((Path(cfg['_root'])/'sources/policy').glob('*.json')):
            data=json.loads(path.read_text())
            if key in data:
                answer=str(data[key]);retrieved=[f'policy::{path.name}#chunk0'];break
        rows.append({'id':t['id'],'answer':answer,'retrieved_chunk_ids':retrieved})
    return {'tasks':rows,'metrics':{'total_tokens':None,'mean_latency_ms':None,'total_cost_usd':None},
            'adapter_identity':'deterministic JSON application v1','not_model_inference':True}


def main(output):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new output directory')
    output.mkdir(parents=True)
    base=workspace(output/'source');freeze(base,output/'accepted')
    before=read_config(output/'accepted');after=workspace(output/'candidate',days=14)
    spec=propose(before,after)
    # This explicit demo policy-owner decision is not independent research annotation.
    approval=review(spec,reviewer='demo policy-owner fixture',rationale='Fixture intentionally changes returns; warranty remains protected',
        expected_changes={'returns':'14'},protected_tasks=['warranty'],
        expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    for name,obj in [('change',spec),('approval',approval)]:
        (output/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
    result=execute(before,after,spec,approval=approval,callback=external_agent,max_calls=4,max_seconds=10)
    (output/'release.json').write_text(json.dumps(result,indent=2)+'\n');(output/'release.md').write_text(markdown(result))
    print(json.dumps({'verdict':result['verdict'],'calls':result['execution']['calls'],'output':str(output)},indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
