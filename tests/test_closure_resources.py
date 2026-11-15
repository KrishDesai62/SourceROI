"""Real process admission/cleanup and fixed-operation analytical negatives."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from unittest.mock import patch
import pytest
from sourceroi.live import runtime_resources as r,parser_boundary as b
from sourceroi.live.analysis_boundary import call


def stop(p):
    if p.poll() is None:p.kill();p.wait(timeout=5)


def test_two_real_processes_share_quota_and_death_releases_slot():
    code='from sourceroi.live.runtime_resources import admission;import time\nwith admission():\n print("held",flush=True);time.sleep(30)'
    children=[subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    try:
        for p in children:assert p.stdout.readline().strip()=='held'
        with pytest.raises(ValueError,match='Global runtime capacity'): 
            with r.admission(.05):pytest.fail('Third process must not enter')
        stop(children[0])
        with r.admission(.5):pass
    finally:
        for p in children:stop(p)


def test_global_capacity_stays_owned_until_steward_stops(tmp_path):
    code='''import sys
from pathlib import Path
from sourceroi.live import parser_boundary as b
b.supervise([sys.executable,'-c',"import os,time;from pathlib import Path;Path('ready').write_text(str(os.getpid()));time.sleep(30)"],Path(sys.argv[1]),wall=10)
'''
    process=subprocess.Popen([sys.executable,'-c',code,str(tmp_path)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        until=time.monotonic()+3
        while not (tmp_path/'ready').exists() and time.monotonic()<until:time.sleep(.02)
        assert (tmp_path/'ready').exists();stop(process)
        # Steward receives the same OS lock descriptor, so cleanup/re-admission
        # relies on process termination rather than expiring a wall-clock lease.
        pid=int((tmp_path/'ready').read_text())
        with r.admission(.5):
            until=time.monotonic()+3
            while time.monotonic()<until:
                try:
                    with r.admission(.05):pass
                    break
                except ValueError:time.sleep(.02)
            state=subprocess.run(['/bin/ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
            assert not state or state.startswith('Z')
    finally:stop(process)


def test_killed_scratch_requires_forensic_export_before_cleanup(tmp_path):
    code='''from sourceroi.live.runtime_resources import scratch;import time
with scratch() as (work,fd):
 (work/'source.txt').write_text('authored forensic input');print(work.parent.name,flush=True);time.sleep(30)
'''
    process=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        ident=process.stdout.readline().strip();assert ident.startswith('op-')
        active=r.inspect_cleanup(ids=[ident]);assert active['operations'][0]['state']=='ACTIVE'
        stop(process)
        preview=r.inspect_cleanup(ids=[ident]);assert not preview['operations'][0]['deleted']
        with pytest.raises(ValueError,match='forensic'):r.inspect_cleanup(delete=True,ids=[ident])
        result=r.inspect_cleanup(delete=True,ids=[ident],archive_directory=tmp_path/'forensics')
        assert result['operations'][0]['deleted'] and Path(result['operations'][0]['forensic_archive']).is_file()
        import zipfile
        with zipfile.ZipFile(result['operations'][0]['forensic_archive']) as z:assert z.read('work/source.txt')==b'authored forensic input'
    finally:stop(process)


def test_low_disk_and_retention_pressure_fail_closed(monkeypatch):
    from collections import namedtuple
    Usage=namedtuple('Usage','total used free')
    monkeypatch.setattr(r.shutil,'disk_usage',lambda _:Usage(1000,999,1))
    with pytest.raises(ValueError,match='free-disk'):
        with r.admission(.01):pass


def test_cleanup_cannot_accept_arbitrary_paths():
    with pytest.raises(ValueError,match='operation identity'):r.inspect_cleanup(ids=['../../historical'])


def test_analytical_selection_cannot_forge_evidence():
    chunks=[{'id':'source::x#0','text':'Original value is 4.','title':'Source','source_id':'source'}]
    with patch.object(b,'run',return_value=[{**chunks[0],'text':'Forged approval'}]):
        with pytest.raises(ValueError,match='changed registered evidence'):call('search',question='value',chunks=chunks,k=1)


def test_unrecognized_analytical_operation_never_dispatches():
    with pytest.raises(ValueError,match='fixed pure'):call('review',reviewer='admin')


def test_analytical_corpus_bound_rejects_without_worker():
    chunks=[{'id':'duplicate','text':'x'}]*50001
    with patch.object(b,'run',side_effect=AssertionError('No dispatch')):
        with pytest.raises(ValueError,match='bounded'):call('search',question='x',chunks=chunks,k=1)


def test_real_large_retrieval_obeys_wall_deadline():
    chunks=[{'id':str(i),'source_id':'s','title':'Source','text':('adversarial token'+str(i)+' ')*150} for i in range(4000)]
    original=b.supervise
    def tight(command,cwd,**kwargs):return original(command,cwd,**{**kwargs,'wall':.15})
    with patch.object(b,'supervise',side_effect=tight):
        with pytest.raises(ValueError,match='deadline|terminated'):call('search',question='adversarial token',chunks=chunks,k=10)


def test_cleanup_handles_verified_creation_interruption(tmp_path):
    import secrets
    directory=r.root()/('op-'+secrets.token_hex(16));directory.mkdir(mode=0o700);(directory/'work').mkdir(mode=0o700)
    result=r.inspect_cleanup(delete=True,ids=[directory.name],archive_directory=tmp_path/'forensics')
    assert result['operations'][0]['deleted']


def test_sandbox_blocks_replacement_exec(tmp_path):
    code="from pathlib import Path;import os\ntry:os.execv('/usr/bin/true',['true'])\nexcept PermissionError:Path('blocked').write_text('yes')"
    b.supervise([sys.executable,'-c',code],tmp_path,sandbox=True,wall=3)
    assert (tmp_path/'blocked').read_text()=='yes'


def test_directory_substitution_cannot_read_outside_workspace(tmp_path,monkeypatch):
    root=tmp_path/'root';inside=root/'nested';inside.mkdir(parents=True);(inside/'doc.txt').write_text('authorized')
    outside=tmp_path/'outside';outside.mkdir();(outside/'doc.txt').write_text('private outside data')
    original=os.open;changed=[]
    def swap(path,flags,*args,**kwargs):
        if path=='nested' and kwargs.get('dir_fd') is not None and not changed:
            changed.append(True);inside.rename(root/'saved');inside.symlink_to(outside,target_is_directory=True)
        return original(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',swap)
    with pytest.raises((ValueError,OSError)):b.snapshot(inside/'doc.txt',root)
    assert changed


def test_both_source_roots_are_protected_in_shared_analysis(tmp_path):
    work=tmp_path/'work';work.mkdir();old=tmp_path/'baseline';old.mkdir();new=tmp_path/'candidate';new.mkdir();(old/'secret').write_text('private')
    code=f"from pathlib import Path\ntry:Path({str(old/'secret')!r}).read_text()\nexcept PermissionError:Path('denied').write_text('yes')"
    b.supervise([sys.executable,'-c',code],work,sandbox=True,protected_root=[old,new],wall=3)
    assert (work/'denied').read_text()=='yes'
