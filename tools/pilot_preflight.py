"""Offline registered-index mapping check. Never imports/calls customer code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.data_ci import digest


def registration(project):
    cfg=read_config(project);docs,chunks=scan_sources(cfg);tasks=load_benchmark(cfg)
    if not docs or not chunks or not tasks:raise ValueError('Register nonempty sources and frozen evaluation tasks before preflight')
    return cfg,{'knowledge_manifest':{d['id']:d['fingerprint'] for d in docs},
        'passages':{c['id']:hashlib.sha256(c['text'].encode()).hexdigest() for c in chunks},
        'configuration_version':cfg['_config_hash'],'task_version':digest(tasks)}


def template(project):
    cfg,registered=registration(project)
    return {'version':1,'adapter':'YOUR_MODULE:YOUR_FUNCTION','protocol':'callback_v1',
        'configuration_version':registered['configuration_version'],'task_version':registered['task_version'],
        'knowledge_manifest':None,'knowledge_version':None,'passages':None,
        'execution_identity':cfg.get('agent',{}).get('execution_identity'),
        'instructions':'Fill manifest/version/passages from an offline export of the actual application index. Do not echo requested values as proof. No application is called by this tool.'}


def preflight(project,mapping):
    cfg,registered=registration(project)
    if not isinstance(mapping,dict) or mapping.get('version')!=1:raise ValueError('Mapping must be a version-1 object')
    if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*',mapping.get('adapter','')) or mapping.get('adapter')=='YOUR_MODULE:YOUR_FUNCTION':raise ValueError('Set adapter to your MODULE:FUNCTION; preflight does not import it')
    if mapping.get('protocol') not in ('callback_v1','http_v2'):raise ValueError('Use callback_v1 or http_v2')
    if mapping['protocol']=='http_v2' and (cfg.get('runner')!='http_agent' or cfg.get('agent',{}).get('protocol_version')!=2):raise ValueError('HTTP mapping requires registered runner=http_agent and agent.protocol_version=2')
    identity=cfg.get('agent',{}).get('execution_identity')
    if identity is not None and (not isinstance(identity,dict) or set(identity)!={'model','prompt','retrieval'} or any(not isinstance(v,str) or not v.strip() for v in identity.values())):raise ValueError('Registered execution_identity must bind model, prompt and retrieval strings')
    for key in ('configuration_version','task_version','knowledge_manifest','passages'):
        if mapping.get(key)!=registered[key]:raise ValueError(key+' mismatch or missing: export the actual index for this exact frozen registration; do not change hashes to conceal drift')
    if mapping.get('knowledge_version')!=digest(registered['knowledge_manifest']):raise ValueError('knowledge_version mismatch')
    if mapping.get('execution_identity')!=cfg.get('agent',{}).get('execution_identity'):raise ValueError('Registered execution identity mismatch')
    return {'status':'VERIFIED_OFFLINE_DECLARATION','adapter':mapping['adapter'],'protocol':mapping['protocol'],
        'configuration_version':registered['configuration_version'],'task_version':registered['task_version'],
        'knowledge_version':mapping['knowledge_version'],'documents':len(registered['knowledge_manifest']),
        'passages':len(registered['passages']),'model_calls':0,'application_called':False,
        'runtime_mapping_and_generation':'PENDING','independence':'Operator-supplied offline index assertion; not authenticated app attestation'}


def read_json(path):
    if Path(path).stat().st_size>6*1024*1024:raise ValueError('JSON input exceeds 6 MiB limit')
    return json.loads(Path(path).read_text())


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['template','check','dry-run'])
    p.add_argument('--project',type=Path);p.add_argument('--mapping',type=Path);p.add_argument('--owner-input',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        if a.action=='dry-run':
            if not a.owner_input:raise ValueError('dry-run requires --owner-input with authorized documents and owner-established labels')
            if a.output.exists():raise ValueError('Output exists; choose a fresh project path')
            from tools.source_owner_onboarding import materialize
            from sourceroi.live.assurance import propose
            materialize(read_json(a.owner_input),a.output)
            before=read_config(a.output/'accepted');after=read_config(a.output/'candidate')
            intent=read_json(a.output/'intent.json');spec=propose(before,after,intent=intent)
            write_new(a.output/'change.json',spec)
            write_new(a.output/'mapping-template.json',template(a.output/'candidate'))
            value={'status':'VERIFIED_PREPARATION_ONLY','release_verdict':None,'execution':'NOT_EXECUTED',
                'model_calls':0,'application_called':False,'review':'PENDING_REAL_REVIEW',
                'next':'Inspect change.json; supply actual offline index export; review DRAFT decisions. No release safety result exists.'}
            write_new(a.output/'dry-run.json',value)
        else:
            if not a.project:raise ValueError('Use --project pointing to the registered workspace')
            value=template(a.project) if a.action=='template' else preflight(a.project,read_json(a.mapping)) if a.mapping else None
            if value is None:raise ValueError('check requires --mapping from your actual offline application index')
            write_new(a.output,value)
        print(json.dumps(value,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:p.exit(2,'Offline preflight failed: '+str(exc)+'\n')

if __name__=='__main__':main()
