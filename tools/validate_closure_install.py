"""Offline installed upgrade/rollback probe; authored identities, no inference."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/artifacts/phase3-closure'

def main():
    old=ROOT/'docs/artifacts/phase3/acceptance-wheel/sourceroi-0.2.0-py3-none-any.whl'
    new=OUT/'test-wheel/sourceroi-0.2.0-py3-none-any.whl'
    records=[]
    with tempfile.TemporaryDirectory(prefix='sourceroi-installed-upgrade-') as d:
        base=Path(d); env=base/'venv';venv.EnvBuilder(with_pip=False).create(env)
        py=env/'bin/python';project=base/'project';project.mkdir();(project/'sources').mkdir()
        (project/'sources/plain.txt').write_text('Installed operational fixture.')
        (project/'benchmark.jsonl').write_text(json.dumps({'id':'fixture','question':'Fixture?','expected':'pending'})+'\n')
        (project/'project.json').write_text(json.dumps({'sources':[{'id':'source','path':'sources'}],'model':{'name':'not-called','base_url':'http://127.0.0.1:1/v1','local_only':True}}))
        def run(args):
            p=subprocess.run([str(x) for x in args],cwd=base,text=True,capture_output=True,timeout=120)
            records.append({'command':[str(x) for x in args],'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:raise RuntimeError(p.stderr)
            return p.stdout
        def code(body):return run([py,'-I','-c',body])
        def install(wheel):run([sys.executable,'-m','pip','--python',py,'install','--no-index','--no-deps','--force-reinstall',wheel])
        run([sys.executable,'-m','pip','--python',py,'install','--no-index','--find-links',ROOT/'workspace/pilot-acceptance/wheelhouse','--require-hashes','-r',ROOT/'requirements-pilot-py313-macos-arm64.lock'])
        install(old)
        prefix=f"from pathlib import Path; from sourceroi.live.security import SecurityStore; root=Path({str(project)!r}); "
        code(prefix+"s=SecurityStore(root,initialize=True); s.add_user('fixture','Development fixture password only','operator'); t=s.login('fixture','Development fixture password only')['token']; (root/'token').write_text(t); print('old schema initialized')")
        install(new)
        code(prefix+"\ntry: SecurityStore(root)\nexcept ValueError as e: assert 'auth-migrate' in str(e); print('implicit migration refused')\nelse: raise AssertionError('migration bypass')")
        run([env/'bin/sourceroi','--project',project,'auth-migrate'])
        code(prefix+"s=SecurityStore(root); assert s.authenticate((root/'token').read_text()) is None; assert s.login('fixture','Development fixture password only'); print('old session revoked; credential retained')")
        install(old)
        code(prefix+"\ntry: SecurityStore(root)\nexcept ValueError: print('rollback refused newer schema')\nelse: raise AssertionError('rollback bypass')")
        code(f"from sourceroi.live.api import create_app\nfor auth in (None,False):\n try: create_app({str(project)!r},authenticated=auth)\n except ValueError: print('rollback service refused',auth)\n else: raise AssertionError('unauthenticated rollback')")
        install(new)
        run([py,'-I',ROOT/'docs/artifacts/phase3/install-smoke.py'])
    result={'status':'VERIFIED_INTERNAL_INSTALLED_PROBE','old_wheel_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_wheel_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'steps':records,'real_model_generations':0,'limitations':'Same-host fresh environment; supported auth-aware rollback only. No production upgrade or independent review.'}
    (OUT/'installed-upgrade-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('VERIFIED installed upgrade, rollback refusal, TXT/PDF/DOCX smoke; zero inference')

if __name__=='__main__':main()
