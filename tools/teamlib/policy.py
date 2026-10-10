"""Trusted-base admission rules. Candidate programs and hooks are never executed."""
import os
import re
import stat
from pathlib import Path
from .contracts import TeamLibError, read_json, hash_file, safe_relative, ensure_no_symlinks, validate_record
from .package import validate_entry, scan_file, scan_text


MAINTENANCE_ROOT_FILES = frozenset({'AGENTS.md','README.md','library.json','library.example.json','.gitignore','00-打开团队能力库网页.html'})
MAINTENANCE_PREFIXES = ('docs/','tools/','schemas/','templates/','tests/','.github/')
GOVERNANCE_FILES = frozenset({'governance/policy.json','governance/members.json','governance/revocations.json'})
# Fixed first-release interfaces and the trusted checker must survive maintenance.
PROTECTED_MAINTENANCE_FILES = MAINTENANCE_ROOT_FILES | GOVERNANCE_FILES | frozenset({
    'tools/library.py','tools/check_submission.py','tools/check_ci.py',
    'tools/__init__.py','tools/teamlib/__init__.py',
    'tools/teamlib/contracts.py','tools/teamlib/config.py','tools/teamlib/package.py',
    'tools/teamlib/policy.py','tools/teamlib/snapshots.py',
    'schemas/meta.schema.json','schemas/manifest.schema.json','schemas/state.schema.json',
    'schemas/receipt.schema.json','schemas/run.schema.json','schemas/library.schema.json',
    '.github/workflows/check-submission.yml',
})


def _maintenance_path(path):
    return path in MAINTENANCE_ROOT_FILES or path in GOVERNANCE_FILES or path.startswith(MAINTENANCE_PREFIXES)


def _validate_maintenance(candidate, changed, after):
    _validate_governance(candidate,[p for p in changed if p in GOVERNANCE_FILES])
    for path in changed:
        if path not in after: continue
        if path in {'library.json','library.example.json'}:
            # Import and execute only the trusted baseline configuration validator.
            from .config import load_config
            load_config(candidate/path)
        elif path.startswith('schemas/') and path.endswith('.json'):
            # JSON syntax is data validation, not execution of candidate schema/code.
            read_json(candidate/path)


def _files(root):
    root = ensure_no_symlinks(root)
    if not root.is_dir(): raise TeamLibError('INVALID_PACKAGE', 'Snapshot root is missing.')
    files = {}; folded = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        if Path(directory) == root:
            dirs[:] = [d for d in dirs if d != '.git']
            names = [n for n in names if n != '.git']
        for name in dirs + names:
            path=Path(directory)/name; rel=path.relative_to(root).as_posix(); safe_relative(rel)
            if rel.casefold() in folded or path.is_symlink():
                raise TeamLibError('INVALID_PACKAGE', 'Snapshot contains links or case collisions.')
            folded.add(rel.casefold()); mode=path.lstat().st_mode
            if stat.S_ISREG(mode): files[rel]=hash_file(path)
            elif not stat.S_ISDIR(mode): raise TeamLibError('INVALID_PACKAGE', 'Special snapshot file was blocked.')
    return files


