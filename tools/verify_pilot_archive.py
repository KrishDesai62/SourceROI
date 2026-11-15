"""Trusted-digest verification and strict, bounded offline pilot extraction.

Obtain this verifier and the archive SHA-256 through a trusted channel BEFORE
running archive-supplied code. Local hashes are identity, not publisher approval.
"""
import argparse
from contextlib import contextmanager
import gzip
import tempfile
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

MAX_BYTES=256*1024*1024
MAX_MEMBERS=5000


@contextmanager
def bounded_tar(stream):
    # Bound gzip expansion, including metadata/padding, before tarfile parses PAX.
    with tempfile.TemporaryFile() as decoded:
        total=0
        with gzip.GzipFile(fileobj=stream) as compressed:
            for block in iter(lambda:compressed.read(1024*1024),b''):
                total+=len(block)
                if total>MAX_BYTES+8*1024*1024:raise ValueError('Decoded archive resource limit exceeded')
                decoded.write(block)
        decoded.seek(0)
        with tarfile.open(fileobj=decoded,mode='r:') as archive:yield archive


def safe_name(name):
    path=PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or str(path)!=name.rstrip('/'):
        raise ValueError('Unsafe or noncanonical archive path: '+name)
    return path


def verify(archive,expected,output=None):
    if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Expected SHA-256 must be 64 lowercase hex characters from a trusted channel')
    archive=Path(archive)
    if archive.stat().st_size>64*1024*1024:raise ValueError('Compressed archive exceeds 64 MiB limit')
    with archive.open('rb') as stream:
        actual=hashlib.file_digest(stream,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(stream.read()).hexdigest()
        if actual!=expected:raise ValueError('Trusted archive digest mismatch; nothing extracted')
        stream.seek(0)
        with bounded_tar(stream) as tar:
            members={};total=0
            for member in tar:
                path=safe_name(member.name)
                if path.parts[0]!='SourceROI-pilot':raise ValueError('Unexpected archive root')
                if member.name.rstrip('/') in members:raise ValueError('Duplicate archive member')
                if not (member.isfile() or member.isdir()):raise ValueError('Links and special archive entries are forbidden')
                if member.mode & 0o7000:raise ValueError('Privileged archive mode forbidden')
                total+=member.size
                if len(members)>=MAX_MEMBERS or total>MAX_BYTES or member.size>64*1024*1024:raise ValueError('Expanded archive resource limit exceeded')
                members[member.name.rstrip('/')]=member
            files={n:m for n,m in members.items() if m.isfile()}
            name='SourceROI-pilot/CHECKSUMS.json'
            if name not in files or files[name].size>1024*1024:raise ValueError('Bounded CHECKSUMS.json is required')
            def unique(pairs):
                result={}
                for k,v in pairs:
                    if k in result:raise ValueError('Duplicate checksum key')
                    result[k]=v
                return result
            manifest=json.load(tar.extractfile(files[name]),object_pairs_hook=unique)
            if not isinstance(manifest,dict):raise ValueError('Invalid checksum manifest')
            expected_files={}
            for rel,value in manifest.items():
                safe_name(rel)
                if not re.fullmatch('[0-9a-f]{64}',str(value)):raise ValueError('Invalid file digest')
                expected_files['SourceROI-pilot/'+rel]=value
            if set(files)!={name}|set(expected_files):raise ValueError('Unexpected or missing archive files')
            for n,m in members.items():
                if any(str(parent) in files for parent in PurePosixPath(n).parents if str(parent)!='.'):
                    raise ValueError('File/directory path collision')
                if m.isdir() and not any(f.startswith(n+'/') for f in files):raise ValueError('Unexpected empty directory')
            for n,value in expected_files.items():
                h=hashlib.sha256()
                with tar.extractfile(files[n]) as contents:
                    for block in iter(lambda:contents.read(1024*1024),b''):h.update(block)
                if h.hexdigest()!=value:raise ValueError('File digest mismatch: '+n)
            if output is not None:
                output=Path(output)
                if output.exists() or output.is_symlink():raise ValueError('Extraction destination exists; choose a fresh path')
                output.mkdir(mode=0o700) # exclusive creation; parent is operator controlled
                try:
                    for n,m in sorted(files.items()):
                        relative=PurePosixPath(n).relative_to('SourceROI-pilot')
                        target=output/str(relative);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                        with tar.extractfile(m) as contents,target.open('xb') as dest:shutil.copyfileobj(contents,dest)
                        target.chmod(0o600)
                except BaseException:
                    shutil.rmtree(output);raise
    return {'status':'VERIFIED_FILE_INTEGRITY','sha256':actual,'files':len(files)-1,
            'extracted':output is not None,'independent_security_review':'PENDING'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:print(json.dumps(verify(args.archive,args.sha256,args.output),indent=2))
    except (ValueError,OSError,tarfile.TarError,json.JSONDecodeError) as exc:p.exit(2,'Package verification failed: '+str(exc)+'\n')
