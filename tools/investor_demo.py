"""Read-only replay of preserved synthetic evidence. No inference or approvals."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
    'docs/artifacts/native-tables/table-workflow-summary.json': None,
    'docs/artifacts/native-tables/table-release.json': None,
    'docs/artifacts/native-tables/table-data-ci.json': None,
    'docs/artifacts/native-tables/table-isolated-repair.json': None,
}

def replay():
    manifest=json.loads((ROOT/'docs/artifacts/production-beta/historical-hashes.json').read_text())
    for relative in EXPECTED:
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=manifest[relative]:
            raise ValueError('Historical evidence changed: '+relative)
    summary=json.loads((ROOT/'docs/artifacts/native-tables/table-workflow-summary.json').read_text())
    return {'mode':'IMMUTABLE_SYNTHETIC_REPLAY','live_inference':False,
            'human_approvals':'Synthetic fixture assertions only',
            'independent_validation':'PENDING','customer_outcomes':None,
            'results':summary,'evidence':list(EXPECTED),
            'optimization':'No independently verified quality-preserving savings; maintained baseline tied detection'}

if __name__=='__main__': print(json.dumps(replay(),indent=2))
