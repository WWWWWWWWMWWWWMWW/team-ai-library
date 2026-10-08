"""File-level three-way comparison with preserved originals and explicit apply."""
import os
import shutil
import tempfile
from pathlib import Path
from .contracts import TeamLibError, read_json, validate_record, write_json
from .install import inventory, safe_path, copy_tree, verify_download, check_current, create_receipt, _installed_tree, managed_receipt


def compare_update(base,local,upstream):
    return _compare_update(base,local,upstream,safe_path(local).parent)


def _compare_update(base,local,upstream,candidate_parent):
    roots=[safe_path(p) for p in (base,local,upstream)]
    for i,left in enumerate(roots):
        for right in roots[i+1:]:
            if left==right or left in right.parents or right in left.parents:
                raise TeamLibError('CONFLICT','Comparison material roots must not overlap')
    maps=[{r['path']:r for r in inventory(p)} for p in roots]
    candidate=Path(tempfile.mkdtemp(prefix='teamlib-update-',dir=safe_path(candidate_parent)))
    actions=[];conflicts=[]
    for name in sorted(set().union(*maps)):
        b,l,u=[m.get(name) for m in maps]
        if l==u: action='keep'; source=1 if l else None
        elif l==b: action='remove' if u is None else 'add' if b is None else 'update';source=2 if u else None
        elif u==b: action='keep';source=1 if l else None
        else: action='conflict';conflicts.append(name);source=1 if l else None
        actions.append(dict(path=name,action=action))
        if source is not None:
            out=candidate/name;out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(roots[source]/name,out,follow_symlinks=False)
    return dict(state='blocked' if conflicts else 'prepared',actions=actions,conflicts=conflicts,candidate=str(candidate),base=str(roots[0]),local=str(roots[1]),upstream=str(roots[2]),originals_preserved=True)


def apply_update(receipt_path,download,workspace):
    receipt_path=safe_path(receipt_path);receipt=read_json(receipt_path)
    validate_record('receipt',receipt)
    workspace=safe_path(workspace)
    target,baseline=managed_receipt(receipt_path,receipt,workspace,download.get('config'),download['root'])
    canonical=workspace/'installations'/receipt['installation_id']/'receipt.json'
    if receipt_path!=canonical or receipt.get('receipt_path')!=str(canonical):
        raise TeamLibError('CONFLICT','Receipt is not controlled by the selected workspace')
    if receipt['repository']!=download['repository'] or receipt['id']!=download['id']:
        raise TeamLibError('CONFLICT','Update has a different source identity')
    if inventory(baseline)!=receipt.get('baseline_files'):
        raise TeamLibError('INVALID_PACKAGE','Upstream baseline differs from the recorded original')
    verify_download(download);check_current(download.get('config'),workspace,download)
    from .reuse import _immutable_material
    _,_,new_original=_immutable_material(download.get('config'),workspace,download)
    if download['files']!=new_original:
        raise TeamLibError('INVALID_PACKAGE','Update download differs from its immutable source')
    _,_,original=_immutable_material(download.get('config'),workspace,receipt)
    if inventory(baseline)!=original:
        raise TeamLibError('INVALID_PACKAGE','Update baseline is not the immutable upstream original')
    folder=canonical.parent
    upstream=Path(tempfile.mkdtemp(prefix='upstream-',dir=folder))
    _installed_tree(download,upstream)
    # Compare per-capability files across version-directory changes. Rebase only
    # known old release prefixes, leaving unrelated local files untouched.
    new_versions={row['id']:row['version'] for row in download['releases']}
    if len(new_versions)!=len(download['releases']):
        raise TeamLibError('DEPENDENCY_BLOCKED','Multiple versions of one capability need an explicit target layout')
    mappings={row['path']:f"releases/{row['id']}/{new_versions[row['id']]}" for row in receipt['releases'] if row['id'] in new_versions}
    normalized=[]
    for source,label in ((baseline,'base'),(target,'local')):
        dest=Path(tempfile.mkdtemp(prefix='normalized-'+label+'-',dir=folder))
        names=set()
        for row in inventory(source):
            name=row['path']
            for old,new in mappings.items():
                if name.startswith(old+'/'):name=new+name[len(old):];break
            if name in names:
                raise TeamLibError('CONFLICT','Local release positions overlap the new upstream layout')
            names.add(name)
            out=dest/name;out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/row['path'],out,follow_symlinks=False)
        normalized.append(dest)
    # Comparison inputs stay in workspace; the *final* switch candidate must
    # be created beside the actual target, even when workspace is another volume.
    report=_compare_update(normalized[0],normalized[1],upstream,target.parent)
    if report['conflicts']:
        raise TeamLibError('CONFLICT','Update conflicts; originals and candidate preserved',report)
    token=Path(tempfile.mkdtemp(prefix='revision-',dir=folder))
    write_json(token/'prior-receipt.json',receipt)
    new_baseline=token/'baseline';copy_tree(upstream,new_baseline)
    for row in inventory(new_baseline): (new_baseline/row['path']).chmod(0o444)
    backup=target.parent/(target.name+'.teamlib-backup-'+token.name)
    if backup.exists(): raise TeamLibError('CONFLICT','Recovery location is occupied')
    # Candidate and target are on the same parent filesystem, so no cross-volume rename.
    os.rename(target,backup)
    try:
        os.rename(report['candidate'],target)
        new_receipt=create_receipt(download,target,workspace,new_baseline,receipt['installation_id'],recovery_backup=backup)
    except Exception:
        if target.exists(): os.rename(target,report['candidate'])
        os.rename(backup,target)
        raise
    return new_receipt
