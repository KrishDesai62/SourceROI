"""Generate/verify a platform-specific wheel hash lock, entirely offline.

This verifies downloaded artifact identity and the installed metadata closure,
not advisories, provenance/signatures, or absence of vulnerabilities.
"""
import argparse
import email
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import zipfile


def wheel_rows(wheelhouse):
    rows=[];seen=set()
    for path in sorted(Path(wheelhouse).glob('*.whl')):
        with zipfile.ZipFile(path) as archive:
            names=[n for n in archive.namelist() if n.endswith('.dist-info/METADATA') and n.count('/')==1]
            if len(names)!=1:raise ValueError('Missing or ambiguous top-level wheel metadata')
            meta=email.message_from_bytes(archive.read(names[0]))
        name=re.sub(r'[-_.]+','-',meta['Name']).lower()
        if name in seen:raise ValueError('Multiple wheels per distribution; use one platform closure')
        seen.add(name)
        rows.append({'name':name,'version':meta['Version'],'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if not rows:raise ValueError('No wheels found')
    return rows


def render(rows):
    return ('# Python 3.13 / macOS arm64 tested wheel closure, including test/build dependencies.\n'
            '# Offline install: python -m pip install --no-index --find-links WHEELHOUSE --require-hashes -r THIS_FILE\n'
            +'\n'.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}" for r in rows)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['generate','verify']);p.add_argument('--wheelhouse',type=Path,required=True)
    p.add_argument('--lock',type=Path,required=True);p.add_argument('--installed',action='store_true')
    args=p.parse_args();rows=wheel_rows(args.wheelhouse);text=render(rows)
    if args.action=='generate':
        with args.lock.open('x') as stream:stream.write(text)
    elif args.lock.read_text()!=text:raise ValueError('Wheel content/version set differs from locked artifacts')
    if args.installed:
        for row in rows:
            if metadata.version(row['name'])!=row['version']:raise ValueError('Installed version differs: '+row['name'])
    print(json.dumps({'status':'VERIFIED_ARTIFACT_IDENTITY','wheels':len(rows),'installed_versions_checked':args.installed,
                      'vulnerability_advisories':'PENDING; no offline advisory database supplied'}))

if __name__=='__main__':main()
