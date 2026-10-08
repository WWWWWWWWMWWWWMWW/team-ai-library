#!/usr/bin/env python3
"""AI-facing team capability library CLI. stdout is one truthful JSON result."""
import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.teamlib.contracts import TeamLibError,read_json,write_json,validate_id,validate_version
from tools.teamlib.config import load_config,normalize_directory,validate_layout


class Parser(argparse.ArgumentParser):
    def error(self,message):
        raise TeamLibError('INVALID_PACKAGE','Command arguments are missing or unsupported; use --help.')


def parser():
    root=Parser(description=__doc__)
    root.add_argument('--config',type=Path,default=ROOT/'library.json')
    root.add_argument('--workspace',type=Path)
    commands=root.add_subparsers(dest='operation',required=True)
    def sub(name):
        p=commands.add_parser(name)
        p.add_argument('--config',type=Path,default=argparse.SUPPRESS)
        p.add_argument('--workspace',type=Path,default=argparse.SUPPRESS)
        return p
    sub('doctor')
    p=sub('validate');p.add_argument('--entry',required=True,type=Path)
    p=sub('search');p.add_argument('--query',required=True)
    for name in ('fetch','install'):
        p=sub(name);p.add_argument('--id',required=True);p.add_argument('--version',required=True)
        if name=='fetch':p.add_argument('--dest',required=True,type=Path)
        else:p.add_argument('--target',required=True)
    p=sub('propose');p.add_argument('--entry',required=True,type=Path)
    p=sub('status');p.add_argument('--request',required=True);p.add_argument('--kind',choices=['proposal','governance'],default='proposal');p.add_argument('--expected',type=Path)
    p=sub('check-reuse');p.add_argument('--selection',required=True,type=Path);p.add_argument('--context',required=True,type=Path)
    p=sub('update');p.add_argument('--receipt',required=True,type=Path);p.add_argument('--version',required=True)
    p=sub('withdraw');p.add_argument('--id',required=True);p.add_argument('--version',required=True);p.add_argument('--reason',required=True)
    p=sub('record-run');p.add_argument('--sources',required=True,type=Path);p.add_argument('--summary',required=True,type=Path)
    p=sub('derive');p.add_argument('--source',required=True,type=Path);p.add_argument('--changes',required=True,type=Path)
    return root


def _portable(value):
    if isinstance(value,dict):return {k:_portable(v) for k,v in value.items() if k!='config'}
    if isinstance(value,list):return [_portable(v) for v in value]
    if isinstance(value,Path):return str(value)
    return value


def _settings(args):
    config=load_config(args.config)
    if args.workspace:
        config['workspace']=normalize_directory(str(args.workspace),Path(config['repository_root']))
        validate_layout(config)
    return config,Path(config['workspace'])


