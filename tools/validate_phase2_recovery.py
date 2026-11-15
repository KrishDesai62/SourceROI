"""Reproducible internal offline job + complete recovery acceptance probe.

Temporary development identities and source fixtures. Never dispatches a model.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from examples.knowledge_change.demo import workspace
from sourceroi.live import assurance as a,db
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs
from sourceroi.live.workspace_recovery import backup,restore,identities


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();cpu=time.process_time()
    with tempfile.TemporaryDirectory() as tmp,patch('sourceroi.live.engine.run_chat',side_effect=AssertionError('No inference')):
        cfg=workspace(Path(tmp)/'authored-workspace');store=SecurityStore(cfg['_root'],initialize=True)
        for role in ('operator','reviewer'):store.add_user(role,'Development-only fixture password',role)
        actor=store.login('operator','Development-only fixture password')['user'];reviewer=store.login('reviewer','Development-only fixture password')['user']
        sid='a'*32;snapshot=Path(cfg['_root'])/'.sourceroi/snapshots'/sid;freeze(cfg,snapshot)
        (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days":14}')
        cfg=read_config(cfg['_root']);spec=a.propose(read_config(snapshot),cfg);store.register_plan(spec,sid)
        review=a.review(spec,reviewer='reviewer',rationale='Authored development acceptance, not independent human',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
        approval=store.bind_approval(review,reviewer);jobs=Jobs(store)
        t=time.perf_counter();job=jobs.submit(actor,'acceptance-request-0001',spec,approval);submit_ms=1000*(time.perf_counter()-t)
        t=time.perf_counter();duplicate=jobs.submit(actor,'acceptance-request-0001',spec,approval);duplicate_ms=1000*(time.perf_counter()-t)
        assert duplicate['id']==job['id']
        t=time.perf_counter();completed=jobs.run_one('acceptance-worker-0001');worker_ms=1000*(time.perf_counter()-t)
        assert completed['state']=='COMPLETED' and completed['result']['verdict']=='INCONCLUSIVE'
        rid=db.begin(cfg,'fixture_release_history',[]);db.finish(cfg,rid,{'verdict':'REVIEW','kind':'authored_offline_history','generation_attempts':0})
        t=time.perf_counter();b=backup(cfg['_root'],args.output/'complete-workspace.zip',quiesced=True);backup_ms=1000*(time.perf_counter()-t)
        t=time.perf_counter();r=restore(b['archive'],args.output/'independent-restore',expected_sha256=b['sha256']);restore_ms=1000*(time.perf_counter()-t)
        target=read_config(r['workspace']);assert identities(target['_root'])==identities(cfg['_root'])
        assert db.get(target,rid)['report']==db.get(cfg,rid)['report']
        newstore=SecurityStore(target['_root']);newjobs=Jobs(newstore)
        assert newjobs.claim('restored-worker-0001') is None
        with newstore.connect() as c:counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ('users','sessions','approvals','jobs')}
        oldevents=jobs.events(job['id'])
        t=time.perf_counter();jobs.recover();recovery_scan_ms=1000*(time.perf_counter()-t)
        result={'classification':'VERIFIED_INTERNAL_FIXTURE','new_model_generations':0,'external_spend_usd':0,'job':completed,'events':oldevents,
                'backup':b,'restore':r,'restored_active_security_counts':counts,'restored_history_equal':True,
                'timing_ms':{'submit':submit_ms,'duplicate_lookup':duplicate_ms,'worker_offline_preflight':worker_ms,'backup':backup_ms,'restore':restore_ms,'terminal_recovery_scan':recovery_scan_ms},
                'whole_probe_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,
                'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
                'limitations':'Tiny authored local fixture, not production RPO/RTO, provider dispatch or real model validation. Quiescence assumes stopped external writers.'}
        (args.output/'acceptance-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k in ('classification','timing_ms','restored_active_security_counts','new_model_generations','whole_probe_seconds','peak_rss_bytes')},indent=2))
if __name__=='__main__':main()
