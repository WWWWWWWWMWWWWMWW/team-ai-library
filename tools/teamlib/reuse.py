"""Read-only reuse gate, local run records, and explicit derived provenance."""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .contracts import TeamLibError, read_json, write_json, validate_record, hash_file
from .install import safe_path, relative_path, inventory, verify_download, check_current, _catalog, _closure, _identity, managed_receipt


def _denied(message):
    raise TeamLibError('SCOPE_DENIED',message)


def _strings(value):
    return isinstance(value,list) and all(isinstance(x,str) and x for x in value)


def _version_parts(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*',value):
        _denied('Runtime version evidence is unsupported')
    parts=tuple(int(x) for x in value.split('.'))
    return parts+(0,)*(4-len(parts))


def _runtime_matches(actual,requirement):
    actual_parts=_version_parts(actual)
    for clause in requirement.split(','):
        match=re.fullmatch(r'\s*(>=|<=|==|>|<|=)?\s*([0-9]+(?:\.[0-9]+)*)\s*',clause)
        if not match: _denied('Runtime requirement needs explicit verification')
        op,value=match.groups();required=_version_parts(value)
        if not {'>=':actual_parts>=required,'<=':actual_parts<=required,'>':actual_parts>required,'<':actual_parts<required,'==':actual_parts==required,'=':actual_parts==required,None:actual_parts==required}[op]: return False
    return True


def _context_check(manifest,context):
    scope=context.get('task_scope');environment=context.get('environment');authorized=context.get('effects_authorized')
    if not isinstance(scope,dict) or not isinstance(environment,dict) or not _strings(authorized):
        _denied('Task scope, actual environment, and effect authorization are required')
    if not set(scope)<= {'inputs','outputs','includes','excludes'}:
        _denied('Task scope uses unsupported fields')
    for key in ('inputs','outputs','includes','excludes'):
        if not _strings(scope.get(key)) and scope.get(key)!=[]: _denied('Task scope evidence is incomplete')
    expected=manifest['scope']
    for key in ('inputs','outputs','includes'):
        actual=set(scope[key]); allowed=set(expected[key])
        if not actual and expected[key]: _denied('Task scope evidence is incomplete')
        if 'any' not in allowed and not actual<=allowed: _denied('Task falls outside the capability scope')
    if set(scope['includes']) & set(expected['excludes']): _denied('Task uses an excluded capability scope')
    if not set(manifest['effects'])<=set(authorized): _denied('Required effects are not authorized for this task')
    compatibility=manifest['compatibility']
    if environment.get('os') not in compatibility['os'] and 'any' not in compatibility['os']:
        _denied('Actual operating system is not supported')
    for key in ('tools','capabilities'):
        if not _strings(environment.get(key)) and environment.get(key)!=[]: _denied('Actual tool or capability evidence is incomplete')
        if not set(compatibility[key])<=set(environment[key]): _denied('Required tools or capabilities are missing')
    runtimes=environment.get('runtimes')
    if not isinstance(runtimes,dict): _denied('Actual runtime evidence is required')
    for name,required in compatibility['runtimes'].items():
        if name not in runtimes or not _runtime_matches(runtimes[name],required): _denied('Actual runtime does not meet the requirement')


def _immutable_material(config,workspace,package):
    from .snapshots import open_snapshot
    snapshot=open_snapshot(config,workspace,commit=package['source_commit'])
    catalog=_catalog(snapshot);order=_closure(catalog,package['id'],package['version'])
    source_rows=[]
    releases=[]
    for i,v in order:
        row=catalog[(i,v)];rel=f'releases/{i}/{v}'
        releases.append(dict(id=i,version=v,manifest_sha256=row['manifest_sha256'],path=rel))
        for file in inventory(Path(row['release_root'])):
            source_rows.append(dict(file,path=rel+'/'+file['path']))
    source_rows.sort(key=lambda r:r['path'])
    if releases!=package['releases']:
        raise TeamLibError('DEPENDENCY_BLOCKED','Selected dependency closure differs from immutable source')
    lock=[{k:r[k] for k in ('id','version','manifest_sha256')} for r in releases if (r['id'],r['version'])!=(package['id'],package['version'])]
    if lock!=package['dependency_lock'] or catalog[(package['id'],package['version'])]['manifest_sha256']!=package['manifest_sha256']:
        raise TeamLibError('DEPENDENCY_BLOCKED','Selected lock differs from immutable source')
    return catalog,order,source_rows


def preflight_reuse(config,selection,context,workspace):
    workspace=safe_path(workspace)
    if not isinstance(selection,dict) or len(selection)!=1 or not set(selection)<= {'download_path','receipt_path'}:
        raise TeamLibError('INVALID_PACKAGE','Select one complete download or installed receipt')
    if 'download_path' in selection:
        root=safe_path(selection['download_path']); package=read_json(root/'download.json')
        package.update(root=str(root),config=config)
        verify_download(package)
        actual=[r for r in inventory(root) if r['path']!='download.json']
        receipt_path=None
    else:
        receipt_path=safe_path(selection['receipt_path']); package=read_json(receipt_path)
        validate_record('receipt',package)
        canonical=workspace/'installations'/package['installation_id']/'receipt.json'
        if receipt_path!=canonical or package['receipt_path']!=str(canonical):
            raise TeamLibError('INVALID_PACKAGE','Receipt belongs to a different workspace')
        root,baseline=managed_receipt(receipt_path,package,workspace,config)
        actual=inventory(root)
        if inventory(baseline)!=package.get('baseline_files'):
            raise TeamLibError('INVALID_PACKAGE','Installed upstream baseline has changed')
    # Never inherit old availability evidence, even when the source is pinned.
    current=check_current(config,workspace,package)
    catalog,order,original=_immutable_material(config,workspace,package)
    if actual!=original:
        raise TeamLibError('INVALID_PACKAGE','Actual capability or dependency material is a local adaptation; original-version evidence cannot be inherited')
    checks=[];sources=[];verification=[]
    current_catalog=_catalog(current)
    for i,v in order:
        row=catalog[(i,v)];manifest=row.get('manifest',row)
        _context_check(manifest,context)
        source={k:package[k] for k in ('repository','source_commit')}
        source.update(id=i,version=v,manifest_sha256=row['manifest_sha256'])
        if receipt_path: source['receipt_path']=str(receipt_path)
        sources.append(source)
        state=current_catalog[(i,v)]['state']
        for evidence in state.get('verification',[]):
            if evidence.get('id')==i and evidence.get('version')==v and evidence.get('manifest_sha256')==row['manifest_sha256']:
                verification.append(dict(id=i,version=v,evidence=evidence,applicability='not inferred'))
        checks.append(dict(id=i,version=v,integrity=True,current_availability=True,scope=True,environment=True,effects_authorized=True))
    return dict(state='prepared',sources=sources,checks=checks,business_verified=False,execution_authorized=False,verification=verification,next_action='Read the material and use it only within the current task authorization; record actual results locally')


def _scan_record(value):
    from .package import scan_text
    if isinstance(value,dict):
        for key,item in value.items():
            if re.search(r'(?i)(password|token|secret|credential_value|raw_input|chat|private_input)',key):
                raise TeamLibError('INVALID_PACKAGE','Sensitive or raw data fields are not accepted in local records')
            _scan_record(item)
    elif isinstance(value,list):
        for item in value:_scan_record(item)
    elif isinstance(value,str): scan_text(value,'local_record')


def record_run(workspace,sources,result):
    allowed={'task_goal','environment','result','artifacts','change_summary','unverified','started_at','finished_at'}
    if not isinstance(result,dict) or not set(result)<=allowed:
        raise TeamLibError('INVALID_PACKAGE','Run records accept only a sanitized task summary')
    source_keys={'repository','id','version','manifest_sha256','source_commit','receipt_path'}
    sanitized=[]
    for source in sources:
        sanitized.append({k:v for k,v in source.items() if k in source_keys})
    now=datetime.now(timezone.utc).isoformat()
    record=dict(schema_version=1,run_id=str(uuid.uuid4()),started_at=result.get('started_at',now),finished_at=result.get('finished_at',now),sources=sanitized)
    record.update({k:result[k] for k in ('task_goal','environment','result','artifacts','change_summary','unverified') if k in result})
    _scan_record(record);validate_record('run',record)
    path=safe_path(workspace)/'runs'/(record['run_id']+'.json')
    write_json(path,record)
    return dict(record,record_path=str(path))


def derived_provenance(source,changed_files,change_summary):
    required={'repository','id','version','manifest_sha256','source_commit'}
    if not isinstance(source,dict) or not required<=source.keys() or not _strings(changed_files) or not isinstance(change_summary,str) or not change_summary:
        raise TeamLibError('INVALID_PACKAGE','Derived provenance requires a complete origin and explicit changes')
    for name,width in (('source_commit',40),('manifest_sha256',64)):
        if not isinstance(source[name],str) or not re.fullmatch(r'[0-9a-f]{'+str(width)+'}',source[name]):
            raise TeamLibError('INVALID_PACKAGE','Derived origin requires exact source and manifest digests')
    repository=source['repository']
    if not isinstance(repository,str) or not repository.strip() or repository.startswith('-') or any(ord(c)<32 for c in repository):
        raise TeamLibError('INVALID_PACKAGE','Derived origin repository is invalid')
    from urllib.parse import urlsplit
    if '://' in repository:
        try:
            parsed=urlsplit(repository)
            if not parsed.hostname or parsed.password is not None or (parsed.username is not None and parsed.scheme in ('http','https')) or parsed.query or parsed.fragment:
                raise ValueError()
        except ValueError:
            raise TeamLibError('INVALID_PACKAGE','Derived origin repository contains unsupported URL data') from None
    _identity(source['id'],source['version'])
    for path in changed_files:relative_path(path)
    result=dict(derived_from={k:source[k] for k in sorted(required)},changed_files=sorted(set(changed_files)),change_summary=change_summary,business_verified=False,unverified=['local adaptation has no inherited validation'])
    _scan_record(result)
    return result
