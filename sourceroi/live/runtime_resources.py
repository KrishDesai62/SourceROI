"""Single-host, per-OS-user admission and private crash evidence. POSIX only.

Advisory locks survive in the trusted steward until supervised children stop.
No leases, environment-selected quota roots or automatic uncertain-work retry.
"""
from contextlib import contextmanager
import fcntl
import json
import hashlib
import zipfile
import os
import re
from pathlib import Path
import secrets
import shutil
import stat
import tempfile
import time

SLOTS=2
MAX_RETAINED=256*1024*1024
MAX_OPERATIONS=128
MIN_FREE=512*1024*1024


def root():
    path=Path('/private/tmp' if __import__('sys').platform=='darwin' else '/tmp')/('sourceroi-runtime-'+str(os.getuid()))
    try:path.mkdir(mode=0o700)
    except FileExistsError:pass
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('Unsafe shared runtime root')
    return path


def open_lock(path):
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
        os.close(fd);raise ValueError('Unsafe shared runtime lock')
    return fd


def retained_bytes(path):
    total=0
    for p in path.glob('op-*'):
        if p.is_symlink():raise ValueError('Unsafe runtime evidence directory')
        for child in p.rglob('*'):
            if child.is_symlink():total+=child.lstat().st_size
            elif child.is_file():total+=child.stat().st_size
    return total


@contextmanager
def admission(timeout=15):
    path=root()
    if shutil.disk_usage(path).free<MIN_FREE:raise ValueError('Runtime free-disk safety floor not met')
    if sum(1 for _ in path.glob('op-*'))>=MAX_OPERATIONS:raise ValueError('Runtime operation retention limit reached; inspect verified orphans')
    if retained_bytes(path)>MAX_RETAINED:raise ValueError('Runtime crash evidence budget exceeded; inspect and clean verified orphans')
    deadline=time.monotonic()+timeout;fd=None
    while fd is None:
        for i in range(SLOTS):
            candidate=open_lock(path/f'slot-{i}.lock')
            try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB);fd=candidate;break
            except BlockingIOError:os.close(candidate)
        if fd is None:
            if time.monotonic()>=deadline:raise ValueError('Global runtime capacity wait deadline exceeded')
            time.sleep(.02)
    try:yield fd
    finally:os.close(fd)


def publish(path,value):
    temporary=path.with_suffix('.new')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


@contextmanager
def scope():
    from .parser_boundary import _LOCAL
    if getattr(_LOCAL,'depth',0):yield;return
    with admission() as fd:
        _LOCAL.depth=1;_LOCAL.global_fd=fd
        try:yield
        finally:_LOCAL.depth=0;_LOCAL.global_fd=None


@contextmanager
def scratch():
    with scope():
        with _scratch() as value:yield value


@contextmanager
def _scratch():
    directory=root()/('op-'+secrets.token_hex(16));directory.mkdir(mode=0o700)
    work=directory/'work';work.mkdir(mode=0o700)
    lock=open_lock(directory/'owner.lock');fcntl.flock(lock,fcntl.LOCK_EX)
    record={'version':1,'id':directory.name,'owner':os.getpid(),'state':'ACTIVE','created_at':time.time()}
    publish(directory/'control.json',record)
    try:
        yield work,lock
    except BaseException:
        publish(directory/'control.json',{**json.loads((directory/'control.json').read_text()),'state':'INCOMPLETE','ended_at':time.time()})
        raise
    else:
        # Only this newly-created operation is removed. Historical experiment
        # archives/workspace files are outside this root and never traversed.
        shutil.rmtree(directory)
    finally:os.close(lock)


