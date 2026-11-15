"""Quiesced, integrity-checked workspace backups and non-overwriting restores.

Cooperative writers use workspace_lock. The trusted OS administrator must stop
external editors/direct Python writers. This is not a filesystem snapshot against
malicious or uncooperative writers. Backups contain sensitive source evidence.
"""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import secrets
import sqlite3
import stat
import tempfile
import zipfile
from .workspace_lock import workspace_lock
from .data_ci import digest

MAX_FILES=10000
MAX_BYTES=512*1024*1024

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def identities(root):
    from .config import read_config
    from .ingest import scan_sources,load_benchmark
    from .assurance import verify_snapshot
    root=Path(root)
    if (root/'snapshot.json').exists():verify_snapshot(read_config(root))
    snapshots=root/'.sourceroi/snapshots'
    if snapshots.exists():
        for frozen in sorted(snapshots.rglob('snapshot.json')):
            if not (frozen.parent/'project.json').is_file():raise ValueError('Frozen snapshot configuration missing')
            verify_snapshot(read_config(frozen.parent))
    cfg=read_config(root);docs,_=scan_sources(cfg)
    return {'configuration':cfg['_config_hash'],'tasks':digest(load_benchmark(cfg)),
            'sources':{d['id']:d['fingerprint'] for d in docs}}


def inventory(root):
    result={};size=0
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():raise ValueError('Workspace symlinks forbidden in complete backup')
        if p.is_dir():continue
        name=p.relative_to(root).as_posix()
        if name=='.sourceroi/workspace.lock':continue
        if name.startswith('.sourceroi/security/'):
            if name not in {'.sourceroi/security/identity.sqlite3'+suffix for suffix in ('','-wal','-shm','-journal')}:raise ValueError('Unexpected identity-store file; cannot silently omit it')
            continue
        is_sidecar=False
        for suffix in ('-wal','-shm','-journal'):
            if name.endswith(suffix):
                base=Path(root)/name[:-len(suffix)]
                if base.is_file():
                    with base.open('rb') as f:is_sidecar=f.read(16)==b'SQLite format 3\x00'
        if is_sidecar:continue
        if not p.is_file() or p.stat().st_nlink!=1:raise ValueError('Workspace special files/hardlinks forbidden')
        size+=p.stat().st_size
        if size>MAX_BYTES or len(result)>=MAX_FILES:raise ValueError('Workspace exceeds backup resource limit')
        result[name]={'sha256':sha(p),'bytes':p.stat().st_size}
    return result


def security_history(root):
    from .security import SecurityStore
    folder=Path(root)/'.sourceroi/security'
    if not folder.exists():return {'version':1,'provisioned':False,'policy':'No credentials or live authority restored'}
    store=SecurityStore(root)
    with store.connect() as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result={'version':1,'provisioned':True,'original_workspace':store.binding,'policy':'Historical provenance only; re-provision identities; no sessions/passwords/receipts restored'}
        if 'job_schema' in tables and c.execute('SELECT version FROM job_schema').fetchone()[0]!=1:raise ValueError('Incompatible job schema in backup')
        result['users']=[dict(r) for r in c.execute('SELECT id,name,role,enabled FROM users')]
        result['approvals']=[dict(r) for r in c.execute('SELECT * FROM approvals')]
        for table in ('metadata','plans','audit','approval_revocations','identity_revisions','job_schema','jobs','job_events','fixture_authorizations','job_attempts','job_native_fixture_evidence','job_runtime_artifacts','semantic_judgments'):
            if table in tables:result[table]=[dict(r) for r in c.execute('SELECT * FROM '+table)]
    return result


def capture_db(source,dest):
    with sqlite3.connect(source) as a,sqlite3.connect(dest) as b:
        a.backup(b)
        if b.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database backup integrity failed')


