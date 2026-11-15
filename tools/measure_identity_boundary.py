"""Bounded internal HTTP/identity workload; no model, sockets, or customer data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import resource
import statistics
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from fastapi.testclient import TestClient
from examples.knowledge_change.demo import workspace
from sourceroi.live.api import create_app
from sourceroi.live.security import SecurityStore


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    start=time.perf_counter();cpu=time.process_time()
    with tempfile.TemporaryDirectory() as tmp:
        cfg=workspace(Path(tmp)/'fixture');store=SecurityStore(cfg['_root'],initialize=True)
        password='Authored internal benchmark password';store.add_user('fixture',password,'viewer')
        logins=[]
        for _ in range(5):
            t=time.perf_counter();session=store.login('fixture',password);logins.append(1000*(time.perf_counter()-t))
        with patch('sourceroi.live.engine.run_chat',side_effect=AssertionError('No model dispatch')):
            with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
                def request(_):
                    t=time.perf_counter();response=client.get('/api/v2/runs?limit=10',headers={'authorization':'Bearer '+session['token']})
                    return {'ms':1000*(time.perf_counter()-t),'status':response.status_code}
                t=time.perf_counter()
                with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(request,range(40)))
                elapsed=time.perf_counter()-t
        with store.connect() as conn:audit_count=conn.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    durations=sorted(r['ms'] for r in results)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={'classification':'VERIFIED_INTERNAL_FIXTURE','platform':platform.platform(),'python':platform.python_version(),
        'transport':'in-process TestClient ASGI; not network/TLS/load certification','concurrency':8,'requests':40,
        'status_counts':{str(s):sum(r['status']==s for r in results) for s in {r['status'] for r in results}},
        'request_latency_ms':{'median':statistics.median(durations),'p95':durations[37],'max':max(durations)},
        'requests_per_second':40/elapsed,'http_workload_seconds':elapsed,
        'scrypt_login_ms':{'n':5,'median':statistics.median(logins),'max':max(logins)},'audit_rows':audit_count,
        'whole_probe_seconds':time.perf_counter()-start,'whole_probe_cpu_seconds':time.process_time()-cpu,
        'process_peak_rss_bytes':peak if sys.platform=='darwin' else peak*1024,
        'new_model_generations':0,'spend_usd':0,'limits':'Small authenticated history reads, not customer workloads, parser or generation throughput.'}
    if result['status_counts']!={'200':40}:raise RuntimeError('Workload failed: '+json.dumps(result))
    with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