def dispatch(args,operation_id):
    if args.operation=='validate':
        from tools.teamlib.package import validate_entry
        data=validate_entry(args.entry)
        return 'prepared',{'id':data['meta']['id'],'versions':list(data['releases']),'release_count':data['release_count'],'payload_executed':False},'Ask to share this material only when intended.'
    config,workspace=_settings(args)
    if args.operation=='doctor':
        if config['platform']=='unconfigured':
            raise TeamLibError('CONFIG_MISSING','Maintainer must configure the real repository, shared branch and platform.')
        from tools.teamlib.snapshots import open_snapshot
        snapshot=open_snapshot(config,workspace)
        data={'readable':True,'source_commit':snapshot['source_commit'],'python':sys.version.split()[0],
              'git_available':bool(shutil.which('git')),'installation_profiles':list(config['target_profiles']),
              'platform':config['platform'],'can_publish':False,'native_discovery_verified':False}
        if config['platform']=='github':
            from tools.teamlib.platform import doctor_platform
            try:
                data['platform_checks']=doctor_platform(config)
                if not data['platform_checks'].get('permissions',{}).get('push'):
                    raise TeamLibError('SCOPE_DENIED','The authenticated account can read but cannot submit a branch.')
                data['can_publish']=True
            except TeamLibError as exc:
                data['publishing_failure']={'code':exc.code,'message':exc.message}
                raise TeamLibError(exc.code,exc.message,data) from exc
        else:data.update(test_only=True,protected_branch_verified=False)
        return 'prepared',data,'Use supported operations within the current task authorization.'
    if args.operation=='record-run':
        from tools.teamlib.reuse import record_run
        sources=read_json(args.sources)
        if set(sources)!={'sources'} or not isinstance(sources['sources'],list):
            raise TeamLibError('INVALID_PACKAGE','Sources must be a sources-list record.')
        return 'reused',record_run(workspace,sources['sources'],read_json(args.summary)),'Run summary stays local; share only when requested.'
    if args.operation=='derive':
        from tools.teamlib.reuse import derived_provenance
        changes=read_json(args.changes)
        return 'prepared',derived_provenance(read_json(args.source),changes.get('changed_files'),changes.get('change_summary')),'Prepare an adapted entry only when sharing is requested.'
    if args.operation=='check-reuse':
        from tools.teamlib.reuse import preflight_reuse
        data=preflight_reuse(config,read_json(args.selection),read_json(args.context),workspace)
        return data['state'],data,data['next_action']
    if args.operation=='propose':
        from tools.teamlib.publish import propose_entry
        data=propose_entry(config,args.entry,workspace)
        return data['state'],data,'Wait for maintainer review; status checks must verify actual shared material.'
    if args.operation=='status':
        if args.kind=='governance':
            from tools.teamlib.platform import get_governance_request
            data=get_governance_request(config,args.request)
            return 'submitted',data,'Issue state is not proof that capability withdrawal has been applied.'
        from tools.teamlib.publish import verify_request
        expected=read_json(args.expected) if args.expected else None
        if expected is None:
            for path in sorted((workspace/'proposals').glob('*.json')):
                record=read_json(path)
                if str(record.get('request_id'))==args.request or record.get('url')==args.request:
                    expected=record;break
        if expected is None:raise TeamLibError('STATUS_UNVERIFIED','Original proposal receipt is required to verify publication material.')
        data=verify_request(config,args.request,expected)
        return data['state'],data,'Published material remains subject to current availability and task checks.'
    if args.operation=='withdraw':
        from tools.teamlib.platform import create_governance_request
        from tools.teamlib.package import scan_text
        validate_id(args.id);validate_version(args.version);scan_text(args.reason,'withdrawal reason')
        stable=hashlib.sha256(json.dumps([config['remote'],config['shared_branch'],args.id,args.version,args.reason],ensure_ascii=False).encode()).hexdigest()[:32]
        payload={'operation_id':stable,'id':args.id,'version':args.version,'reason':args.reason}
        path=workspace/'governance-requests'/(stable+'.json');write_json(path,payload)
        data=create_governance_request(config,'withdrawal',path)
        return data['state'],data,'Maintainer must create and merge a state proposal; no withdrawal is applied by creating an issue.'
    from tools.teamlib.snapshots import open_snapshot
    if args.operation=='search':
        from tools.teamlib.search import search_entries
        snapshot=open_snapshot(config,workspace)
        return 'prepared',{'source_commit':snapshot['source_commit'],'results':search_entries(Path(snapshot['root']),args.query)},'Read the selected version scope before downloading or using it.'
    from tools.teamlib.install import fetch_release,install_release
    if args.operation=='update':
        from tools.teamlib.updates import apply_update
        receipt=read_json(args.receipt);identifier=receipt.get('id');version=args.version
    else:identifier=args.id;version=args.version
    validate_id(identifier);validate_version(version)
    if args.operation=='install':
        profile=config['target_profiles'].get(args.target)
        if profile is None:raise TeamLibError('CONFIG_MISSING','The target profile is not configured.')
        if profile.get('tool','library-directory')!='library-directory':
            raise TeamLibError('TOOL_MISSING','Native AI target adapter is not implemented; use an explicit library-directory profile for material storage.')
    snapshot=open_snapshot(config,workspace)
    dest=args.dest if args.operation=='fetch' else workspace/'downloads'/operation_id
    download=fetch_release(snapshot,identifier,version,dest);download['config']=config
    if args.operation=='fetch':return 'downloaded',download,'Material is downloaded; installation and execution are separate operations.'
    if args.operation=='install':
        receipt=install_release(download,Path(profile['path']),workspace)
        receipt.update(installation_type='library-directory',native_discovery_verified=False)
        return 'installed',receipt,'Material is installed into the explicit library directory; native AI discovery is not verified.'
    if args.operation=='update':
        receipt=apply_update(args.receipt,download,workspace)
        return 'installed',receipt,'Updated material retains upstream baseline and any preserved local changes.'
    raise TeamLibError('INVALID_PACKAGE','Unsupported operation.')


def main(argv=None):
    operation_id=uuid.uuid4().hex;operation='unknown'
    try:
        if sys.version_info<(3,11):raise TeamLibError('TOOL_MISSING','Python 3.11 or newer is required.')
        args=parser().parse_args(argv);operation=args.operation
        state,data,next_action=dispatch(args,operation_id)
        code=data.get('code','OK')
        result={'protocol_version':1,'operation_id':data.get('operation_id',operation_id),'operation':operation,
                'state':state,'code':code,'message':'Operation completed at the reported stage.' if code=='OK' else data.get('message','Operation remains incomplete.'),
                'data':_portable(data),'checks':data.get('checks',[]),'next_action':next_action}
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0 if code=='OK' else 2
    except TeamLibError as exc:
        print(json.dumps({'protocol_version':1,'operation_id':operation_id,'operation':operation,'state':'blocked',
                          'code':exc.code,'message':exc.message,'data':_portable(exc.data),'checks':[],
                          'next_action':'Resolve the stated missing condition; existing materials are preserved.'},ensure_ascii=False))
        return 2
    except Exception:
        print(json.dumps({'protocol_version':1,'operation_id':operation_id,'operation':operation,'state':'blocked',
                          'code':'INTERNAL_ERROR','message':'Operation did not complete; no success is claimed.',
                          'data':{},'checks':[],'next_action':'Report the operation ID for diagnosis.'}))
        return 1


if __name__=='__main__':raise SystemExit(main())
