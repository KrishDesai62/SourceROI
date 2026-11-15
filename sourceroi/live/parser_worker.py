"""Private subprocess protocol. Only fixed parsing operations, no execution APIs."""
import json
import os
from pathlib import Path
import resource
import sys


def limits():
    resource.setrlimit(resource.RLIMIT_CPU,(8,9))
    resource.setrlimit(resource.RLIMIT_FSIZE,(48*1024*1024,48*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    # RLIMIT_AS is not a reliable macOS RSS bound. Parent enforces sampled group
    # RSS; report that limitation rather than pretending a hard memory sandbox.
    if sys.platform.startswith('linux'):resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
    if hasattr(resource,'RLIMIT_NPROC'):
        try:resource.setrlimit(resource.RLIMIT_NPROC,(0,0))
        except (OSError,ValueError):pass


def main():
    limits()
    spec=json.loads(Path('request.json').read_text())
    from sourceroi.live import ingest
    ingest._WORKER_ACTIVE=True
    from .config import secure_path
    configurations=[spec.get('cfg')]
    if spec.get('operation')=='analysis':
        payload=spec['payload'];configurations=[payload.get(k) for k in ('cfg','baseline','candidate')]
    for cfg in configurations:
        if isinstance(cfg,dict) and cfg.get('sources') and ('_root' in cfg or spec['operation'] in ('scan','facts')):
            base=Path(cfg.get('_root','input')).resolve()
            for source in cfg['sources']:secure_path(base,source['path'],must_exist=False).mkdir(parents=True,exist_ok=True)
    try:
        operation=spec['operation']
        if operation=='extract':result=ingest._extract_in_process(Path(spec['path']),preserve_csv=spec['preserve_csv'])
        elif operation=='scan':
            cfg=spec['cfg'];cfg['_root']=str(Path('input').resolve());cfg['_parser_texts']={}
            docs,chunks=ingest._scan_sources_in_process(cfg,include_text=spec['include_text'])
            result={'documents':docs,'chunks':chunks,'texts':cfg['_parser_texts']}
        elif operation=='analysis':
            from sourceroi.live.analysis_boundary import execute
            result=execute(spec['analysis'],spec['payload'])
        elif operation=='json_data':
            result=json.loads(Path(spec['path']).read_text());stack=[(result,0)];nodes=0
            while stack:
                value,depth=stack.pop();nodes+=1
                if depth>64 or nodes>1000000:raise ValueError('Dataset JSON complexity resource limit exceeded')
                if isinstance(value,dict):stack.extend((v,depth+1) for v in value.values())
                elif isinstance(value,list):stack.extend((v,depth+1) for v in value)
        elif operation=='regex_grade':
            import re
            if len(spec['expected'])>3000 or len(spec['actual'])>400000:raise ValueError('Regex grading input limit exceeded')
            try:result=bool(re.search(spec['expected'],spec['actual'],flags=re.IGNORECASE))
            except re.error as exc:raise ValueError('Invalid benchmark regex: '+str(exc)) from exc
        elif operation=='facts':
            from sourceroi.live.facts import _calculate_in_process
            cfg=spec['cfg'];cfg['_root']=str(Path('input').resolve())
            result=_calculate_in_process(spec['context'],spec['contract'],cfg,spec['scope'])
        elif operation=='benchmark':
            cfg=spec['cfg'];cfg['_root']=str(Path('input').resolve());result=ingest._load_benchmark_in_process(cfg)
        else:raise ValueError('Unknown parser operation')
        response={'version':1,'ok':True,'result':result}
    except Exception as exc:
        # Parser diagnostics are bounded; document text is never sent to logs.
        response={'version':1,'ok':False,'error':str(exc)[:500],'error_type':type(exc).__name__}
    value=json.dumps(response,ensure_ascii=False,allow_nan=False).encode()
    if len(value)>48*1024*1024:raise ValueError('Parser output resource limit exceeded')
    with open('response.json','xb') as f:f.write(value);f.flush();os.fsync(f.fileno())

if __name__=='__main__':main()
