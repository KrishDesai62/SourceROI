"""One immutable handoff using existing onboarding/review/study/adapters.

Copied historical answers are exposed retrospective material, not hidden final
labels. Independent final/source-owner inputs and participant records stay empty.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from sourceroi.live.config import read_config,secure_path
from sourceroi.live.ingest import scan_sources
from tools.independent_validation import template
from tools.release_review_packet import export,score
ROOT=Path(__file__).resolve().parents[1]


def build(baseline,candidate,release,output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('External package destination exists')
    baseline=Path(baseline).resolve();candidate=Path(candidate).resolve()
    if any(output==r or r.is_relative_to(output) or output.is_relative_to(r) for r in (baseline,candidate)):
        raise ValueError('Package must be separate from source workspaces')
    report=json.loads(Path(release).read_text());before=read_config(baseline);after=read_config(candidate)
    if any(not report.get('versions',{}).get(k) for k in ('test_set_version','baseline_configuration','candidate_configuration')):
        raise ValueError('Complete source, benchmark and configuration execution versions required for an independent handoff')
    pending=export(report,baseline,candidate) # Verifies actual source versions first.
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='external-package-') as temp:
        root=Path(temp)/'package';root.mkdir();(root/'retrospective').mkdir();(root/'independent').mkdir();(root/'integration').mkdir();(root/'study').mkdir()
        for name,cfg in [('baseline',before),('candidate',after)]:
            target=root/'retrospective'/name;target.mkdir();src=Path(cfg['_root']);documents,_=scan_sources(cfg)
            relative=[Path('project.json'),Path(cfg.get('benchmark','benchmark.jsonl'))]
            if (src/'snapshot.json').exists():relative.append(Path('snapshot.json'))
            if cfg.get('data_provenance'):relative.append(Path(cfg['data_provenance']))
            relative += [Path(d['path']) for d in documents]
            for rel in set(relative):
                origin=secure_path(src,str(rel));dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,dest)
        def write(path,value):(root/path).write_text(json.dumps(value,indent=2)+'\n')
        write('retrospective/release.json',report);write('retrospective/pending-claims.json',pending)
        write('retrospective/pending-score.json',score(pending,[]));write('independent/annotation-template.json',template())
        write('independent/authorized-reviewers.json',[])
        write('study/outcomes-template.json',{'status':'PENDING_REAL_PARTICIPANTS','participants':[],'sessions':[],
            'arms':['maintained_full_suite','maintained_with_diff','sourceroi'],
            'required_equivalent_inputs':['source versions','approved factual changes','protected behavior','answer/evidence labels','review requirements'],
            'outcome_fields':['active_reviewer_seconds','manual_edits','corrections','missed_failures','release_decision_correct','diagnosis_correct','diagnosis_usefulness','integration_seconds','actual_model_calls','actual_tokens','end_to_end_ms'],
            'human_effort_savings':None,'instructions':'Preregister real participant identities/case assignment/order and exclusions. Use existing maintenance_study.py logger; supplement actual observed outcomes here. Empty fields are not observations.'})
        for source,dest in [('docs/CONNECT_EXISTING_RAG.md','integration/CONNECT_EXISTING_RAG.md'),('docs/EXTERNAL_EVALUATION_KIT.md','integration/EXTERNAL_EVALUATION_KIT.md'),('docs/TABLE_EVIDENCE.md','integration/TABLE_EVIDENCE.md'),('examples/connected_rag/adapter.py','integration/adapter.py'),('docs/EVALUATION_MAINTENANCE_STUDY.md','study/protocol.md')]:
            shutil.copy2(ROOT/source,root/dest)
        (root/'README.md').write_text('''# SourceROI external evaluation package

Status: PENDING external source owner, independent reviewers and real participants.

Start with integration/EXTERNAL_EVALUATION_KIT.md. Run the commands from the
SourceROI repository with BUNDLE set to this package's absolute path. This package
requires that repository/tools; its manifest records the implementation hashes.
No model weights, credentials, runtime or fabricated human events are included.

retrospective/: real before/after documents and preserved outputs for independent
claim review AFTER exposure. Existing expected answers are development labels.
These cases cannot be treated as hidden final evaluation.

independent/: unfilled new-document annotation protocol and reviewer allowlist.
Real owners establish answers/evidence/intended/protected changes BEFORE outputs;
freeze with tools/independent_validation.py. Review ambiguous claims as PENDING
with a note, never fabricate a supported verdict to complete a packet.

study/: unfilled three-arm outcomes and existing event-logging protocol. No
human effort, integration saving or customer application has been observed.

Do not edit this sealed package in place. Copy templates into a separate working
folder; write reviewed/scored outputs under fresh names outside the package.
''')
        hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        write('manifest.json',{'kind':'external_evaluation_handoff','status':'PENDING','retrospective_is_exposed':True,
            'independent_labels_established':False,'independent_reviewers':[],'actual_human_sessions':0,'repository_required':True,
            'files':hashes,'python':sys.version,
            'environment_versions':{name:importlib.metadata.version(name) for name in ('httpx','fastapi','pypdf','uvicorn')},
            'implementation_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'sourceroi/live').glob('*.py'))+[ROOT/'tools'/name for name in ('independent_validation.py','source_owner_onboarding.py','release_review_packet.py','maintenance_study.py','check_external_release.py','prepare_external_evaluation.py')]}})
        root.replace(output)
    return {'output':str(output),'files':len(hashes),'status':'PENDING','new_model_calls':0}


def verify(root):
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text())
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}-{'manifest.json'}
    if actual!=set(manifest['files']):raise ValueError('Package contains added or missing files')
    for rel,value in manifest['files'].items():
        path=secure_path(root,rel)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=value:raise ValueError('Package file integrity mismatch: '+rel)
    for rel,value in manifest['implementation_hashes'].items():
        if hashlib.sha256(secure_path(ROOT,rel).read_bytes()).hexdigest()!=value:raise ValueError('Implementation differs from the package snapshot: '+rel)
    return {'status':'VERIFIED_FILE_INTEGRITY','independent_validation':'PENDING','files':len(manifest['files'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build')
    for name in ('baseline','candidate','release','output'):b.add_argument('--'+name,type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--root',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.root) if a.action=='verify' else build(a.baseline,a.candidate,a.release,a.output),indent=2))


if __name__=='__main__':main()
