"""Acceptance tooling integrity tests; no customer/semantic or model claims."""
import hashlib
from pathlib import Path
import zipfile
import pytest
from tools.lock_pilot_dependencies import wheel_rows,render


def wheel(path, *, nested=False):
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('fixture-1.0.dist-info/METADATA','Name: Fixture\nVersion: 1.0\n')
        if nested:archive.writestr('fixture/_vendor/other-1.dist-info/METADATA','Name: Other\nVersion: 1\n')


def test_lock_uses_top_level_metadata_and_detects_artifact_drift(tmp_path):
    path=tmp_path/'fixture-1.0-py3-none-any.whl';wheel(path,nested=True)
    rows=wheel_rows(tmp_path);assert len(rows)==1 and rows[0]['name']=='fixture'
    assert rows[0]['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    original=render(rows)
    with zipfile.ZipFile(path,'a') as archive:archive.writestr('fixture/code.py','changed=True')
    assert render(wheel_rows(tmp_path))!=original


def test_lock_rejects_duplicate_distributions_and_empty_wheelhouse(tmp_path):
    with pytest.raises(ValueError,match='No wheels'):wheel_rows(tmp_path)
    wheel(tmp_path/'fixture-1.whl');wheel(tmp_path/'fixture-2.whl')
    with pytest.raises(ValueError,match='Multiple wheels'):wheel_rows(tmp_path)


def test_synthetic_pilot_callback_uses_observed_source_and_unknown_usage(tmp_path):
    import json
    from examples.connected_rag.synthetic_pilot_adapter import answer
    from sourceroi.live.config import read_config
    from sourceroi.live.ingest import scan_sources
    from sourceroi.live.data_ci import digest
    (tmp_path/'docs').mkdir();(tmp_path/'docs/return.txt').write_text('Return window is 14 days.')
    (tmp_path/'benchmark.jsonl').write_text('')
    (tmp_path/'project.json').write_text(json.dumps({'sources':[{'id':'policy','path':'docs'}],
        'model':{'name':'never-called','base_url':'http://127.0.0.1:1/v1'}}))
    result=answer(question='What is the return window?',task_id='x',snapshot_root=str(tmp_path),
        knowledge_manifest={'forged':'ignored'},scope={},contracts={})
    docs,_=scan_sources(read_config(tmp_path))
    manifest={d['id']:d['fingerprint'] for d in docs}
    assert result['answer']=='14' and result['knowledge_manifest']==manifest
    assert result['knowledge_version']==digest(manifest) and 'usage' not in result
    (tmp_path/'docs/conflict.txt').write_text('Return window is 999 days.')
    result=answer(question='What is the return window?',task_id='x',snapshot_root=str(tmp_path),
        knowledge_manifest={},scope={},contracts={})
    assert result['answer']=='INSUFFICIENT_EVIDENCE' and result['citations']==[]


def test_installed_record_audit_detects_changed_files(tmp_path,monkeypatch):
    import base64
    from tools import audit_pilot_environment as checker
    payload=tmp_path/'module.py';payload.write_bytes(b'original')
    value=base64.urlsafe_b64encode(hashlib.sha256(payload.read_bytes()).digest()).decode().rstrip('=')
    class Distribution:
        version='1.0'
        def read_text(self,name):return f'module.py,sha256={value},8\n'
        def locate_file(self,name):return tmp_path/name
    monkeypatch.setattr(checker.metadata,'distribution',lambda name:Distribution())
    monkeypatch.setattr(checker.sys,'prefix',str(tmp_path))
    lock=tmp_path/'requirements.lock';lock.write_text('fixture==1.0 --hash=sha256:unused\n')
    assert checker.audit(lock)['status']=='VERIFIED_INSTALLED_FILE_INTEGRITY'
    payload.write_bytes(b'tampered')
    result=checker.audit(lock)
    assert result['status']=='FAILED' and result['failures'][0]['reason']=='Installed file hash mismatch'


def test_table_validation_refuses_existing_output_without_model(tmp_path):
    import subprocess,sys
    dest=tmp_path/'existing';dest.mkdir()
    proc=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/validate_table_release.py'),
        '--output',str(dest),'--workspace',str(tmp_path/'new')],capture_output=True,text=True)
    assert proc.returncode!=0 and 'Output exists' in proc.stderr
    assert not (tmp_path/'new').exists()
