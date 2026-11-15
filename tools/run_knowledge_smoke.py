"""Four-call/60-second real local model smoke; no download or paid API path."""
import json
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from examples.knowledge_change.demo import workspace
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.assurance import propose,review,execute,markdown

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path('workspace/knowledge-local-smoke'))
parser.add_argument('--output',type=Path,default=Path('docs/artifacts/knowledge-local-smoke.json'))
args=parser.parse_args();root=args.root;output=args.output
if root.exists() or output.exists():raise SystemExit('Refusing to overwrite previous experiment')
reference=json.loads(Path('workspace/reliability-24/project.json').read_text())
for version,days in [('source',30),('candidate',14)]:
    cfg=workspace(root/version,days=days)
    p=root/version/'project.json';c=json.loads(p.read_text());c['model']=reference['model'];c['local_inference_manifest']=reference['local_inference_manifest']
    c['settings']['max_model_calls_per_run']=4;c['settings']['max_run_seconds']=60;p.write_text(json.dumps(c,indent=2))
    tasks=[{'id':'returns','question':'How many days is the return period (returns_days)? Answer with only the number.','expected':'30','evidence':[{'document_id':'policy::returns.json','quote':'30'}]},
           {'id':'warranty','question':'How many days is warranty coverage (warranty_days)? Answer with only the number.','expected':'365','evidence':[{'document_id':'policy::warranty.json','quote':'365'}]}]
    (root/version/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
freeze(read_config(root/'source'),root/'accepted');before=read_config(root/'accepted');after=read_config(root/'candidate')
spec=propose(before,after)
approval=review(spec,reviewer='authored smoke policy owner',rationale='Explicit synthetic policy fixture, not independently reviewed real business data',
 expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
result=execute(before,after,spec,approval=approval,max_calls=4,max_seconds=60)
result['validation_scope']='Previously authored two-task smoke; not held-out or independent business validation'
result['external_api_spend_usd']=0
result['normalization_contract']='string, finite JSON number, boolean; answer-only object remains supported but has no citation support claim'
result['citation_review_status']='pending; literal retrieved reference coverage is not citation entailment'
output.write_text(json.dumps(result,indent=2)+'\n');output.with_suffix('.md').write_text(markdown(result))
print(json.dumps({'verdict':result['verdict'],'reason':result['reason'],'execution':result['execution']},indent=2))
