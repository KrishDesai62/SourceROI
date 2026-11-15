"""Offline installed-file/lock audit. Not a vulnerability advisory scan."""
import argparse
import base64
import csv
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path
import sys


def audit(lock):
    names=[line.split('==')[0] for line in Path(lock).read_text().splitlines() if line and not line.startswith('#')]
    rows=[];failures=[]
    for name in names+['sourceroi']:
        dist=metadata.distribution(name);record=dist.read_text('RECORD')
        if record is None:failures.append({'name':name,'reason':'Missing RECORD'});continue
        checked=0
        for rel,hash_value,size in csv.reader(io.StringIO(record)):
            if not hash_value:continue
            algorithm,value=hash_value.split('=',1)
            if algorithm!='sha256':failures.append({'name':name,'path':rel,'reason':'Unsupported record hash'});continue
            path=Path(dist.locate_file(rel)).resolve()
            if not path.is_relative_to(Path(sys.prefix).resolve()):
                failures.append({'name':name,'path':rel,'reason':'Installed path outside environment'});continue
            if not path.is_file() or base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).decode().rstrip('=')!=value:
                failures.append({'name':name,'path':rel,'reason':'Installed file hash mismatch'})
            checked+=1
        rows.append({'name':name,'version':dist.version,'hashed_files_checked':checked})
    return {'status':'FAILED' if failures else 'VERIFIED_INSTALLED_FILE_INTEGRITY','distributions':rows,'failures':failures,
            'vulnerability_advisories':'PENDING: no offline database supplied; online advisory queries not run',
            'signatures_and_publisher_trust':'PENDING; hashes are locally recorded identity, not authenticity',
            'scope':'Installed RECORD hashes only; unlisted added files and same-account manifest rewrite not detected'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lock',type=Path,required=True)
    result=audit(p.parse_args().lock);print(json.dumps(result,indent=2));raise SystemExit(1 if result['failures'] else 0)
