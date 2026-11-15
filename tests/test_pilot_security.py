"""Negative trust-boundary checks; no model or external service."""
import asyncio
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sourceroi.live.api import create_app
from sourceroi.live.http_guard import LocalBoundary, MAX_BODY, validate_browser_request
from sourceroi.live import db
from sourceroi.live.ingest import _extract, load_benchmark

@pytest.mark.parametrize('host,origin', [
    ('attacker.example', None), ('localhost:8765', 'http://localhost:9999'),
    ('127.0.0.1:8765', 'http://localhost:8765'), ('localhost', 'null'),
    ('localhost', 'https://localhost'), ('user@localhost', None),
    ('localhost:bad', None), ('localhost', 'http://localhost/path'),
])
def test_browser_boundary_refuses_untrusted_origins(host, origin):
    assert not validate_browser_request(host, origin)

@pytest.mark.parametrize('host', ['localhost:8765', '127.0.0.1:8765', '[::1]:8765'])
def test_same_origin_and_cli_clients(host):
    assert validate_browser_request(host, 'http://' + host)
    assert validate_browser_request(host)


def test_api_boundary_validation_pagination_and_readiness(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/v2/health', headers={'host': 'attacker.example'}).status_code == 403
        assert client.post('/api/v2/runs', headers={'origin': 'http://localhost:9999'}, json={}).status_code == 403
        assert client.post('/api/v2/runs', content='{}', headers={'content-type': 'text/plain'}).status_code == 415
        assert client.post('/api/v2/runs', content='x'*(MAX_BODY+1)).status_code == 413
        assert client.get('/api/v2/runs?limit=101').status_code == 422
        assert client.get('/api/v2/runs?offset=-1').status_code == 422
        health=client.get('/api/v2/health')
        assert len(health.headers['x-request-id']) == 32
        assert client.get('/api/v2/ready').status_code == 503


def test_streamed_body_bound_before_application():
    async def scenario():
        called=[]; sent=[]
        async def app(*args): called.append(True)
        chunks=iter([{'type':'http.request','body':b'x'*(MAX_BODY//2+1),'more_body':True}]*2)
        async def receive(): return next(chunks)
        async def send(message): sent.append(message)
        await LocalBoundary(app)({'type':'http','method':'POST','scheme':'http',
                                 'headers':[(b'host',b'localhost')],'client':('127.0.0.1',123)},receive,send)
        assert not called and sent[0]['status']==413
    asyncio.run(scenario())


def test_db_symlink_confinement_and_rollback(tmp_path):
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside';outside.mkdir()
    cfg={'_root':str(root)}
    (root/'.sourceroi').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError,match='escapes'): db.begin(cfg,'baseline',[])
    assert not list(outside.iterdir())
    (root/'.sourceroi').unlink();(root/'.sourceroi').mkdir()
    (root/'.sourceroi/runs.sqlite3').symlink_to(outside/'db')
    with pytest.raises(ValueError,match='symlinks'): db.begin(cfg,'baseline',[])
    (root/'.sourceroi/runs.sqlite3').unlink()
    rid=db.begin(cfg,'baseline',[])
    with pytest.raises(RuntimeError):
        with db.connect(cfg) as conn:
            conn.execute('DELETE FROM runs')
            raise RuntimeError('rollback')
    assert db.get(cfg,rid)['status']=='running'
    for _ in range(3): db.begin(cfg,'baseline',[])
    assert len(db.list_runs(cfg,2,offset=2))==2
    assert not {r['id'] for r in db.list_runs(cfg,2)} & {r['id'] for r in db.list_runs(cfg,2,offset=2)}


def test_document_prechecks_and_benchmark_limit(tmp_path):
    import zipfile
    fake=tmp_path/'fake.pdf';fake.write_text('plain text')
    with pytest.raises(ValueError,match='signature'): _extract(fake)
    doc=tmp_path/'bomb.docx'
    with zipfile.ZipFile(doc,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml',b'0'*(49*1024*1024))
    with pytest.raises(ValueError,match='inflated'): _extract(doc)
    bench=tmp_path/'benchmark.jsonl'
    with bench.open('wb') as f: f.truncate(12*1024*1024+1)
    with pytest.raises(ValueError,match='12MB'): load_benchmark({'_root':str(tmp_path)})


def test_backup_restore_and_no_overwrite(tmp_path):
    import hashlib
    import sqlite3
    root=tmp_path/'active';root.mkdir();cfg={'_root':str(root)}
    rid=db.begin(cfg,'baseline',[]);db.finish(cfg,rid,{'kind':'fixture','answer':'original'})
    dest=tmp_path/'backup.sqlite3'
    result=db.backup(cfg,dest)
    assert result['runs']==1 and result['sha256']==hashlib.sha256(dest.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError): db.backup(cfg,dest)
    with pytest.raises(ValueError,match='outside'): db.backup(cfg,root/'bad.sqlite3')
    restored=tmp_path/'restored';(restored/'.sourceroi').mkdir(parents=True)
    import shutil
    shutil.copy2(dest,restored/'.sourceroi/runs.sqlite3')
    assert db.get({'_root':str(restored)},rid)['report']['answer']=='original'
    assert db.get(cfg,rid)['report']['answer']=='original'


def test_legacy_source_and_benchmark_escape_refused(tmp_path):
    from sourceroi.corpus import load_project
    from sourceroi.store import save_baseline
    root=tmp_path/'legacy';root.mkdir();(root/'docs').mkdir()
    outside=tmp_path/'outside.txt';outside.write_text('private')
    (root/'benchmark.json').write_text('[{"id":"x"}]')
    cfg={'benchmark':'benchmark.json','sources':[{'id':'a','path':'docs'}]}
    (root/'project.json').write_text(json.dumps(cfg))
    (root/'docs/link.txt').symlink_to(outside)
    with pytest.raises(ValueError,match='escapes'): load_project(root)
    (root/'docs/link.txt').unlink();cfg['benchmark']='../outside.txt'
    (root/'project.json').write_text(json.dumps(cfg))
    with pytest.raises(ValueError,match='escapes'): load_project(root)
    (root/'.sourceroi').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError,match='escapes'): save_baseline({'root':str(root)}, {})


def test_body_timeout_never_invokes_application(monkeypatch):
    import sourceroi.live.http_guard as guard
    async def scenario():
        called=[];sent=[]
        async def app(*args):called.append(True)
        async def receive(): return {'type':'http.request','body':b''}
        async def timeout(coro, **kwargs):
            coro.close()
            raise asyncio.TimeoutError()
        async def send(message):sent.append(message)
        monkeypatch.setattr(guard.asyncio,'wait_for',timeout)
        await guard.LocalBoundary(app)({'type':'http','method':'POST','scheme':'http',
            'headers':[(b'host',b'localhost')]},receive,send)
        assert not called and sent[0]['status']==408
    asyncio.run(scenario())


def test_readiness_storage_probe_does_not_certify_production(tmp_path):
    (tmp_path/'docs').mkdir();(tmp_path/'benchmark.jsonl').write_text('')
    (tmp_path/'project.json').write_text(json.dumps({'id':'test','name':'test',
        'sources':[{'id':'docs','path':'docs'}], 'model':{'name':'unused','base_url':'http://127.0.0.1:8788/v1'}}))
    with TestClient(create_app(tmp_path)) as client:
        result=client.get('/api/v2/ready')
        assert result.status_code==200
        assert result.json()['production_ready'] is False
        assert result.json()['native_accounting']=='PENDING'


def test_investor_replay_is_explicitly_synthetic():
    from tools.investor_demo import replay
    result=replay()
    assert result['live_inference'] is False and result['customer_outcomes'] is None
    assert result['results']['strict_release']=='REVIEW'
    assert result['results']['repair_overall']=='INCONCLUSIVE'
