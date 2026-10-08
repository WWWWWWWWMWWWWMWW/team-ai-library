#!/usr/bin/env python3
"""AI maintenance: refresh navigation from the real configured shared branch."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.teamlib.catalog import build_catalog, collect_pending, write_catalog
from tools.teamlib.config import load_config
from tools.teamlib.contracts import TeamLibError
from tools.teamlib.snapshots import open_snapshot
from tools.teamlib.local_web import build_web_record, render_web


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'library.json')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'docs')
    parser.add_argument('--with-pending',action='store_true',help='Read current open requests separately from published entries.')
    args=parser.parse_args()
    try:
        config=load_config(args.config)
        snapshot=open_snapshot(config,Path(config['workspace']))
        pending=[]; pending_status='not_checked'
        if args.with_pending:
            try:
                pending=collect_pending(config); pending_status='available'
            except TeamLibError:
                pending_status='unavailable'
        record=build_catalog(snapshot,pending=pending,pending_status=pending_status)
        web_html=render_web(build_web_record(snapshot,record))
        paths=write_catalog(record,args.output_dir,web_html=web_html)
        print(json.dumps({'state':'prepared','code':'OK','capability_count':record['capability_count'],
                          'version_count':record['version_count'],'source_commit':snapshot['source_commit'],
                          'pending_status':pending_status,'outputs':paths},ensure_ascii=False))
        return 0
    except TeamLibError as exc:
        print(json.dumps({'state':'blocked','code':exc.code,'message':exc.message},ensure_ascii=False)); return 2
    except (OSError,ValueError):
        print(json.dumps({'state':'blocked','code':'LOCAL_CATALOG_FAILED','message':'Local directory could not be refreshed.'})); return 2


if __name__=='__main__': raise SystemExit(main())
