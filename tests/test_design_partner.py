"""Design-partner preparation is offline; no external application is executed."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
from unittest.mock import patch
import pytest
from tools.verify_pilot_archive import verify
from tools.pilot_preflight import preflight,template,registration
from tools.pilot_events import record,summarize


def archive(tmp_path,extra=None,content=b'ok'):
    path=tmp_path/'bundle.tar.gz';sha=lambda b:hashlib.sha256(b).hexdigest()
    manifest={'source/ok.txt':sha(content)}
    with tarfile.open(path,'w:gz') as tar:
        for name,data in [('SourceROI-pilot/source/ok.txt',content),('SourceROI-pilot/CHECKSUMS.json',json.dumps(manifest).encode())]:
            m=tarfile.TarInfo(name);m.size=len(data);tar.addfile(m,io.BytesIO(data))
        if extra:
            m,data=extra;tar.addfile(m,io.BytesIO(data) if data else None)
    return path,sha(path.read_bytes())


@pytest.mark.parametrize('kind',['parent','absolute','symlink','hardlink','device','extra','duplicate','backslash'])
def test_archive_refuses_unsafe_members_before_output(tmp_path,kind):
    m=tarfile.TarInfo('SourceROI-pilot/extra');data=b''
    if kind=='parent':m.name='SourceROI-pilot/../../escape'
    if kind=='absolute':m.name='/tmp/escape'
    if kind=='symlink':m.type=tarfile.SYMTYPE;m.linkname='/tmp'
    if kind=='hardlink':m.type=tarfile.LNKTYPE;m.linkname='SourceROI-pilot/source/ok.txt'
    if kind=='device':m.type=tarfile.CHRTYPE
    if kind=='duplicate':m.name='SourceROI-pilot/source/ok.txt'
    if kind=='backslash':m.name='SourceROI-pilot/..\\escape'
    path,sha=archive(tmp_path,(m,data));dest=tmp_path/'out'
    with pytest.raises(ValueError):verify(path,sha,dest)
    assert not dest.exists()


def test_archive_digest_first_valid_extract_and_no_overwrite(tmp_path):
    path,sha=archive(tmp_path)
    with patch('tools.verify_pilot_archive.tarfile.open',side_effect=AssertionError('Must not parse before digest')):
        with pytest.raises(ValueError,match='digest mismatch'):verify(path,'0'*64,tmp_path/'bad')
    dest=tmp_path/'good';assert verify(path,sha,dest)['files']==1
    assert (dest/'source/ok.txt').read_bytes()==b'ok'
    with pytest.raises(ValueError,match='exists'):verify(path,sha,dest)


def project(root):
    root.mkdir();(root/'sources').mkdir();(root/'sources/policy.txt').write_text('Return window is 14 days.')
    (root/'benchmark.jsonl').write_text(json.dumps({'id':'returns','question':'How many days?','expected':'14'})+'\n')
    (root/'project.json').write_text(json.dumps({'sources':[{'id':'policy','path':'sources'}],
        'model':{'name':'never-called','base_url':'http://127.0.0.1:1/v1'}}))
    return root


def mapping(root):
    from sourceroi.live.data_ci import digest
    _,registered=registration(root)
    return {'version':1,'adapter':'DO_NOT_IMPORT.application:answer','protocol':'callback_v1',
        **registered,'knowledge_version':digest(registered['knowledge_manifest'])}


def test_preflight_checks_offline_export_without_importing_or_network(tmp_path):
    root=project(tmp_path/'project');data=mapping(root)
    with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('importlib.import_module',side_effect=AssertionError('No customer import')):
        assert preflight(root,data)['application_called'] is False
        assert template(root)['knowledge_manifest'] is None
    assert preflight(root,data)['runtime_mapping_and_generation']=='PENDING'


@pytest.mark.parametrize('drift',['passages','knowledge_manifest','knowledge_version','task_version','configuration_version','execution_identity'])
def test_preflight_rejects_missing_spoofed_and_stale_exports(tmp_path,drift):
    root=project(tmp_path/'project');data=mapping(root);data[drift]='wrong'
    with pytest.raises(ValueError):preflight(root,data)


def test_events_exclude_automation_time_and_preserve_unknowns(tmp_path):
    path=tmp_path/'events.jsonl'
    base={'session_id':'automation','origin':'automation'}
    record(path,{**base,'event':'setup_started'})
    record(path,{**base,'event':'setup_completed'})
    assert summarize(path)['operator_declared_active_seconds'] is None
    with pytest.raises(ValueError,match='Automation'):record(path,{**base,'event':'active_time','active_seconds':10})
    human={'session_id':'real-operator-declaration','origin':'operator','operator':'test declaration, not a person'}
    record(path,{**human,'event':'setup_started'})
    record(path,{**human,'event':'active_time','active_seconds':12})
    assert summarize(path)['operator_declared_active_seconds']==12
    assert summarize(path)['actual_independently_verified_human_time'] is None
    text=path.read_text();path.write_text(text.replace('12','13'))
    with pytest.raises(ValueError,match='integrity'):summarize(path)


def test_release_cli_requires_authorization_before_customer_import(tmp_path,monkeypatch):
    from tools.check_external_release import main
    monkeypatch.setattr('importlib.import_module',lambda *a:(_ for _ in ()).throw(AssertionError('No import without approval')))
    with pytest.raises(SystemExit) as exc:
        main(['--baseline','missing','--candidate','missing','--spec','missing','--approval','missing','--output',str(tmp_path/'never'), '--adapter','customer:answer'])
    assert exc.value.code==2 and not (tmp_path/'never').exists()


def test_archive_resource_limit_and_empty_directory(tmp_path,monkeypatch):
    import tools.verify_pilot_archive as guard
    path,sha=archive(tmp_path)
    monkeypatch.setattr(guard,'MAX_BYTES',1)
    with pytest.raises(ValueError,match='resource limit'):verify(path,sha)
    monkeypatch.setattr(guard,'MAX_BYTES',256*1024*1024)
    m=tarfile.TarInfo('SourceROI-pilot/unexpected');m.type=tarfile.DIRTYPE
    path,sha=archive(tmp_path,(m,b''))
    with pytest.raises(ValueError,match='empty directory'):verify(path,sha)


def test_dry_run_cli_uses_owned_documents_without_generation(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    bundle={'version':1,'owner':'synthetic test author; not independent','labels_established_at':'2020-01-01T00:00:00Z',
        'labels_from_evaluated_model':False,'before_documents':[{'source_id':'policy','name':'rules.txt','text':'Limit is 12.'}],
        'after_documents':[{'source_id':'policy','name':'rules.txt','text':'Limit is 14.'}],
        'tasks':[{'id':'limit','question':'What is the limit?','expected_before':'12','expected_after':'14','intended_change':True,
        'evidence_before':[{'document_id':'policy::rules.txt','quote':'Limit is 12.'}],
        'evidence_after':[{'document_id':'policy::rules.txt','quote':'Limit is 14.'}]}]}
    path=tmp_path/'input.json';path.write_text(json.dumps(bundle));dest=tmp_path/'dry'
    argv=[sys.executable,str(root/'tools/pilot_preflight.py'),'dry-run','--owner-input',str(path),'--output',str(dest)]
    proc=subprocess.run(argv,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    result=json.loads((dest/'dry-run.json').read_text())
    assert result['application_called'] is False and result['release_verdict'] is None
    assert result['model_calls']==0 and (dest/'accepted/snapshot.json').exists()
    assert not (dest/'release.json').exists()
    again=subprocess.run(argv,capture_output=True,text=True)
    assert again.returncode==2 and 'fresh project' in again.stderr