def _members(root):
    record=read_json(root/'governance'/'members.json')
    if set(record) != {'schema_version','members'} or record['schema_version'] != 1 or not isinstance(record['members'],list):
        raise TeamLibError('INVALID_PACKAGE', 'Trusted member registry is invalid.')
    result={}; logins=set()
    for row in record['members']:
        if not isinstance(row,dict) or set(row) != {'actor_key','github_login','role'} or row['role'] not in {'contributor','maintainer'} or not isinstance(row['actor_key'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',row['actor_key']) or not isinstance(row['github_login'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*',row['github_login']):
            raise TeamLibError('INVALID_PACKAGE', 'Trusted member mapping is invalid.')
        if row['actor_key'] in result or row['github_login'].casefold() in logins:
            raise TeamLibError('INVALID_PACKAGE', 'Duplicate trusted member mapping was blocked.')
        result[row['actor_key']]=row['role']; logins.add(row['github_login'].casefold())
    return result


def _validate_governance(root, changed):
    for rel in changed:
        value=read_json(root/rel)
        if rel.endswith('/members.json'): _members(root)
        elif rel.endswith('/policy.json'):
            if set(value) != {'schema_version','max_file_bytes','max_release_bytes','max_files','opaque_shares'} or value['schema_version'] != 1:
                raise TeamLibError('INVALID_PACKAGE', 'Governance policy shape is invalid.')
            for key in ('max_file_bytes','max_release_bytes','max_files'):
                if type(value[key]) is not int or value[key] <= 0:
                    raise TeamLibError('INVALID_PACKAGE', 'Governance material limit is invalid.')
            if not isinstance(value['opaque_shares'],list): raise TeamLibError('INVALID_PACKAGE','Opaque approvals must be a list.')
            for approval in value['opaque_shares']:
                if not isinstance(approval,dict) or set(approval) != {'sha256','scope','approved_by'} or not re.fullmatch(r'[0-9a-f]{64}',str(approval['sha256'])) or not isinstance(approval['scope'],str) or not approval['scope'] or _members(root).get(approval['approved_by']) != 'maintainer':
                    raise TeamLibError('INVALID_PACKAGE','Opaque sharing approval is invalid.')
        elif rel.endswith('/revocations.json'):
            if set(value) != {'schema_version','revocations'} or value['schema_version'] != 1 or not isinstance(value['revocations'],list):
                raise TeamLibError('INVALID_PACKAGE','Revocations record is invalid.')
            for row in value['revocations']:
                allowed={'source_commit','id','version','manifest_sha256','reason','replacement'}
                if not isinstance(row,dict) or set(row)-allowed or not {'reason'} <= row.keys() or not isinstance(row['reason'],str) or not row['reason'] or not ({'source_commit'} <= row.keys() or {'id','version','manifest_sha256'} <= row.keys()):
                    raise TeamLibError('INVALID_PACKAGE','Revocation requires an exact provenance selector.')
                if 'source_commit' in row and not re.fullmatch(r'[0-9a-f]{40}',str(row['source_commit'])):
                    raise TeamLibError('INVALID_PACKAGE','Revocation commit selector is invalid.')
                if 'id' in row:
                    from .contracts import validate_id,validate_version
                    validate_id(row['id']); validate_version(row.get('version'))
                    if not re.fullmatch(r'[0-9a-f]{64}',str(row.get('manifest_sha256'))): raise TeamLibError('INVALID_PACKAGE','Revocation digest is invalid.')


def _decision(allowed, code, message, changed=()):
    # Do not leak possibly sensitive branch-authored filenames; report only count.
    return {'allowed':allowed,'code':code,'message':message,'changed_paths_count':len(changed),'checks':{'trusted_base':True,'material_policy':allowed}}


def check_change(base, candidate, context):
    try:
        base=ensure_no_symlinks(base); candidate=ensure_no_symlinks(candidate)
        if not isinstance(context,dict): return _decision(False,'AUTH_REQUIRED','Trusted platform context is required.')
        public_write = context.get('public_write') is True
        members=_members(base); actor=context.get('actor_key')
        if public_write:
            # In public_write mode GitHub's authenticated collaborator permission
            # is the write authority. The registry is retained for attribution and
            # maintainer-only governance, but it is not an allowlist for commits.
            if not isinstance(actor, str) or context.get('proposal_author') != actor or context.get('role') not in {'contributor', 'maintainer'}:
                return _decision(False,'AUTH_REQUIRED','Authenticated GitHub Write identity is incomplete.')
        elif actor not in members or context.get('proposal_author') != actor or context.get('role') != members[actor]:
            return _decision(False,'AUTH_REQUIRED','Platform identity and trusted membership do not agree.')
        if context.get('reviewed_commit') is not None and context.get('reviewed_commit') != context.get('head_commit'):
            return _decision(False,'STATUS_UNVERIFIED','Approval does not bind the current candidate commit.')
        maintenance=context.get('proposal_kind') == 'maintenance'
        if maintenance and context.get('role') != 'maintainer':
            return _decision(False,'SCOPE_DENIED','Maintenance requires a trusted base maintainer.')
        policy=read_json(base/'governance'/'policy.json')
        _validate_governance(base,['governance/policy.json'])
        policy=dict(policy,_trusted_maintainers=[key for key,role in members.items() if role == 'maintainer'])
        before=_files(base); after=_files(candidate)
        changed=sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))
        if not changed: return _decision(False,'INVALID_PACKAGE','Proposal contains no material changes.')
        for path in changed:
            scan_text(path,'changed_path')
            # Include deleted old files: later removal cannot erase an outbound disclosure.
            if path in before: scan_file(base/path,policy=policy,location='base_changed_material')
            if path in after: scan_file(candidate/path,policy=policy,location='candidate_changed_material')
            if path not in after and not (maintenance and _maintenance_path(path) and path not in PROTECTED_MAINTENANCE_FILES):
                return _decision(False,'SCOPE_DENIED','Deleting critical or entry library material is forbidden.',changed)
            if re.fullmatch(r'entries/[^/]+/[^/]+/releases/[^/]+/.+',path) and path in before:
                return _decision(False,'SCOPE_DENIED','Published release material is immutable for every role.',changed)
        if maintenance:
            if any(not _maintenance_path(path) for path in changed):
                return _decision(False,'SCOPE_DENIED','Maintenance changes contain forbidden paths.',changed)
            _validate_maintenance(candidate,changed,after)
            return _decision(True,'OK','Trusted-base maintenance material policy passed.',changed)
        governance=context.get('proposal_kind') == 'governance'
        if governance:
            if context.get('role') != 'maintainer': return _decision(False,'SCOPE_DENIED','Governance requires a trusted maintainer.',changed)
            approved_governance=GOVERNANCE_FILES
            if any(p not in approved_governance and not re.fullmatch(r'entries/[^/]+/[^/]+/(state|meta)\.json',p) for p in changed):
                return _decision(False,'SCOPE_DENIED','Governance changes contain forbidden paths.',changed)
            _validate_governance(candidate,[p for p in changed if p in approved_governance])
        elif any(not re.fullmatch(r'entries/[^/]+/[^/]+/(meta\.json|state\.json|releases/[^/]+/.+)',p) for p in changed):
            return _decision(False,'SCOPE_DENIED','Ordinary publication is restricted to entry data.',changed)
        entry_ids={('/'.join(p.split('/')[1:3])) for p in changed if p.startswith('entries/')}
        if not governance and len(entry_ids) != 1:
            return _decision(False,'SCOPE_DENIED','Ordinary publication must contain exactly one entry.',changed)
        for identifier in entry_ids:
            entry_path='entries/'+identifier
            new=validate_entry(candidate/entry_path,policy=policy); nm=new['meta']; ns=new['entry_state']
            if nm['id'] != identifier or ns.get('id',identifier) != identifier:
                return _decision(False,'INVALID_PACKAGE','Entry identity does not match its directory.',changed)
            old_exists=(base/entry_path/'meta.json').exists()
            if not old_exists:
                if governance: return _decision(False,'SCOPE_DENIED','Governance cannot introduce new releases.',changed)
                if nm['author_key'] != actor or nm['owner_key'] != actor or len(new['releases']) != 1:
                    return _decision(False,'SCOPE_DENIED','New entry must belong to the platform author and contain one first release.',changed)
                first=next(iter(new['releases']))
                if ns['owner_key'] != actor or ns['recommended_version'] != first or ns['withdrawn_versions'] or ns['reviews'] or ns['verification']:
                    return _decision(False,'SCOPE_DENIED','Initial state must match the fixed unverified first-release template.',changed)
            else:
                old=validate_entry(base/entry_path,policy=policy); om=old['meta']; os_=old['entry_state']
                if nm['id'] != om['id'] or nm['author_key'] != om['author_key']:
                    return _decision(False,'SCOPE_DENIED','Original ID and author cannot change.',changed)
                old_versions=set(old['releases']); new_versions=set(new['releases'])-old_versions
                # Also forbid filling extra files into a published release.
                for version in old_versions:
                    prefix=entry_path+'/releases/'+version+'/'
                    old_tree={p:sha for p,sha in before.items() if p.startswith(prefix)}
                    new_tree={p:sha for p,sha in after.items() if p.startswith(prefix)}
                    if old_tree != new_tree: return _decision(False,'SCOPE_DENIED','Published release directories are immutable.',changed)
                if governance:
                    if new_versions or any(nm[k] != om[k] for k in om if k != 'owner_key'):
                        return _decision(False,'SCOPE_DENIED','Governance permits state and owner transfer only.',changed)
                    if ns['owner_key'] not in members:
                        return _decision(False,'SCOPE_DENIED','Transferred owner must already be a trusted member.',changed)
                    if not set(os_['withdrawn_versions']) <= set(ns['withdrawn_versions']):
                        return _decision(False,'SCOPE_DENIED','Withdrawn versions cannot silently become active.',changed)
                else:
                    if os_['owner_key'] != actor:
                        return _decision(False,'SCOPE_DENIED','Only the current trusted owner may publish this entry.',changed)
                    if ns != os_:
                        return _decision(False,'SCOPE_DENIED','Existing state changes require governance.',changed)
                    if len(new_versions) > 1:
                        return _decision(False,'SCOPE_DENIED','Ordinary publication allows at most one new version.',changed)
                    allowed_discovery={'title','summary','tags','aliases'}
                    if any(nm[key] != om[key] for key in om if key not in allowed_discovery):
                        return _decision(False,'SCOPE_DENIED','Canonical metadata changes require a governance proposal.',changed)
        return _decision(True,'OK','Trusted-base material policy passed.',changed)
    except (TeamLibError,OSError,KeyError,TypeError,ValueError):
        return _decision(False,'INVALID_PACKAGE','Candidate or trusted governance material failed validation.')
