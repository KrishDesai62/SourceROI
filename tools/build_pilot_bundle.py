"""Package existing locked wheels and sdist; no downloads or model artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
from lock_pilot_dependencies import wheel_rows,render
from verify_pilot_archive import safe_name,MAX_BYTES,MAX_MEMBERS


def build(sdist,app_wheel,wheelhouse,lock,output,sdist_sha256):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new bundle destination')
    rows=wheel_rows(wheelhouse)
    if Path(lock).read_text()!=render(rows):raise ValueError('Dependency wheels differ from lock')
    if hashlib.sha256(Path(sdist).read_bytes()).hexdigest()!=sdist_sha256:raise ValueError('Trusted source distribution digest mismatch; nothing extracted')
    output.mkdir(parents=True)
    source=output/'source'
    with tarfile.open(sdist) as archive:
        seen=set();total=0
        for member in archive:
            safe_name(member.name)
            total+=member.size
            if not (member.isfile() or member.isdir()) or member.name in seen or member.mode & 0o7000 or total>MAX_BYTES or len(seen)>=MAX_MEMBERS:
                raise ValueError('Unsafe, duplicate or oversized source distribution member')
            seen.add(member.name)
        archive.extractall(source,filter='data')
    roots=[p for p in source.iterdir() if p.is_dir()]
    if len(roots)!=1:raise ValueError('Expected one source distribution root')
    wheels=output/'wheelhouse';wheels.mkdir()
    for row in rows:shutil.copy2(Path(wheelhouse)/row['file'],wheels/row['file'])
    shutil.copy2(app_wheel,wheels/Path(app_wheel).name)
    (output/'requirements.lock').write_text(render(wheel_rows(wheels)))
    (output/'START_HERE.md').write_text('''# SourceROI controlled pilot distribution

Internal synthetic acceptance distribution, not independent customer validation.
Python 3.13 / macOS arm64 only. No model weights, secrets or live inference.
Dependency hashes provide artifact identity, not publisher trust/security approval.

See source/sourceroi-0.2.0/FIRST_EXTERNAL_DEVELOPER.md for exact commands. Verify
CHECKSUMS.json against every file before installation/execution. A trusted
published archive SHA-256 is necessary to anchor this local manifest. Keep the
existing external-evaluation v2 archive and its frozen implementation unchanged.
''')
    hashes={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    (output/'CHECKSUMS.json').write_text(json.dumps(hashes,indent=2))
    return {'files':len(hashes),'dependency_wheels':len(rows),'application_wheels':1,'source_root':str(roots[0].relative_to(output))}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('sdist','app-wheel','wheelhouse','lock','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sdist-sha256',required=True,help='Trusted locally built source archive SHA-256; checked before extraction')
    print(json.dumps(build(**{k:v for k,v in vars(p.parse_args()).items()}),indent=2))
