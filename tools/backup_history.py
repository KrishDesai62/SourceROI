"""Offline/local SQLite backup. Never overwrites a backup or restores live state."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.db import backup

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    print(json.dumps(backup(read_config(args.project), args.output), indent=2))
