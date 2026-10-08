"""Exact, same-snapshot dependency resolution; never choose an implicit latest."""
from pathlib import Path
from .contracts import (TeamLibError,read_json,hash_file,validate_record,
                        validate_version,validate_id,ensure_no_symlinks)


def load_catalog(snapshotroot):
    root=ensure_no_symlinks(Path(snapshotroot).absolute());entries=root/'entries'
    records={}
    if not entries.exists():return records
    ensure_no_symlinks(entries)
    for author in sorted(entries.iterdir()):
        ensure_no_symlinks(author)
        if not author.is_dir():raise TeamLibError('INVALID_PACKAGE','Entries root must contain author directories.')
        for entry in sorted(author.iterdir()):
            ensure_no_symlinks(entry)
            if not entry.is_dir():raise TeamLibError('INVALID_PACKAGE','Author directory must contain capability directories.')
            identifier=author.name+'/'+entry.name;validate_id(identifier)
            meta=read_json(entry/'meta.json');state=read_json(entry/'state.json')
            validate_record('meta',meta);validate_record('state',state)
            if meta['id']!=identifier or meta['owner_key']!=state['owner_key']:
                raise TeamLibError('INVALID_PACKAGE','Capability identity or owner differs from its trusted state.')
            if state.get('id',identifier)!=identifier:
                raise TeamLibError('INVALID_PACKAGE','State identity does not match its capability.')
            releases=ensure_no_symlinks(entry/'releases')
            if not releases.is_dir():raise TeamLibError('INVALID_PACKAGE','Capability releases are missing.')
            versions=set()
            for release in sorted(releases.iterdir()):
                ensure_no_symlinks(release)
                if not release.is_dir():raise TeamLibError('INVALID_PACKAGE','Release must be a directory.')
                version=release.name;validate_version(version);versions.add(version)
                manifest=read_json(release/'manifest.json');validate_record('manifest',manifest)
                if (manifest['id'],manifest['version'])!=(identifier,version):
                    raise TeamLibError('INVALID_PACKAGE','Manifest identity differs from its release path.')
                records[(identifier,version)]={**manifest,'manifest_sha256':hash_file(release/'manifest.json'),
                                             'release_root':str(release),'state':state,'meta':meta}
            recommended=state['recommended_version']
            if recommended is not None and recommended not in versions:
                raise TeamLibError('INVALID_PACKAGE','Recommended version is missing.')
            if not set(state['withdrawn_versions'])<=versions:
                raise TeamLibError('INVALID_PACKAGE','Withdrawn version is missing.')
    return records


def resolve_dependencies(records,root):
    root=tuple(root);done=set();visiting=set();ordered=[]
    def visit(key):
        if key in visiting:raise TeamLibError('DEPENDENCY_BLOCKED','Dependency cycle detected.')
        if key in done:return
        if key not in records:raise TeamLibError('DEPENDENCY_BLOCKED','Exact dependency version is missing.')
        visiting.add(key)
        for dependency in records[key].get('dependencies',[]):
            dep=(dependency.get('id'),dependency.get('version'))
            if dep not in records:raise TeamLibError('DEPENDENCY_BLOCKED','Exact dependency version is missing.')
            digest=dependency.get('manifest_sha256')
            if not digest or digest!=records[dep].get('manifest_sha256'):
                raise TeamLibError('DEPENDENCY_BLOCKED','Dependency manifest digest differs from the lock.')
            visit(dep)
        visiting.remove(key);done.add(key);ordered.append(key)
    visit(root)
    return ordered
