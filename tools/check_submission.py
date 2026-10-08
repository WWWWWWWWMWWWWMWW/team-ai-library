#!/usr/bin/env python3
"""Run only from the approved base. Candidate content is data, never code."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.teamlib.contracts import TeamLibError,read_json
from tools.teamlib.policy import check_change


def infer_proposal_kind(base,candidate):
    """Classify actual changes; the trusted base alone grants a role."""
    base=Path(base);candidate=Path(candidate)
    from tools.teamlib.contracts import hash_file
    from tools.teamlib.policy import _files, MAINTENANCE_ROOT_FILES, MAINTENANCE_PREFIXES
    before_files=_files(base);after_files=_files(candidate)
    changed={p for p in set(before_files)|set(after_files) if before_files.get(p)!=after_files.get(p)}
    if any(p in MAINTENANCE_ROOT_FILES or p.startswith(MAINTENANCE_PREFIXES) for p in changed):
        return 'maintenance'
    for name in ('members.json','policy.json','revocations.json'):
        before=base/'governance'/name;after=candidate/'governance'/name
        if before.exists()!=after.exists() or (before.exists() and hash_file(before)!=hash_file(after)):
            return 'governance'
    entries=base/'entries'
    if entries.exists():
        for before in entries.glob('*/*/state.json'):
            after=candidate/before.relative_to(base)
            if not after.exists() or hash_file(before)!=hash_file(after):return 'governance'
            meta=before.parent/'meta.json';other=candidate/meta.relative_to(base)
            if other.exists() and read_json(meta).get('owner_key')!=read_json(other).get('owner_key'):
                return 'governance'
    return 'publication'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',required=True,type=Path)
    parser.add_argument('--candidate',required=True,type=Path)
    parser.add_argument('--context',required=True,type=Path)
    args=parser.parse_args()
    try:
        context=read_json(args.context)
        context['proposal_kind']=infer_proposal_kind(args.base,args.candidate)
        decision=check_change(args.base,args.candidate,context)
        print(json.dumps(decision,ensure_ascii=False))
        return 0 if decision['allowed'] else 2
    except TeamLibError as exc:
        print(json.dumps({'allowed':False,'code':exc.code,'message':exc.message,'checks':[]},ensure_ascii=False))
        return 2
    except Exception:
        print(json.dumps({'allowed':False,'code':'INTERNAL_ERROR','message':'Trusted check did not complete.','checks':[]}))
        return 1


if __name__=='__main__':raise SystemExit(main())
