"""Complete temporary-workspace recovery, not deployment certification."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch
import zipfile
import pytest
from examples.knowledge_change.demo import workspace
from sourceroi.live import db
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.security import SecurityStore
from sourceroi.live.workspace_recovery import backup,restore,sha,identities,retention_preview
from sourceroi.live.workspace_lock import workspace_lock

@pytest.fixture
def setup(tmp_path):
    cfg=workspace(tmp_path/'project');store=SecurityStore(cfg['_root'],initialize=True)
    store.add_user('operator','Authored fixture password 2026','operator');session=store.login('operator','Authored fixture password 2026')
    freeze(cfg,Path(cfg['_root'])/'.sourceroi/snapshots'/('a'*32))
    rid=db.begin(cfg,'fixture',[]);db.finish(cfg,rid,{'kind':'fixture','verdict':'REVIEW','evidence':'authored'})
    artifact=Path(cfg['_root'])/'evidence';artifact.mkdir();(artifact/'answer.json').write_text('{"answer":"authored fixture"}')
    return cfg,store,rid,session


def make_backup(setup,tmp_path):return backup(setup[0]['_root'],tmp_path/'backup.zip',quiesced=True)


def test_full_restore_preserves_sources_snapshots_history_without_authority(setup,tmp_path):
    cfg,store,rid,session=setup;b=make_backup(setup,tmp_path);r=restore(b['archive'],tmp_path/'restored',expected_sha256=b['sha256'])
    target=Path(r['workspace']);restored=read_config(target)
    assert identities(target)==identities(cfg['_root'])
    assert db.get(restored,rid)['report']==db.get(cfg,rid)['report']
    assert (target/'evidence/answer.json').read_bytes()==(Path(cfg['_root'])/'evidence/answer.json').read_bytes()
    assert (target/'.sourceroi/snapshots'/('a'*32)/'snapshot.json').is_file()
    newstore=SecurityStore(target)
    assert not newstore.authenticate(session['token'])
    with newstore.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM approvals').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0
    newstore.add_user('new-operator','Reprovisioned fixture password','operator')
    assert newstore.login('new-operator','Reprovisioned fixture password')
    history=list((target/'.sourceroi/restored-history').glob('security-provenance-*.json'))
    assert len(history)==1 and 'password' not in json.loads(history[0].read_text())['users'][0]
    assert not (tmp_path/'restored/RESTORE_INCOMPLETE').exists()
    # A recovered workspace can itself be backed up without overwriting provenance.
    assert backup(target,tmp_path/'second.zip',quiesced=True)['status']=='VERIFIED'


def test_trusted_digest_checked_before_archive_extraction(setup,tmp_path):
    b=make_backup(setup,tmp_path)
    with pytest.raises(ValueError,match='SHA-256'):restore(b['archive'],tmp_path/'target',expected_sha256='0'*64)
    assert not (tmp_path/'target').exists()


def rewrite(path,transform):
    with zipfile.ZipFile(path) as z:contents={i.filename:z.read(i.filename) for i in z.infolist()}
    transform(contents)
    with zipfile.ZipFile(path,'w') as z:
        for name,value in contents.items():z.writestr(name,value)
    return sha(path)


@pytest.mark.parametrize('mode',['missing','altered','schema','extra','traversal'])
def test_invalid_archives_reject_without_target_creation(setup,tmp_path,mode):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    def change(contents):
        name=next(n for n in contents if n.startswith('workspace/sources/'))
        if mode=='missing':del contents[name]
        elif mode=='altered':contents[name]=b'altered source'
        elif mode=='schema':m=json.loads(contents['manifest.json']);m['version']=999;contents['manifest.json']=json.dumps(m).encode()
        elif mode=='extra':contents['workspace/extra.txt']=b'extra'
        else:contents['workspace/../../escaped']=b'bad'
    digest=rewrite(path,change)
    with pytest.raises(ValueError):restore(path,tmp_path/'target',expected_sha256=digest)
    assert not (tmp_path/'target').exists() and not (tmp_path/'escaped').exists()


def test_truncated_archive_is_not_a_complete_backup(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive']);path.write_bytes(path.read_bytes()[:100])
    with pytest.raises((ValueError,zipfile.BadZipFile)):restore(path,tmp_path/'target',expected_sha256=sha(path))
    assert not (tmp_path/'target').exists()


def test_source_identity_mismatch_even_if_file_hashes_are_rewritten(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    def change(contents):
        name=next(n for n in contents if n.startswith('workspace/sources/'));contents[name]=b'{"changed":true}'
        manifest=json.loads(contents['manifest.json']);manifest['files'][name[10:]]={'sha256':hashlib.sha256(contents[name]).hexdigest(),'bytes':len(contents[name])};contents['manifest.json']=json.dumps(manifest).encode()
    digest=rewrite(path,change)
    with pytest.raises(ValueError,match='identity mismatch'):restore(path,tmp_path/'target',expected_sha256=digest)
    assert (tmp_path/'target/RESTORE_INCOMPLETE').is_file() and not (tmp_path/'target/workspace').exists()


def test_existing_restore_target_never_overwritten(setup,tmp_path):
    b=make_backup(setup,tmp_path);dest=tmp_path/'target';dest.mkdir();(dest/'precious').write_text('preserve')
    with pytest.raises(ValueError,match='must be new'):restore(b['archive'],dest,expected_sha256=b['sha256'])
    assert (dest/'precious').read_text()=='preserve'


def test_lock_excludes_live_writer_and_backup_has_explicit_quiescence(setup,tmp_path):
    cfg,*_=setup
    with pytest.raises(ValueError,match='quiesced'):backup(cfg['_root'],tmp_path/'backup.zip')
    with workspace_lock(cfg['_root']):
        with pytest.raises(ValueError,match='Workspace busy'):make_backup(setup,tmp_path)
    assert not (tmp_path/'backup.zip').exists()


def test_symlink_and_hardlink_sources_rejected(setup,tmp_path):
    cfg,*_=setup;root=Path(cfg['_root']);p=root/'evidence/link';p.symlink_to(root/'project.json')
    with pytest.raises(ValueError,match='symlinks'):make_backup(setup,tmp_path)
    p.unlink()
    import os
    os.link(root/'project.json',p)
    with pytest.raises(ValueError,match='hardlinks'):make_backup(setup,tmp_path)


def test_interrupted_backup_not_published(setup,tmp_path):
    with patch('sourceroi.live.workspace_recovery.identities',side_effect=RuntimeError('fixture interrupted')):
        with pytest.raises(RuntimeError):make_backup(setup,tmp_path)
    assert not (tmp_path/'backup.zip').exists()


def test_retention_is_preview_only_and_confined(setup,tmp_path):
    cfg,*_=setup
    result=retention_preview(cfg['_root'],['evidence/answer.json'])
    assert result['dry_run'] and not result['deletion_implemented'] and not result['files'][0]['would_delete']
    for value in ('../outside','.sourceroi/security/identity.sqlite3','docs/artifacts/historical.json'):
        with pytest.raises((ValueError,FileNotFoundError)):retention_preview(cfg['_root'],[value])


def test_real_interrupted_restore_leaves_incomplete_marker(setup,tmp_path):
    b=make_backup(setup,tmp_path)
    code='''import sys,time
from pathlib import Path
from sourceroi.live.workspace_recovery import restore
original=Path.write_bytes
def stop(self,data):
 print('extracting',flush=True);time.sleep(30);return original(self,data)
Path.write_bytes=stop
restore(sys.argv[1],sys.argv[2],expected_sha256=sys.argv[3])
'''
    dest=tmp_path/'interrupted';p=subprocess.Popen([sys.executable,'-c',code,b['archive'],str(dest),b['sha256']],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='extracting';p.kill();p.wait(timeout=5)
        assert (dest/'RESTORE_INCOMPLETE').exists() and not (dest/'workspace').exists()
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=5)


def test_changed_files_during_backup_never_publish(setup,tmp_path):
    from sourceroi.live.workspace_recovery import inventory
    cfg,*_=setup;original=inventory;calls=[]
    def changed(root):
        calls.append(True)
        if len(calls)==2:(Path(root)/'evidence/answer.json').write_text('changed by uncooperative fixture')
        return original(root)
    with patch('sourceroi.live.workspace_recovery.inventory',side_effect=changed):
        with pytest.raises(ValueError,match='changed during'):make_backup(setup,tmp_path)
    assert not (tmp_path/'backup.zip').exists()
    assert list(tmp_path.glob('backup.zip.partial-*'))


def test_symlink_archive_member_and_duplicate_paths_rejected(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    with zipfile.ZipFile(path,'a') as z:
        member=zipfile.ZipInfo('workspace/evil');member.external_attr=(0o120777<<16);z.writestr(member,b'../../outside')
    with pytest.raises(ValueError,match='Unsafe'):restore(path,tmp_path/'target',expected_sha256=sha(path))


def test_backup_keeps_non_database_wal_named_file(setup,tmp_path):
    cfg,*_=setup;(Path(cfg['_root'])/'evidence/notes-wal').write_text('ordinary source evidence')
    b=make_backup(setup,tmp_path)
    with zipfile.ZipFile(b['archive']) as z:assert z.read('workspace/evidence/notes-wal')==b'ordinary source evidence'


def test_unexpected_identity_files_fail_instead_of_silent_omission(setup,tmp_path):
    cfg,*_=setup;(Path(cfg['_root'])/'.sourceroi/security/other-metadata.json').write_text('{}')
    with pytest.raises(ValueError,match='Unexpected'):make_backup(setup,tmp_path)


def test_actual_process_backup_interruption_has_no_published_archive(setup,tmp_path):
    cfg,*_=setup;dest=tmp_path/'killed-backup.zip'
    code='''import sys,time
from sourceroi.live import workspace_recovery as r
original=r.capture_db
def stop(*args):
 original(*args);print('captured',flush=True);time.sleep(30)
r.capture_db=stop;r.backup(sys.argv[1],sys.argv[2],quiesced=True)
'''
    p=subprocess.Popen([sys.executable,'-c',code,cfg['_root'],str(dest)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='captured';p.kill();p.wait(timeout=5)
        assert not dest.exists() and list(tmp_path.glob('killed-backup.zip.partial-*'))
        assert make_backup(setup,tmp_path)['status']=='VERIFIED'
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=5)


def test_quiescence_prevents_another_process_writing_through_cli(setup,tmp_path):
    cfg,*_=setup
    with workspace_lock(cfg['_root'],exclusive=True):
        result=subprocess.run([sys.executable,'-m','sourceroi','--project',cfg['_root'],'doctor'],capture_output=True,text=True,timeout=15)
    assert result.returncode!=0 and 'Workspace busy' in result.stderr


def test_duplicate_archive_entries_rejected(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    with zipfile.ZipFile(path,'a') as z:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');z.writestr('manifest.json',z.read('manifest.json'))
    with pytest.raises(ValueError,match='Duplicate'):restore(path,tmp_path/'target',expected_sha256=sha(path))


def test_invalid_manifest_shape_rejected_without_extraction(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    digest=rewrite(path,lambda contents:contents.update({'manifest.json':b'[]'}))
    with pytest.raises(ValueError,match='schema'):restore(path,tmp_path/'target',expected_sha256=digest)
    assert not (tmp_path/'target').exists()


def test_tampered_frozen_snapshot_rejected_even_with_updated_archive_hashes(setup,tmp_path):
    b=make_backup(setup,tmp_path);path=Path(b['archive'])
    def change(contents):
        name=next(n for n in contents if n.endswith('/snapshot.json'))
        value=json.loads(contents[name]);value['identity']='forged';contents[name]=json.dumps(value).encode()
        m=json.loads(contents['manifest.json']);m['files'][name[10:]]={'sha256':hashlib.sha256(contents[name]).hexdigest(),'bytes':len(contents[name])};contents['manifest.json']=json.dumps(m).encode()
    digest=rewrite(path,change)
    with pytest.raises(ValueError,match='snapshot tampered'):restore(path,tmp_path/'target',expected_sha256=digest)
    assert (tmp_path/'target/RESTORE_INCOMPLETE').exists() and not (tmp_path/'target/workspace').exists()
