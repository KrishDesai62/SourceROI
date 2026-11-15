"""Local authored-fixture acceptance. No live models, independent humans or spend."""
import argparse
from copy import deepcopy
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
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources
from sourceroi.live import parser_boundary as parsers,assurance as assurance
from sourceroi.live.data_ci import freeze
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs
from sourceroi.live.fixture_execution import authorize
from sourceroi.live.semantic_store import SemanticStore
from sourceroi.live.workspace_recovery import backup,restore
from sourceroi.live.api import create_app


def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();cpu=time.process_time()
    with tempfile.TemporaryDirectory(prefix='phase3-authored-') as directory,patch('sourceroi.live.provider._post',side_effect=AssertionError('No network')):
        root=Path(directory);cfg=workspace(root/'project')
        larger=workspace(root/'larger')
        for i in range(20):(Path(larger['_root'])/'sources/policy'/f'bounded-{i}.txt').write_text(('Bounded development document sentence. '*100)+str(i))
        parsers._CACHE.clear();t=time.perf_counter();docs,chunks=scan_sources(larger);cold=1000*(time.perf_counter()-t)
        t=time.perf_counter();assert scan_sources(larger)==(docs,chunks);warm=1000*(time.perf_counter()-t)
        store=SecurityStore(cfg['_root'],initialize=True)
        for role in ('operator','reviewer'):store.add_user(role,'Development fixture password only',role)
        session=store.login('operator','Development fixture password only');actor=session['user'];reviewer=store.login('reviewer','Development fixture password only')['user']
        sid='a'*32;frozen=Path(cfg['_root'])/'.sourceroi/snapshots'/sid;freeze(cfg,frozen)
        (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"returns_days":14}')
        cfg=read_config(cfg['_root']);spec=assurance.propose(read_config(frozen),cfg);store.register_plan(spec,sid)
        review=assurance.review(spec,reviewer='reviewer',rationale='Authored fixture maintenance assertion, not a real human/independent judgment',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
        approval=store.bind_approval(review,reviewer);jobs=Jobs(store)
        permission=authorize(jobs,actor,spec,max_attempts=8,max_seconds=60)
        values={'baseline':{'returns':'30','warranty':'365'},'candidate':{'returns':'14','warranty':'365'}}
        j=jobs.submit(actor,'phase3-acceptance-fixture',spec,approval,operation='fixture_release',fixture_authorization=permission['id'],fixture_responses=values)
        t=time.perf_counter();result=jobs.run_one('phase3-acceptance-worker');elapsed=time.perf_counter()-t
        assert result['state']=='COMPLETED' and result['result']['verdict']=='REVIEW'
        reviews=SemanticStore(jobs);packet=reviews.packet(j['id'],'warranty');sample=packet['sample']
        claim={'start':0,'end':len(sample['answer']),'verdict':'supported','evidence':[{'id':sample['citations'][0],'quote':sample['context'][0]['text']}]}
        judgment=reviews.put(j['id'],'warranty',reviewer,binding=packet['binding'],decision='supported',claims=[claim],rationale='Authored fixture assertion only, not a human or independent semantic label',authorization_basis='Test role; external independence NOT verified',dimensions={'semantic_correctness':True,'citation_correctness':True,'scope_appropriate':True,'uses_outdated_fact':False})
        assessment=reviews.assess(j['id']);assert assessment['verdict']=='REVIEW' and not assessment['independence_verified_externally']
        latencies=[]
        with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
            for _ in range(20):
                t=time.perf_counter();response=client.get('/api/v2/jobs/'+j['id'],headers={'authorization':'Bearer '+session['token']});latencies.append(1000*(time.perf_counter()-t));assert response.status_code==200
        t=time.perf_counter();archive=backup(cfg['_root'],args.output/'complete-fixture-workspace.zip',quiesced=True);backup_ms=1000*(time.perf_counter()-t)
        t=time.perf_counter();recovered=restore(archive['archive'],args.output/'independent-restore',expected_sha256=archive['sha256']);restore_ms=1000*(time.perf_counter()-t)
        newstore=SecurityStore(recovered['workspace']);newjobs=Jobs(newstore);SemanticStore(newjobs)
        with newstore.connect() as c:counts={table:c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('users','sessions','approvals','jobs','fixture_authorizations','semantic_judgments')}
        assert all(v==0 for v in counts.values())
        with store.connect() as c:attempts=[dict(r) for r in c.execute('SELECT * FROM job_attempts WHERE job=? ORDER BY created,id',(j['id'],))]
        dump(args.output/'job-result.json',result);dump(args.output/'fixture-attempts.json',attempts);dump(args.output/'authored-semantic-judgment.json',judgment)
        measurements={'classification':'VERIFIED_INTERNAL_FIXTURE','platform':platform.platform(),'python':platform.python_version(),
            'ingestion':{'documents':len(docs),'chunks':len(chunks),'cold_ms':cold,'immutable_cache_ms':warm,'supervision':'macOS scoped profile + process steward + CPU/file/fd limits + sampled RSS'},
            'execution':{'worker_seconds':elapsed,'provider_fixture_attempts':len(attempts),'fixture_reported_prompt_tokens':sum(json.loads(a['usage'])['prompt_tokens'] for a in attempts),'fixture_reported_completion_tokens':sum(json.loads(a['usage'])['completion_tokens'] for a in attempts),'verdict':'REVIEW','real_model_generations':0,'external_spend_usd':0},
            'api':{'requests':20,'transport':'in-process TestClient','median_ms':statistics.median(latencies),'max_ms':max(latencies)},
            'backup':archive,'restore':recovered,'backup_ms':backup_ms,'restore_ms':restore_ms,'restored_active_counts':counts,
            'semantic_assessment':assessment,'whole_probe_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'limitations':'Authored fixtures and synthetic usage. No customer throughput, independent semantics, real model performance, RPO/RTO, security certification or browser automation.'}
        dump(args.output/'measurements.json',measurements)
        print(json.dumps({k:v for k,v in measurements.items() if k in ('ingestion','execution','api','backup_ms','restore_ms','restored_active_counts','whole_probe_seconds','peak_rss_bytes')},indent=2))
if __name__=='__main__':main()