def backup(root,destination,*,quiesced=False):
    root=Path(root).resolve();destination=Path(destination).absolute()
    if not quiesced:raise ValueError('Explicit quiesced confirmation required: stop external editors and direct library writers')
    if destination.resolve().is_relative_to(root):raise ValueError('Backup must be outside workspace')
    if destination.exists() or destination.is_symlink():raise ValueError('Backup destination exists')
    if not destination.parent.is_dir():raise ValueError('Backup parent must exist')
    partial=destination.with_name(destination.name+'.partial-'+secrets.token_hex(8))
    with workspace_lock(root,exclusive=True),tempfile.TemporaryDirectory() as tmp:
        before=inventory(root);identity=identities(root);history=security_history(root)
        fd=os.open(partial,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        rows={};dbfiles={}
        # Capture all standalone SQLite files, including nested historical stores.
        for name in before:
            if name.endswith(('.sqlite3','.sqlite','.db')):
                with (root/name).open('rb') as f:header=f.read(16)
                if header==b'SQLite format 3\x00':
                    target=Path(tmp)/str(len(dbfiles));capture_db(root/name,target);dbfiles[name]=target
        with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in before:
                path=dbfiles.get(name,root/name);value=path.read_bytes()
                rows[name]={'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)}
                archive.writestr('workspace/'+name,value)
            value=json.dumps(history,sort_keys=True).encode();name='.sourceroi/restored-history/security-provenance-'+secrets.token_hex(8)+'.json'
            if name in rows:raise ValueError('Workspace already contains reserved recovery provenance path')
            rows[name]={'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)};archive.writestr('workspace/'+name,value)
            manifest={'version':1,'kind':'sourceroi_complete_workspace','identity':identity,'files':rows,
                'identity_policy':'reprovision; no active sessions, credentials, approval receipts or queued jobs restored',
                'consistency':'exclusive cooperative lock plus operator external-writer quiescence; online SQLite captures; before/after inventory'}
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
        if before!=inventory(root) or identity!=identities(root) or history!=security_history(root):raise ValueError('Workspace changed during quiesced backup')
        with partial.open('rb') as f:os.fsync(f.fileno())
        os.link(partial,destination);partial.unlink() # atomic exclusive publication
        fd=os.open(destination.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return {'status':'VERIFIED','archive':str(destination),'sha256':sha(destination),'files':len(rows),'identity':identity,'identity_authority_restored':False}


def checked_archive(path,expected_sha256):
    path=Path(path)
    if not expected_sha256 or sha(path)!=expected_sha256:raise ValueError('Trusted archive SHA-256 mismatch')
    try:z=zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:raise ValueError('Invalid or truncated backup archive') from exc
    try:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(names)>MAX_FILES+1:raise ValueError('Duplicate/excess archive members')
        if sum(i.file_size for i in infos)>MAX_BYTES:raise ValueError('Archive inflated size exceeds limit')
        for i in infos:
            p=PurePosixPath(i.filename);kind=stat.S_IFMT(i.external_attr>>16)
            if p.is_absolute() or any(s in ('','.','..') for s in i.filename.split('/')) or '\\' in i.filename or i.is_dir() or kind not in (0,stat.S_IFREG) or i.flag_bits&1:raise ValueError('Unsafe archive member')
        if 'manifest.json' not in names:raise ValueError('Backup manifest missing')
        m=json.loads(z.read('manifest.json'))
        if not isinstance(m,dict) or m.get('version')!=1 or m.get('kind')!='sourceroi_complete_workspace':raise ValueError('Incompatible backup schema')
        if not isinstance(m.get('files'),dict) or not m['files'] or 'project.json' not in m['files']:raise ValueError('Incomplete backup file manifest')
        expected={'manifest.json'}|{'workspace/'+n for n in m['files']}
        if set(names)!=expected:raise ValueError('Missing or unexpected backup files')
        for name,record in m['files'].items():
            if name.startswith('.sourceroi/security/'):raise ValueError('Active identity stores cannot be restored')
            if not isinstance(record,dict) or set(record)!={'sha256','bytes'} or type(record['bytes']) is not int or record['bytes']<0 or not isinstance(record['sha256'],str) or len(record['sha256'])!=64:raise ValueError('Invalid backup file record')
            value=z.read('workspace/'+name)
            if len(value)!=record['bytes'] or hashlib.sha256(value).hexdigest()!=record['sha256']:raise ValueError('Backup file hash mismatch')
        return z,m
    except (zipfile.BadZipFile,KeyError,TypeError,AttributeError) as exc:
        z.close();raise ValueError('Malformed or corrupted backup manifest/archive') from exc
    except BaseException:z.close();raise


def restore(path,destination,*,expected_sha256):
    z,m=checked_archive(path,expected_sha256);destination=Path(destination).absolute()
    try:
        if destination.exists() or destination.is_symlink():raise ValueError('Restore target must be new; never overwrite a workspace')
        destination.mkdir(mode=0o700) # exclusive private container, detects interrupted restores
        marker=destination/'RESTORE_INCOMPLETE';marker.write_text('Do not serve; restore incomplete\n')
        stage=destination/'.staging';stage.mkdir(mode=0o700);target=destination/'workspace'
        for name in m['files']:
            out=stage/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read('workspace/'+name));out.chmod(0o600)
        for p in stage.rglob('*'):
            if p.is_file() and p.suffix in ('.db','.sqlite','.sqlite3'):
                with p.open('rb') as f:header=f.read(16)
                if header==b'SQLite format 3\x00':
                    with sqlite3.connect(p) as c:
                        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Restored database integrity failed')
        if identities(stage)!=m['identity']:raise ValueError('Restored source/config/task identity mismatch')
        # Re-provision a completely empty, final-path-bound identity store. Prior
        # identities/approvals/jobs remain historical JSON only, never live authority.
        from .security import SecurityStore,hashed
        store=SecurityStore(stage,initialize=True)
        with store.connect() as c:c.execute('UPDATE metadata SET workspace=?',(hashed(str(target.resolve())),))
        provenance={'version':1,'backup_sha256':expected_sha256,'original_identity':m['identity'],
            'credentials_restored':False,'sessions_restored':0,'active_approval_receipts_restored':0,'active_jobs_restored':0,
            'historical_jobs_policy':'Inspect historical job JSON; active/unknown work requires explicit reconciliation, never auto-resume'}
        (stage/'.sourceroi/restore-validation.json').write_text(json.dumps(provenance,indent=2)+'\n')
        # Flush all content before publishing inside the newly reserved container.
        for p in stage.rglob('*'):
            if p.is_file():
                with p.open('rb') as f:os.fsync(f.fileno())
        os.rename(stage,target);marker.unlink()
        fd=os.open(destination,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return {'status':'VERIFIED','workspace':str(target),'identity':identities(target),'files_verified':len(m['files']),**provenance}
    finally:z.close()


def retention_preview(root,relative_paths):
    """No deletion operation is supplied; explicit content inventory only."""
    from .config import secure_path
    root=Path(root).resolve();rows=[]
    for name in relative_paths:
        if name.startswith(('docs/artifacts/','.sourceroi/security/')):raise ValueError('Historical evidence/identity deletion excluded')
        path=secure_path(root,name)
        if not path.is_file() or path.is_symlink() or path.stat().st_nlink!=1:raise ValueError('Preview requires an ordinary workspace file')
        rows.append({'path':path.relative_to(root).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'would_delete':False})
    return {'dry_run':True,'deletion_implemented':False,'files':rows}