def inspect_cleanup(*,delete=False,ids=None,archive_directory=None):
    path=root();rows=[]
    if delete and archive_directory is None:raise ValueError('Verified cleanup requires a private forensic archive directory')
    if ids is not None and any(not re.fullmatch(r'op-[0-9a-f]{32}',i) for i in ids):raise ValueError('Invalid operation identity')
    for directory in sorted(path.glob('op-*')):
        if ids is not None and directory.name not in ids:continue
        if not re.fullmatch(r'op-[0-9a-f]{32}',directory.name) or directory.is_symlink() or not directory.is_dir():raise ValueError('Unsafe orphan path')
        info=directory.lstat()
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('Unsafe runtime operation permissions')
        fd=open_lock(directory/'owner.lock')
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:rows.append({'id':directory.name,'state':'ACTIVE','deleted':False});continue
            if (directory/'control.json').is_symlink():raise ValueError('Unsafe runtime control record')
            if not (directory/'control.json').exists():
                if (directory/'work/steward-spec.json').exists():rows.append({'id':directory.name,'state':'TERMINATION_UNVERIFIED','deleted':False});continue
                record={'version':1,'id':directory.name,'state':'CREATION_INTERRUPTED'}
            else:record=json.loads((directory/'control.json').read_text())
            if record.get('version')!=1 or record.get('id')!=directory.name:raise ValueError('Unknown runtime evidence; refuse cleanup')
            # A steward writes its process group outside the sandboxed work dir.
            group=record.get('process_group')
            if group:
                import subprocess
                p=subprocess.run(['/bin/ps','-axo','pgid=,stat='],capture_output=True,text=True,timeout=2)
                if p.returncode:raise ValueError('Cannot verify orphan process termination')
                if any(len(line.split())==2 and line.split()[0]==str(group) and not line.split()[1].startswith('Z') for line in p.stdout.splitlines()):
                    rows.append({'id':directory.name,'state':'TERMINATION_UNVERIFIED','deleted':False});continue
            size=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and not p.is_symlink())
            if not shutil.rmtree.avoids_symlink_attacks:raise ValueError('Platform cannot safely remove symlink-containing orphan trees')
            summary={'id':directory.name,'state':'ORPHAN_OR_INCOMPLETE','bytes':size,'deleted':False}
            if delete:
                archive_root=Path(archive_directory).absolute()
                if archive_root.resolve().is_relative_to(path):raise ValueError('Forensic archives must be outside runtime retention root')
                archive_root.mkdir(mode=0o700,parents=True,exist_ok=True)
                info=archive_root.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise ValueError('Forensic directory must be private and owner controlled')
                archive=archive_root/(directory.name+'.zip')
                archive_fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                manifest={}
                with os.fdopen(archive_fd,'wb') as target:
                    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                        for member in sorted(directory.rglob('*')):
                            rel=member.relative_to(directory).as_posix()
                            if member.is_symlink():manifest[rel]={'kind':'symlink_metadata_only','target':os.readlink(member)}
                            elif member.is_file():
                                raw=member.read_bytes();manifest[rel]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};z.writestr(rel,raw)
                        z.writestr('forensic-manifest.json',json.dumps(manifest))
                    target.flush();os.fsync(target.fileno())
                with zipfile.ZipFile(archive) as check:
                    for name,item in manifest.items():
                        if 'sha256' in item and hashlib.sha256(check.read(name)).hexdigest()!=item['sha256']:raise ValueError('Forensic export verification failed; scratch preserved')
                directory_fd=os.open(archive_root,os.O_RDONLY)
                try:os.fsync(directory_fd)
                finally:os.close(directory_fd)
                archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
                summary.update(forensic_archive=str(archive),forensic_sha256=archive_sha)
                # Keep a bounded metadata-only tombstone, never document text.
                log=path/'cleanup-audit.jsonl'
                if log.is_symlink() or (path/'last-cleanup.json').is_symlink() or (path/'last-cleanup.new').is_symlink():raise ValueError('Unsafe cleanup audit path')
                existing=log.read_text().splitlines()[-127:] if log.exists() else []
                publish(path/'last-cleanup.json',{'id':directory.name,'bytes':size,'at':time.time(),'authority':'trusted OS operator','original_state':record['state'],'forensic_archive':str(archive),'sha256':archive_sha})
                log.write_text('\n'.join(existing+[json.dumps({'id':directory.name,'bytes':size,'at':time.time()})])+'\n');log.chmod(0o600)
                shutil.rmtree(directory);summary['deleted']=True
            rows.append(summary)
        finally:os.close(fd)
    return {'dry_run':not delete,'root':str(path),'operations':rows,'retained_bytes':retained_bytes(path),'limit_bytes':MAX_RETAINED}
