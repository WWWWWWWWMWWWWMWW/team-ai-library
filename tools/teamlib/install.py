"""Materialize immutable releases and install only explicit, empty targets."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import TeamLibError, hash_file, read_json, write_json, validate_version, validate_id, safe_relative, validate_record


def _error(code, message):
    raise TeamLibError(code, message)


def safe_path(path):
    path = Path(path).absolute()
    if '..' in path.parts:
        _error('INVALID_PACKAGE', 'Parent traversal is not allowed')
    for part in [path, *path.parents]:
        if part.is_symlink():
            _error('INVALID_PACKAGE', 'Symbolic links are not allowed')
    return path


def relative_path(value):
    safe_relative(value)
    path = Path(value)
    if path.is_absolute() or not value or any(p in ('.','..') for p in value.split('/')):
        _error('INVALID_PACKAGE', 'Invalid portable path')
    return path


def _identity(capability_id, version):
    validate_id(capability_id)
    validate_version(version)


def inventory(root):
    root = safe_path(root)
    if not root.is_dir():
        _error('INVALID_PACKAGE', 'Material directory is missing')
    from .package import tree_files
    rows=[]
    for path in tree_files(root):
        safe_path(path)
        rows.append(dict(path=path.relative_to(root).as_posix(),sha256=hash_file(path),size=path.stat().st_size))
    return rows


def copy_tree(source, dest):
    rows = inventory(source)
    dest = safe_path(dest)
    if dest.exists():
        _error('CONFLICT', 'Candidate destination already exists')
    dest.mkdir(parents=True)
    for row in rows:
        out = dest / relative_path(row['path'])
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(source)/row['path'], out, follow_symlinks=False)
    return rows


def _catalog(snapshot):
    from .dependencies import load_catalog
    return load_catalog(Path(snapshot['root']))


def _closure(catalog, capability_id, version):
    from .dependencies import resolve_dependencies
    _identity(capability_id,version)
    return resolve_dependencies(catalog,(capability_id,version))


def _revocation_check(snapshot, package):
    path=Path(snapshot['root'])/'governance/revocations.json'
    if not path.is_file():
        _error('STATUS_UNVERIFIED','Current revocation records are unavailable')
    try:
        record=read_json(safe_path(path))
        allowed={'schema_version','revocations','revoked_commits','manifest_sha256s'}
        if not {'schema_version','revocations'}<=record.keys() or not record.keys()<=allowed or type(record['schema_version']) is not int or record['schema_version']!=1:
            _error('STATUS_UNVERIFIED','Current revocation structure is unsupported')
        revoked=record['revocations']
        if not isinstance(revoked,list): _error('STATUS_UNVERIFIED','Revocations must be an explicit list')
        for name,width in (('revoked_commits',40),('manifest_sha256s',64)):
            values=record.get(name,[])
            if not isinstance(values,list) or any(not isinstance(v,str) or not re.fullmatch(r'[0-9a-f]{'+str(width)+'}',v) for v in values) or len(values)!=len(set(values)):
                _error('STATUS_UNVERIFIED','Revoked digest list is invalid')
        for row in revoked:
            fields={'source_commit','manifest_sha256','id','version','reason','replacement'}
            if not isinstance(row,dict) or not row.keys()<=fields:
                _error('STATUS_UNVERIFIED','Revocation row is unsupported')
            selectors=set(row)&{'source_commit','manifest_sha256','id','version'}
            if not selectors or ('id' in selectors)!=('version' in selectors): _error('STATUS_UNVERIFIED','Revocation selector is incomplete')
            for name,width in (('source_commit',40),('manifest_sha256',64)):
                if name in row and (not isinstance(row[name],str) or not re.fullmatch(r'[0-9a-f]{'+str(width)+'}',row[name])):
                    _error('STATUS_UNVERIFIED','Revocation digest is invalid')
            for name in ('reason','replacement'):
                if name in row and (not isinstance(row[name],str) or not row[name].strip()):
                    _error('STATUS_UNVERIFIED','Revocation explanation must be a nonempty string')
            if 'id' in row:_identity(row['id'],row['version'])
    except TeamLibError:
        _error('STATUS_UNVERIFIED','Current revocation records are unavailable or invalid')
    if package['source_commit'] in record.get('revoked_commits',[]):
        _error('WITHDRAWN','The source commit is revoked')
    for release in package['releases']:
        if release['manifest_sha256'] in record.get('manifest_sha256s',[]):
            _error('WITHDRAWN','Release material is revoked')
        for row in revoked:
            if row.get('source_commit') == package['source_commit'] or row.get('manifest_sha256') == release['manifest_sha256'] or (row.get('id')==release['id'] and row.get('version')==release['version']):
                _error('WITHDRAWN','Release source has been revoked')


def check_current(config, workspace, package):
    from .snapshots import open_snapshot
    if not config:
        _error('STATUS_UNVERIFIED','Current configuration is required')
    if package['repository'] != config.get('remote') or package['shared_branch'] != config.get('shared_branch'):
        _error('INVALID_PACKAGE','Package source differs from the configured library')
    try:
        current = open_snapshot(config,safe_path(workspace))
    except TeamLibError as exc:
        if exc.code in ('CONFIG_MISSING','AUTH_REQUIRED'): raise
        _error('STATUS_UNVERIFIED','Latest availability could not be verified')
    catalog=_catalog(current)
    _revocation_check(current,package)
    for row in package['releases']:
        entry=catalog.get((row['id'],row['version']))
        if not entry: _error('DEPENDENCY_BLOCKED','Locked release is absent from current library')
        state=entry.get('state',{})
        withdrawn=state.get('withdrawn_versions',[])
        versions=[r.get('version') if isinstance(r,dict) else r for r in withdrawn]
        if row['version'] in versions: _error('WITHDRAWN','A locked release is withdrawn')
        if entry['manifest_sha256'] != row['manifest_sha256']:
            _error('INVALID_PACKAGE','Published material differs from the pinned identity')
    return current


def _portable(record):
    return {k:v for k,v in record.items() if k not in ('root','config')}


def verify_download(download):
    from .package import validate_release
    root=safe_path(download['root'])
    disk=read_json(safe_path(root/'download.json'))
    if _portable(download) != disk:
        _error('INVALID_PACKAGE','Download bookkeeping differs from its selected record')
    required={'schema_version','source_commit','repository','shared_branch','id','version','manifest_sha256','dependency_lock','releases','files'}
    if set(disk)!=required or disk.get('schema_version')!=1 or not re.fullmatch(r'[0-9a-f]{40}',str(disk.get('source_commit',''))) or not isinstance(disk.get('releases'),list) or not isinstance(disk.get('dependency_lock'),list):
        _error('INVALID_PACKAGE','Download metadata is invalid')
    expected=[]; catalog={}
    for row in download['releases']:
        if not isinstance(row,dict) or set(row)!={'id','version','manifest_sha256','path'} or not re.fullmatch(r'[0-9a-f]{64}',str(row.get('manifest_sha256',''))):
            _error('INVALID_PACKAGE','Release download metadata is invalid')
        _identity(row['id'],row['version'])
        canonical=f"releases/{row['id']}/{row['version']}"
        if row['path'] != canonical: _error('INVALID_PACKAGE','Release location differs from canonical layout')
        folder=root/relative_path(row['path'])
        if not safe_path(folder/'manifest.json').is_file(): _error('INVALID_PACKAGE','Downloaded release manifest is missing')
        manifest=validate_release(safe_path(folder))
        if isinstance(manifest,dict) and 'manifest' in manifest: manifest=manifest['manifest']
        if hash_file(folder/'manifest.json')!=row['manifest_sha256']:
            _error('INVALID_PACKAGE','Manifest material differs from its pinned digest')
        if manifest['id'] != row['id'] or manifest['version'] != row['version']:
            _error('INVALID_PACKAGE','Manifest identity differs from download')
        key=(row['id'],row['version'])
        if key in catalog: _error('DEPENDENCY_BLOCKED','Repeated installation position')
        catalog[key]=dict(manifest,manifest_sha256=row['manifest_sha256'],release_root=str(folder))
        expected.append(row)
    order=_closure(catalog,download['id'],download['version'])
    if set(order)!=set(catalog): _error('DEPENDENCY_BLOCKED','Download contains an incomplete or unrelated closure')
    lock=[dict(id=i,version=v,manifest_sha256=catalog[(i,v)]['manifest_sha256']) for i,v in order if (i,v)!=(download['id'],download['version'])]
    if lock!=download['dependency_lock']: _error('DEPENDENCY_BLOCKED','Dependency lock differs from actual manifests')
    rootrow=catalog[(download['id'],download['version'])]
    if rootrow['manifest_sha256']!=download['manifest_sha256']: _error('INVALID_PACKAGE','Root digest differs')
    actual=[r for r in inventory(root) if r['path']!='download.json']
    if actual!=download['files']: _error('INVALID_PACKAGE','Downloaded content differs from its inventory')
    return catalog


def fetch_release(snapshot, capability_id, version, dest):
    from .package import validate_release
    catalog=_catalog(snapshot); order=_closure(catalog,capability_id,version)
    dest=safe_path(dest)
    source_root=safe_path(snapshot['root'])
    if dest==source_root or source_root in dest.parents or dest in source_root.parents:
        _error('CONFLICT','Download destination overlaps the immutable snapshot')
    if dest.exists(): _error('CONFLICT','Download destination must not already exist')
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.teamlib-download-',dir=dest.parent))
    try:
        releases=[]
        for i,v in order:
            row=catalog[(i,v)]; source=Path(row['release_root'])
            validate_release(source)
            rel=f'releases/{i}/{v}'; copy_tree(source,stage/rel)
            releases.append(dict(id=i,version=v,manifest_sha256=row['manifest_sha256'],path=rel))
        package=dict(schema_version=1,source_commit=snapshot['source_commit'],repository=snapshot['repository'],shared_branch=snapshot['shared_branch'],id=capability_id,version=version,manifest_sha256=catalog[(capability_id,version)]['manifest_sha256'],dependency_lock=[{k:r[k] for k in ('id','version','manifest_sha256')} for r in releases if (r['id'],r['version'])!=(capability_id,version)],releases=releases,files=inventory(stage))
        write_json(stage/'download.json',package)
        package.update(root=str(stage),config=snapshot.get('config',{}))
        verify_download(package)
        check_current(package['config'],Path(snapshot['workspace']),package)
        os.rename(stage,dest)
        package['root']=str(dest)
        return package
    finally:
        if stage.exists(): shutil.rmtree(stage)


def _installed_tree(download, dest):
    copy_tree(Path(download['root'])/'releases',dest/'releases')


def local_changes(base_rows, actual_rows):
    base={r['path']:r for r in base_rows}; actual={r['path']:r for r in actual_rows}
    return [dict(path=p,change='added' if p not in base else 'removed' if p not in actual else 'modified') for p in sorted(set(base)|set(actual)) if base.get(p)!=actual.get(p)]


def create_receipt(download,target,workspace,baseline,installation_id,actual=None,recovery_backup=None):
    rows=inventory(target) if actual is None else actual
    baseline_rows=inventory(baseline)
    receipt={k:download[k] for k in ('repository','shared_branch','source_commit','id','version','manifest_sha256','dependency_lock','releases')}
    folder=safe_path(workspace)/'installations'/installation_id
    receipt.update(schema_version=1,installation_id=installation_id,target=str(target),baseline=str(baseline),baseline_files=baseline_rows,files=rows,local_changes=local_changes(baseline_rows,rows),installed_at=datetime.now(timezone.utc).isoformat(),receipt_path=str(folder/'receipt.json'))
    if recovery_backup is not None: receipt['recovery_backup']=str(recovery_backup)
    validate_record('receipt',receipt)
    write_json(folder/'receipt.json',receipt)
    return receipt


def target_boundary(target,workspace,config=None,source_root=None):
    """Explicit directory authorization never comes from editable receipt.target."""
    target=safe_path(target);workspace=safe_path(workspace);config=config or {}
    protected=[workspace/name for name in ('installations','snapshots','mirrors','runs')]
    if source_root is not None:protected.append(safe_path(source_root))
    if target==Path(target.anchor) or target==Path.home() or target==workspace or target in workspace.parents or target==Path(config.get('repository_root','/')):
        _error('CONFLICT','A dedicated installation target is required')
    for root in protected:
        if target==root or root in target.parents or target in root.parents:
            _error('CONFLICT','Installation target overlaps source or managed provenance')
    profiles=config.get('target_profiles',{})
    if profiles:
        matches=[profile for profile in profiles.values() if safe_path(profile['path'])==target]
        if not matches or any(profile.get('tool','library-directory')!='library-directory' for profile in matches):
            _error('CONFLICT','Target does not match a configured material installation profile')
    return target


def managed_receipt(receipt_path,receipt,workspace,config=None,source_root=None):
    """Independent local binding catches a damaged/rebound individual receipt.

    It is not a security boundary against an OS user who rewrites all records.
    """
    workspace=safe_path(workspace);receipt_path=safe_path(receipt_path)
    identity=receipt['installation_id']
    if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',identity):
        _error('CONFLICT','Installation identity is not a managed local identity')
    folder=workspace/'installations'/identity;canonical=folder/'receipt.json'
    if receipt_path!=canonical or receipt['receipt_path']!=str(canonical):
        _error('CONFLICT','Receipt is not controlled by the selected workspace')
    try:binding=read_json(safe_path(folder/'binding.json'))
    except TeamLibError:_error('CONFLICT','Independent installation binding is unavailable')
    expected=dict(schema_version=1,installation_id=identity,target=receipt['target'],repository=receipt['repository'],shared_branch=receipt['shared_branch'],id=receipt['id'])
    if type(binding.get('schema_version')) is not int or binding!=expected:
        _error('CONFLICT','Receipt differs from the independently managed target binding')
    target=target_boundary(Path(binding['target']),workspace,config,source_root)
    baseline=safe_path(receipt['baseline'])
    if folder not in baseline.parents or baseline.name!='baseline' or target==baseline:
        _error('CONFLICT','Baseline is outside the installation provenance directory')
    return target,baseline


def install_release(download,target,workspace):
    verify_download(download)
    identifiers=[row['id'] for row in download['releases']]
    if len(identifiers)!=len(set(identifiers)):
        _error('DEPENDENCY_BLOCKED','Multiple locked versions compete for one capability installation position')
    check_current(download.get('config'),workspace,download)
    workspace=safe_path(workspace)
    target=target_boundary(target,workspace,download.get('config'),download['root'])
    from .reuse import _immutable_material
    _,_,original=_immutable_material(download.get('config'),workspace,download)
    if download['files']!=original:
        _error('INVALID_PACKAGE','Download differs from its immutable source commit')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        _error('CONFLICT','Installation target contains unknown existing material')
    target.parent.mkdir(parents=True,exist_ok=True)
    identity=str(uuid.uuid4()); folder=workspace/'installations'/identity
    folder.mkdir(parents=True)
    stage=Path(tempfile.mkdtemp(prefix='.teamlib-install-',dir=target.parent))
    existed=target.exists();switched=False
    try:
        _installed_tree(download,stage)
        copy_tree(stage,folder/'baseline')
        # Baseline is never a mixed local candidate. Read-only files discourage edits.
        for row in inventory(folder/'baseline'): (folder/'baseline'/row['path']).chmod(0o444)
        if target.exists(): target.rmdir()
        os.rename(stage,target)
        switched=True
        receipt=create_receipt(download,target,workspace,folder/'baseline',identity)
        binding=dict(schema_version=1,installation_id=identity,target=str(target),repository=download['repository'],shared_branch=download['shared_branch'],id=download['id'])
        write_json(folder/'binding.json',binding)
        return receipt
    except Exception:
        # Keep the prepared material, restore the original empty/absent target,
        # and remove only this operation's incomplete success bookkeeping.
        if switched:
            os.rename(target,stage)
            if existed:target.mkdir()
            for name in ('receipt.json','binding.json'):
                path=safe_path(folder/name)
                if path.exists():path.unlink()
            try:
                write_json(folder/'failed-install.json',dict(schema_version=1,state='prepared',candidate=str(stage),target=str(target),retry='install again with the original explicit target'))
            except TeamLibError:pass
        else:
            if stage.exists():shutil.rmtree(stage)
            if existed and not target.exists():target.mkdir()
        raise
