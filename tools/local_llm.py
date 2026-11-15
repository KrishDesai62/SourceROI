"""Pinned, workspace-local inference setup. Downloads require explicit approval.

Nothing is downloaded by `plan`. `install --download-approved` is only for use
after the user has authorized the stated runtime/model download. No paid APIs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import tarfile

RUNTIME = {
    'name': 'llama.cpp b12345 macOS arm64', 'bytes': 16915889,
    'url': 'https://github.com/ggml-org/llama.cpp/releases/download/b12345/llama-b12345-bin-macos-arm64.tar.gz',
    'sha256': '2f12877f3bdd1e1ddbbf77f70e075cc52878f81478b90d10aebc28a231bbed3e',
}
MODEL = {
    'name': 'Qwen2.5-1.5B-Instruct Q4_K_M', 'bytes': 1117320736,
    'revision': '91cad51170dc346986eccefdc2dd33a9da36ead9',
    'url': 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf',
    'sha256': '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e',
    'license': 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/LICENSE',
}


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def download(spec, destination):
    import httpx
    if destination.exists():
        if checksum(destination) != spec['sha256']:
            raise ValueError('Existing download checksum mismatch; file left untouched')
        return
    temporary = destination.with_suffix(destination.suffix+'.partial')
    try:
        total = 0
        with httpx.stream('GET', spec['url'], follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            if response.url.scheme != 'https':
                raise ValueError('Download redirected away from HTTPS')
            with temporary.open('wb') as output:
                for block in response.iter_bytes(1024*1024):
                    total += len(block)
                    if total > spec['bytes']:
                        raise ValueError('Download exceeds pinned file size')
                    output.write(block)
        if total != spec['bytes'] or checksum(temporary) != spec['sha256']:
            raise ValueError('Download size/checksum mismatch')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def install(root, *, download_approved=False):
    if not download_approved:
        raise ValueError('Model/runtime download requires explicit user permission first')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Pinned runtime supports macOS Apple Silicon only')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive, model = root/'runtime.tar.gz', root/'model.gguf'
    download(RUNTIME, archive)
    download(MODEL, model)
    runtime = root/'runtime'
    runtime.mkdir(exist_ok=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(runtime, filter='data')
    servers = sorted(p for p in runtime.rglob('llama-server') if p.is_file())
    if len(servers) != 1:
        raise ValueError('Expected exactly one llama-server in the verified runtime archive')
    manifest = {'runtime': RUNTIME, 'model': MODEL, 'server': str(servers[0]), 'model_file': str(model)}
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def configure(project, root):
    """Write only model/runtime settings; never alter tasks, source text, or annotations."""
    project = Path(project).resolve()
    manifest = json.loads((Path(root)/'manifest.json').read_text())
    if checksum(manifest['model_file']) != MODEL['sha256']:
        raise ValueError('Local model checksum does not match the pinned plan')
    path = project/'project.json'
    cfg = json.loads(path.read_text())
    cfg['measurement_kind'] = 'local_generation'
    cfg['model'] = {'name': 'qwen2.5-1.5b-instruct-q4_k_m', 'base_url': 'http://127.0.0.1:8788/v1',
                    'local_only': True, 'runtime': 'llama_cpp', 'context_tokenizer': 'llama_cpp',
                    'response_format': 'json_object', 'compact_source_ids': True, 'seed': 1729, 'temperature': 0,
                    'max_output_tokens': 384, 'timeout_seconds': 180,
                    'input_price_per_million_usd': None, 'output_price_per_million_usd': None}
    cfg['local_inference_manifest'] = {'model': MODEL, 'runtime': RUNTIME}
    # Configuring a model must never silently expand the caller's call budget.
    cfg.setdefault('settings', {}).setdefault('max_model_calls_per_run', 8)
    path.write_text(json.dumps(cfg, indent=2)+'\n')
    return cfg


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['plan', 'install', 'configure', 'serve'])
    p.add_argument('--root', type=Path, default=Path('workspace/.local-llm'))
    p.add_argument('--project', type=Path)
    p.add_argument('--download-approved', action='store_true')
    args = p.parse_args()
    if args.command == 'plan':
        print(json.dumps({'runtime': RUNTIME, 'model': MODEL,
                          'total_download_bytes': MODEL['bytes']+RUNTIME['bytes'],
                          'permission_required': True, 'inference_host': '127.0.0.1'}, indent=2))
    elif args.command == 'install':
        print(json.dumps(install(args.root, download_approved=args.download_approved), indent=2))
    elif args.command == 'configure':
        if args.project is None:
            p.error('configure requires --project')
        configure(args.project, args.root)
        print('Configured genuinely local inference; task/source files unchanged')
    else:
        import subprocess
        manifest = json.loads((args.root/'manifest.json').read_text())
        if checksum(manifest['model_file']) != MODEL['sha256']:
            raise ValueError('Local model checksum mismatch')
        command = [manifest['server'], '--model', manifest['model_file'], '--alias', 'qwen2.5-1.5b-instruct-q4_k_m',
                   '--host', '127.0.0.1', '--port', '8788', '--ctx-size', '4096',
                   '--parallel', '1', '--threads', '4', '--n-gpu-layers', '99', '--no-webui']
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from sourceroi.live.experiment import runtime_lease
        print('Interactive runtime only: this path has no complete experiment accounting. Do not use for bounded validation.',file=sys.stderr)
        with runtime_lease():
            raise SystemExit(subprocess.call(command))


if __name__ == '__main__':
    main()
