"""Bounded subprocess ingestion and immutable byte snapshots.

Resource isolation plus a scoped macOS profile, NOT a complete host sandbox. Private copied
inputs, scrubbed environment, process-group termination, CPU/file/fd limits and
sampled RSS supervision. No live provider or arbitrary worker path is accepted.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
from functools import wraps
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
MAX_INPUT=12*1024*1024
MAX_OUTPUT=48*1024*1024
WALL_SECONDS=15
RSS_KIB=512*1024
_CACHE=OrderedDict()
_CACHE_SIZES={}
_CACHE_LOCK=threading.RLock()
_METRICS={'executions':0,'cache_hits':0,'failures':0}
_SLOTS=threading.BoundedSemaphore(2)
_LOCAL=threading.local()
CAPACITY_WAIT_SECONDS=15


def limited(function):
    @wraps(function)
    def call(*args,**kwargs):
        depth=getattr(_LOCAL,'depth',0)
        if depth:return function(*args,**kwargs)
        if not _SLOTS.acquire(timeout=CAPACITY_WAIT_SECONDS):raise ValueError('Parser capacity wait deadline exceeded; retry after active ingestion finishes')
        try:
            from .runtime_resources import admission
            with admission(CAPACITY_WAIT_SECONDS) as fd:
                _LOCAL.depth=1;_LOCAL.global_fd=fd
                try:return function(*args,**kwargs)
                finally:_LOCAL.depth=0;_LOCAL.global_fd=None
        finally:_SLOTS.release()
    return call



def open_beneath(path,root):
    parts=path.relative_to(root).parts
    if not parts:raise ValueError('Source must be a file beneath workspace')
    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=next_fd
        return os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
    finally:os.close(directory)


def snapshot(path,root,*,max_bytes=MAX_INPUT):
    path=Path(path).absolute();raw_root=Path(root).absolute();root=raw_root.resolve()
    if path.is_relative_to(raw_root):path=root/path.relative_to(raw_root)
    if '..' in path.parts or not path.is_relative_to(root) or not path.resolve().is_relative_to(root):raise ValueError('Parser path escapes workspace')
    current=root
    for part in path.relative_to(root).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Symlink escapes or aliases workspace parser boundary')
    fd=open_beneath(path,root)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>max_bytes:raise ValueError('Parser requires ordinary unlinked-alias-free file at most 12MB')
        with os.fdopen(os.dup(fd),'rb') as f:value=f.read(max_bytes+1)
        after=os.fstat(fd)
        identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
        if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) or len(value)>max_bytes:raise ValueError('Source changed during parser snapshot')
        return {'path':path,'identity':identity,'sha256':hashlib.sha256(value).hexdigest(),'bytes':value,'max_bytes':max_bytes}
    finally:os.close(fd)


def verify(records,root):
    for record in records:
        current=snapshot(record['path'],root,max_bytes=record.get('max_bytes',MAX_INPUT))
        if current['identity']!=record['identity'] or current['sha256']!=record['sha256']:raise ValueError('Source changed during isolated parsing')


def sandbox_command(command,cwd,protected_root=None):
    if sys.platform!='darwin':raise ValueError('Verified parser sandbox supports macOS only; unsupported platform fails closed')
    sandbox=Path('/usr/bin/sandbox-exec')
    if not sandbox.is_file():raise ValueError('macOS parser sandbox unavailable; no unsandboxed fallback')
    # Keep required macOS runtime services, deny network/forks and writes outside
    # the private directory. Deny private home data except trusted code/runtime.
    # This is deliberately narrower than claiming a deny-default OS sandbox.
    allowed=[str(Path(sys.prefix).resolve()),str(ROOT/'sourceroi')]
    filters=' '.join('(require-not (subpath '+json.dumps(p)+'))' for p in allowed)
    profile='(version 1)(allow default)(deny network*)(deny process-fork)'
    profile+='(deny process-exec (require-all (require-not (literal '+json.dumps(str(Path(sys.executable).resolve()))+')) (require-not (literal '+json.dumps(sys.executable)+'))))'
    profile+='(deny appleevent-send)(deny mach-lookup (global-name "com.apple.mDNSResponder"))'
    profile+='(deny file-write* (require-not (subpath '+json.dumps(str(Path(cwd).resolve()))+')))'
    profile+='(deny file-read-data (require-all (subpath '+json.dumps(str(Path.home()))+') (require-not (literal '+json.dumps(str(ROOT))+')) '+filters+'))'
    for protected in (protected_root if isinstance(protected_root,(list,tuple)) else [protected_root]):
        if protected is not None:profile+='(deny file-read-data (require-all (subpath '+json.dumps(str(Path(protected).resolve()))+') (require-not (literal '+json.dumps(str(ROOT))+')) '+filters+'))'
    from .runtime_resources import root as runtime_root
    profile+='(deny file-read-data (require-all (subpath '+json.dumps(str(runtime_root()))+') (require-not (subpath '+json.dumps(str(Path(cwd).resolve()))+'))))'
    return [str(sandbox),'-p',profile,*command]


@limited
def supervise(command,cwd,*,wall=WALL_SECONDS,rss_kib=RSS_KIB,sandbox=False,protected_root=None,owner_fd=None,cancel_check=None):
    """Internal supervisor, separately adversarial-tested; command never from HTTP."""
    env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(ROOT),'PYTHONIOENCODING':'utf-8','PYTHONHASHSEED':'0','TMPDIR':str(cwd),'LANG':'en_US.UTF-8'}
    started=time.monotonic();reason=None;peak=0;p=None
    try:
        if sandbox:command=sandbox_command(command,cwd,protected_root)
        spec_fd=os.open(Path(cwd)/'steward-spec.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(spec_fd,'w') as spec_file:json.dump({'command':command,'parent':os.getpid(),'wall':wall},spec_file);spec_file.flush();os.fsync(spec_file.fileno())
        p=subprocess.Popen([sys.executable,'-m','sourceroi.live.parser_steward'],cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True,pass_fds=tuple(fd for fd in (getattr(_LOCAL,'global_fd',None),owner_fd) if fd is not None))
        control=Path(cwd).parent/'control.json'
        if Path(cwd).name=='work' and Path(cwd).parent.name.startswith('op-') and control.is_file():
            from .runtime_resources import publish
            record=json.loads(control.read_text());record['process_group']=p.pid;publish(control,record)
        while p.poll() is None:
            if cancel_check is not None and cancel_check():reason='Supervised execution cancelled or ownership lost';break
            if time.monotonic()-started>wall:reason='Parser wall deadline exceeded';break
            stats=subprocess.run(['/bin/ps','-axo','pid=,pgid=,rss='],capture_output=True,text=True,timeout=1)
            if stats.returncode:reason='Parser memory/process supervision unavailable';break
            members=[tuple(map(int,line.split())) for line in stats.stdout.splitlines() if len(line.split())==3 and line.split()[1]==str(p.pid)]
            rss=sum(r[2] for r in members);peak=max(peak,rss)
            if len(members)>2:reason='Parser child processes are unsupported';break
            if rss>rss_kib:reason='Parser memory RSS limit exceeded';break
            output=Path(cwd)/'response.json'
            if output.exists() and output.stat().st_size>MAX_OUTPUT:reason='Parser output resource limit exceeded';break
            time.sleep(.015)
        if reason:raise ValueError(reason)
        if p.wait()!=0:raise ValueError('Parser terminated or exceeded OS resource limit')
        return {'elapsed_ms':1000*(time.monotonic()-started),'peak_rss_kib':peak,'pid':p.pid}
    finally:
        if p is not None:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            p.wait(timeout=3)


@limited
def run(spec,files,*,protected_root=None):
    for protected in (protected_root if isinstance(protected_root,(list,tuple)) else [protected_root]):
        if protected is not None:
            selected=Path(protected).resolve()
            if any(selected.is_relative_to(p) for p in (Path(sys.prefix).resolve(),ROOT/'sourceroi')):raise ValueError('Workspace inside trusted parser runtime/code exception is unsupported')
    encoded=json.dumps(spec,sort_keys=True,allow_nan=False).encode()
    if len(encoded)>MAX_OUTPUT:raise ValueError('Analytical request exceeds 48MiB bound')
    if sum(len(record['bytes']) for record in files.values())+len(encoded)>128*1024*1024:raise ValueError('Combined analytical snapshot exceeds 128MiB bound')
    key=hashlib.sha256(encoded+b''.join(name.encode()+b'\0'+record['bytes'] for name,record in sorted(files.items()))).hexdigest()
    with _CACHE_LOCK:
        cached=_CACHE.get(key)
        if cached is not None:_METRICS['cache_hits']+=1;return deepcopy(cached)
    from .runtime_resources import scratch
    with scratch() as (tmp,owner_fd):
        (tmp/'input').mkdir()
        for name,record in files.items():
            out=tmp/'input'/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(record['bytes']);out.chmod(0o400)
        (tmp/'request.json').write_text(json.dumps(spec))
        try:
            supervise([sys.executable,'-m','sourceroi.live.parser_worker'],tmp,sandbox=True,protected_root=protected_root,owner_fd=owner_fd)
            path=tmp/'response.json'
            if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_OUTPUT:raise ValueError('Parser output missing/unsafe/oversized')
            response=json.loads(path.read_text())
            if not isinstance(response,dict) or response.get('version')!=1 or type(response.get('ok')) is not bool:raise ValueError('Invalid parser response contract')
            if not response['ok']:raise ValueError(response.get('error','Isolated parser failed'))
            result=response['result']
            with _CACHE_LOCK:
                _METRICS['executions']+=1
                if path.stat().st_size<1024*1024:
                    for stale in set(_CACHE_SIZES)-set(_CACHE):_CACHE_SIZES.pop(stale,None)
                    _CACHE[key]=deepcopy(result);_CACHE_SIZES[key]=path.stat().st_size
                    while len(_CACHE)>256 or sum(_CACHE_SIZES.values())>32*1024*1024:
                        removed,_=_CACHE.popitem(last=False);_CACHE_SIZES.pop(removed,None)
            return result
        except BaseException:
            with _CACHE_LOCK:_METRICS['failures']+=1
            raise


@limited
def extract(path,*,preserve_csv=False,root=None):
    path=Path(path).absolute();root=Path(root or path.parent);record=snapshot(path,root)
    name='document'+path.suffix.lower()
    value=run({'operation':'extract','path':'input/'+name,'preserve_csv':preserve_csv},{name:record},protected_root=root)
    verify([record],root)
    if not isinstance(value,str) or len(value)>400000:raise ValueError('Extracted document exceeds 400000 character limit; no partial text accepted')
    return value


def prepare(cfg):
    from .config import SUPPORTED_EXTENSIONS,secure_path
    root=Path(cfg['_root']).resolve();files={};size=0
    sources=[]
    for source in cfg['sources']:
        folder=secure_path(root,source['path'])
        # Check the original configured path as well as discovered documents.
        current=root
        for part in Path(source['path']).parts:
            current=current/part
            if current.is_symlink():raise ValueError('Symlink escapes or aliases workspace parser boundary')
        for path in sorted(folder.rglob('*')):
            if path.is_symlink():raise ValueError('Symlink escapes or aliases workspace parser boundary')
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:continue
            record=snapshot(path,root);files[path.relative_to(root).as_posix()]=record;size+=len(record['bytes'])
            if len(files)>2500 or size>64*1024*1024:raise ValueError('Parser corpus snapshot resource limit exceeded')
        sources.append({k:deepcopy(v) for k,v in source.items()})
    settings={k:v for k,v in cfg.get('settings',{}).items() if k in ('chunk_chars','overlap_chars','chunk_strategy','table_evidence')}
    worker_cfg={'sources':sources,'settings':settings}
    if cfg.get('data_provenance'):
        name=cfg['data_provenance'];files[name]=snapshot(secure_path(root,name),root);worker_cfg['data_provenance']=name
    return root,files,sources,worker_cfg


@limited
def scan(cfg,*,include_text=True):
    from .config import SUPPORTED_EXTENSIONS,secure_path
    root,files,sources,worker_cfg=prepare(cfg)
    source_names=set(files)
    result=run({'operation':'scan','cfg':worker_cfg,'include_text':include_text},files,protected_root=root)
    verify(files.values(),root)
    observed={p.relative_to(root).as_posix() for source in sources for p in secure_path(root,source['path']).rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS}
    expected_names=source_names-({cfg['data_provenance']} if cfg.get('data_provenance') and cfg['data_provenance'] not in observed else set())
    if observed!=expected_names:raise ValueError('Source inventory changed during isolated parsing')
    if not isinstance(result,dict) or set(result)!={'documents','chunks','texts'}:raise ValueError('Parser scan contract mismatch')
    docs=result['documents'];chunks=result['chunks'];texts=result['texts'];known={}
    for d in docs:
        if set(d)!={'id','source_id','path','title','fingerprint','characters','bytes'} or d['path'] not in files:raise ValueError('Unexpected parsed document identity')
        source=next((s for s in sources if s['id']==d['source_id']),None)
        if source is None:raise ValueError('Parser cannot register sources')
        relative=Path(d['path']).relative_to(source['path']).as_posix();ident=source['id']+'::'+relative
        text=texts.get(ident)
        if d['id']!=ident or not isinstance(text,str) or len(text)>400000 or d['fingerprint']!=hashlib.sha256(text.encode()).hexdigest() or d['characters']!=len(text):raise ValueError('Parsed document provenance mismatch')
        d['bytes']=len(files[d['path']]['bytes']);known[ident]=d
    if len(known)!=len(docs):raise ValueError('Duplicate parsed document identities')
    for c in chunks:
        if c.get('document_id') not in known or c.get('source_id')!=known[c['document_id']]['source_id'] or not c.get('id','').startswith(c['document_id']+'#chunk'):raise ValueError('Parser chunk identity mismatch')
        if set(c)-{'id','document_id','source_id','title','text','start','end','fragmented','document_fingerprint','chunk_strategy','raw_source_sha256','offset_basis','table'}:raise ValueError('Unexpected trusted field in parser output')
        text=texts[c['document_id']]
        if c.get('start') is not None and text[c['start']:c['end']]!=c['text']:raise ValueError('Parser passage offsets mismatch')
        if c.get('raw_source_sha256') and c['raw_source_sha256']!=files[known[c['document_id']]['path']]['sha256']:raise ValueError('Parser raw source version mismatch')
    return docs,chunks


@limited
def benchmark(cfg):
    from .config import secure_path
    root=Path(cfg['_root']).resolve();name=cfg.get('benchmark','benchmark.jsonl');record=snapshot(secure_path(root,name),root)
    result=run({'operation':'benchmark','cfg':{'benchmark':name}},{name:record});verify([record],root)
    if not isinstance(result,list):raise ValueError('Benchmark parser contract mismatch')
    return result


@limited
def json_data(path):
    path=Path(path).absolute();record=snapshot(path,path.parent,max_bytes=64*1024*1024)
    result=run({'operation':'json_data','path':'input/data.json'},{'data.json':record},protected_root=path.parent)
    verify([record],path.parent);return result


@limited
def calculate(cfg,context,contract,scope):
    root,files,_,worker_cfg=prepare(cfg)
    result=run({'operation':'facts','cfg':worker_cfg,'context':context,'contract':contract,'scope':scope},files,protected_root=root)
    verify(files.values(),root);return result
