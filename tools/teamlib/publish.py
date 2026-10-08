"""Prepare one sanitized proposal commit; publication is verified against fresh shared data."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .contracts import TeamLibError, ensure_no_symlinks, hash_file, read_json, write_json, validate_id
from .package import tree_files, validate_entry, validate_outbound, scan_text
from .policy import check_change
from .platform import doctor_platform, create_request, get_request, repository_name, _request_number
from .snapshots import open_snapshot

run_command = subprocess.run


def _git(root, *args, binary=False):
    command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-C', str(root), *args]
    try:
        result = run_command(command, shell=False, check=False, text=not binary,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except FileNotFoundError:
        raise TeamLibError('TOOL_MISSING', 'Git is unavailable.') from None
    except (OSError, subprocess.SubprocessError):
        raise TeamLibError('REMOTE_FAILED', 'Git operation failed or its result is unknown.') from None
    if result.returncode:
        raise TeamLibError('REMOTE_FAILED', 'Git rejected the proposal operation.')
    return result.stdout if binary else result.stdout.strip()


def _committed_material(root, commit, identifier):
    prefix = 'entries/' + identifier + '/'
    names = _git(root, 'ls-tree', '-r', '--name-only', commit, '--', prefix).splitlines()
    return {name: hashlib.sha256(_git(root, 'cat-file', 'blob', commit + ':' + name, binary=True)).hexdigest() for name in names}


def _material(root, prefix=''):
    return {prefix + p.relative_to(root).as_posix(): hash_file(p) for p in tree_files(root)}


def _copy_snapshot(root, destination):
    # Inspect the data tree before copying; never follow links or include repository config/hooks.
    for directory in root.iterdir():
        if directory.name == '.git': continue
        if directory.is_symlink(): raise TeamLibError('INVALID_PACKAGE', 'Trusted snapshot contains unsupported links.')
        if directory.is_dir():
            tree_files(directory)
            shutil.copytree(directory, destination / directory.name)
        elif directory.is_file(): shutil.copyfile(directory, destination / directory.name)
        else: raise TeamLibError('INVALID_PACKAGE', 'Trusted snapshot contains unsupported material.')


def _check_base(snapshot, candidate, context):
    decision = check_change(Path(snapshot['root']), candidate, context)
    if not decision['allowed']:
        raise TeamLibError(decision.get('code', 'SCOPE_DENIED'), 'Proposal failed trusted-base admission policy.')
    checker = ensure_no_symlinks(Path(snapshot['root']) / 'tools/check_submission.py')
    if not checker.is_file():
        raise TeamLibError('STATUS_UNVERIFIED', 'The trusted base does not contain its admission checker.')
    with tempfile.TemporaryDirectory(prefix='teamlib-check-') as temporary:
        context_file = Path(temporary) / 'context.json'; write_json(context_file, context)
        try:
            result = run_command([sys.executable, '-I', '-B', str(checker), '--base', str(snapshot['root']),
                                  '--candidate', str(candidate), '--context', str(context_file)],
                                 shell=False, check=False, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=60)
            checked = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            raise TeamLibError('STATUS_UNVERIFIED', 'Trusted-base checker could not be verified.') from None
        if result.returncode != 0 or checked.get('allowed') is not True:
            raise TeamLibError('SCOPE_DENIED', 'Trusted-base admission checker rejected the proposal.')
    return decision


def _trusted_policy(base):
    policy = read_json(base / 'governance/policy.json')
    policy['_trusted_maintainers'] = [r['actor_key'] for r in read_json(base / 'governance/members.json')['members'] if r.get('role') == 'maintainer']
    return policy


def _version_conflict(base_entry, candidate_entry):
    if not base_entry.exists(): return
    old = validate_entry(base_entry); new = validate_entry(candidate_entry)
    for version in set(old['releases']) & set(new['releases']):
        if _material(base_entry / 'releases' / version) != _material(candidate_entry / 'releases' / version):
            raise TeamLibError('CONFLICT', 'A published version already contains different material. Prepare a new version.')


def propose_entry(config, entry, workspace):
    entry = ensure_no_symlinks(entry); workspace = ensure_no_symlinks(workspace)
    validated = validate_entry(entry); identifier = validated['meta']['id']; validate_id(identifier)
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='proposal-', dir=workspace) as temporary:
        temp = Path(temporary); locked = temp / 'entry'; shutil.copytree(entry, locked)
        # Lock a verified copy so later user changes cannot race what is checked and sent.
        validated = validate_entry(locked); files = _material(locked, 'entries/' + identifier + '/')
        material_digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        doctor = doctor_platform(config)
        operation_id = hashlib.sha256(json.dumps([config['remote'], config['shared_branch'], doctor['actor_key'], identifier, material_digest]).encode()).hexdigest()[:32]
        record_path = workspace / 'proposals' / (operation_id + '.json')
        if record_path.exists():
            previous = read_json(record_path)
            if previous.get('files') != files or previous.get('repository') != config['remote']:
                raise TeamLibError('CONFLICT', 'Stored operation does not match the proposal material.')
            if previous.get('request_id'):
                return verify_request(config, previous['request_id'], previous)
        deployment={'deployment_mode':doctor.get('deployment_mode','protected'),
                    'owner_trial':doctor.get('owner_trial',False),
                    'hard_gate_enforced':doctor.get('hard_gate_enforced',False),
                    'manual_review_required':doctor.get('manual_review_required',True)}
        title = 'Team library proposal: ' + identifier
        commit_message = 'Team library proposal ' + identifier + '\n\nOperation: ' + operation_id
        body_file = temp / 'body.md'
        body_file.write_text('Review entry ' + identifier + '.\nBusiness behavior remains unverified unless version-bound evidence is supplied.\n\n<!-- teamlib-operation: ' + operation_id + ' -->\n', encoding='utf-8')
        if deployment['owner_trial']:
            body_file.write_text(body_file.read_text()+'\nDeployment: owner-only trial. Server branch protection is not enforced. Human review and explicit merge authorization are required; no automatic merge.\n',encoding='utf-8')
        scan_text(title, 'request_title')
        for attempt in range(3):
            snapshot = open_snapshot(config, workspace)
            doctor = doctor_platform(config)
            if snapshot['source_commit'] != doctor['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed repeatedly during proposal preparation.')
            base = Path(snapshot['root']); existing = base / 'entries' / identifier
            policy = _trusted_policy(base)
            validate_outbound(locked, commit_message + '\n' + title, body_file, policy=policy)
            _version_conflict(existing, locked)
            if existing.exists() and _material(existing, 'entries/' + identifier + '/') == files:
                return {'state': 'published', 'code': 'OK', 'operation_id': operation_id, 'id': identifier,
                        'versions': sorted(validated['releases']), 'source_commit': snapshot['source_commit'],
                        'repository': config['remote'], 'shared_branch': config['shared_branch'], 'files': files,
                        'message': 'Exact entry material is verified in the current shared branch.',**deployment}
            candidate = temp / ('candidate-' + str(attempt)); candidate.mkdir()
            _copy_snapshot(base, candidate)
            target = candidate / 'entries' / identifier
            if target.exists(): shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(locked, target)
            old_versions = set(validate_entry(existing)['releases']) if existing.exists() else set()
            new_versions = set(validated['releases']) - old_versions
            governance = existing.exists() and not new_versions and (hash_file(existing / 'state.json') != hash_file(locked / 'state.json') or read_json(existing / 'meta.json')['owner_key'] != validated['meta']['owner_key'])
            context = {'actor_key': doctor['actor_key'], 'proposal_author': doctor['actor_key'], 'role': doctor['role'], 'proposal_kind': 'governance' if governance else 'publication'}
            decision = _check_base(snapshot, candidate, context)
            # Re-query current trusted branch and membership before any write.
            fresh = open_snapshot(config, workspace); latest_doctor = doctor_platform(config)
            if fresh['source_commit'] != snapshot['source_commit'] or latest_doctor['source_commit'] != snapshot['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed repeatedly before submission.')
            if (latest_doctor['actor_key'], latest_doctor['role']) != (doctor['actor_key'], doctor['role']):
                raise TeamLibError('SCOPE_DENIED', 'Trusted account role changed while preparing the proposal.')
            branch = 'teamlib/' + operation_id + (('-' + str(attempt)) if attempt else '')
            _git(candidate, 'init', '--initial-branch=' + branch)
            _git(candidate, 'fetch', '--no-tags', config['remote'], 'refs/heads/' + config['shared_branch'])
            if _git(candidate, 'rev-parse', 'FETCH_HEAD') != snapshot['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed while preparing sanitized history.')
            # Start the index at the trusted parent, then stage only the approved candidate tree.
            _git(candidate, 'read-tree', snapshot['source_commit'])
            _git(candidate, 'update-ref', 'HEAD', snapshot['source_commit'])
            # Stage approved bytes directly. Git attributes/clean filters must not execute or alter payload.
            for path in tree_files(target):
                rel = path.relative_to(candidate).as_posix()
                blob = _git(candidate, 'hash-object', '-w', '--no-filters', str(path))
                _git(candidate, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + rel)
            _git(candidate, '-c', 'user.name=Team library contributor', '-c', 'user.email=teamlib@users.noreply.github.com', '-c', 'commit.gpgsign=false', 'commit', '--no-verify', '-m', commit_message)
            head_commit = _git(candidate, 'rev-parse', 'HEAD')
            if _committed_material(candidate, head_commit, identifier) != files:
                raise TeamLibError('INVALID_PACKAGE', 'Actual commit material differs from the verified inventory.')
            if _git(candidate, 'rev-list', '--count', snapshot['source_commit'] + '..' + head_commit) != '1':
                raise TeamLibError('SCOPE_DENIED', 'Proposal must contain exactly one sanitized new commit.')
            actual_paths = _git(candidate, 'diff', '--name-only', snapshot['source_commit'], head_commit).splitlines()
            if not actual_paths or any(not p.startswith('entries/' + identifier + '/') for p in actual_paths):
                raise TeamLibError('SCOPE_DENIED', 'Sanitized commit contains unexpected material.')
            validate_outbound(target, commit_message + '\n' + title, body_file, policy=policy)
            remote_branch = _git(candidate, 'ls-remote', '--heads', config['remote'], 'refs/heads/' + branch)
            if remote_branch:
                old_head = remote_branch.split()[0]
                # Timestamp changes in a retried local commit cannot authorize overwriting an existing branch.
                if not record_path.exists() or read_json(record_path).get('head_commit') != old_head:
                    raise TeamLibError('CONFLICT', 'Proposal branch already contains another commit.')
                _git(candidate, 'fetch', '--no-tags', config['remote'], 'refs/heads/' + branch)
                if _committed_material(candidate, old_head, identifier) != files:
                    raise TeamLibError('CONFLICT', 'Existing proposal branch material does not match this operation.')
                head_commit = old_head
            parent_commit = _git(candidate, 'rev-parse', head_commit + '^')
            prepared = {'state': 'prepared', 'code': 'OK', 'operation_id': operation_id, 'id': identifier,
                        'versions': sorted(validated['releases']), 'new_versions': sorted(new_versions), 'files': files,
                        'source_branch': branch, 'head_commit': head_commit, 'source_commit': parent_commit,
                        'repository': config['remote'], 'shared_branch': config['shared_branch'], 'workspace': str(workspace),
                        'checks': decision['checks'], 'proposal_actor_key': doctor['actor_key'],
                        'author_login': doctor['login'], **deployment,
                        'body_sha256': hashlib.sha256(body_file.read_bytes()).hexdigest(),
                        'title_sha256': hashlib.sha256(title.encode('utf-8')).hexdigest()}
            write_json(record_path, prepared)
            if not remote_branch:
                validate_outbound(target, commit_message + '\n' + title, body_file, policy=policy)
                try:
                    _git(candidate, 'push', config['remote'], head_commit + ':refs/heads/' + branch)
                except TeamLibError:
                    prepared.update({'code': 'REMOTE_FAILED', 'message': 'Proposal is prepared; branch upload is not verified.'})
                    write_json(record_path, prepared); return prepared
            # Check branch is actually present before claiming submission.
            try:
                uploaded = _git(candidate, 'ls-remote', '--heads', config['remote'], 'refs/heads/' + branch)
            except TeamLibError:
                uploaded = ''
            if not uploaded or uploaded.split()[0] != head_commit:
                prepared.update({'code': 'STATUS_UNVERIFIED', 'message': 'Proposal branch content is not verified.'})
                write_json(record_path, prepared); return prepared
            validate_outbound(target, commit_message + '\n' + title, body_file, policy=policy)
            request = create_request(config, branch, title, body_file)
            prepared.update(request)
            if prepared.get('request_id'):
                prepared = verify_request(config, prepared['request_id'], prepared)
            write_json(record_path, prepared)
            return prepared
    raise TeamLibError('CONFLICT', 'Proposal could not acquire a fresh trusted base.')


def verify_request(config, request_id, expected):
    if not isinstance(expected, dict) or expected.get('repository') != config.get('remote') or expected.get('shared_branch') != config.get('shared_branch'):
        raise TeamLibError('STATUS_UNVERIFIED', 'Expected request provenance is missing or mismatched.')
    identifier = expected.get('id'); validate_id(identifier)
    repo = repository_name(config)
    requested_number = _request_number(repo, request_id, 'pull')
    if expected.get('request_id') is None or _request_number(repo, expected['request_id'], 'pull') != requested_number:
        raise TeamLibError('CONFLICT', 'Requested identity does not match the original proposal record.')
    if not isinstance(expected.get('author_login'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', expected['author_login']) or any(not isinstance(expected.get(k), str) or not re.fullmatch(r'[0-9a-f]{64}', expected[k]) for k in ('body_sha256', 'title_sha256')):
        return dict(expected, state='submitted', code='STATUS_UNVERIFIED', message='Original reviewed request bindings are missing; current API text cannot replace that evidence.')
    try:
        request = get_request(config, request_id)
    except TeamLibError as exc:
        if exc.code not in {'REMOTE_FAILED', 'AUTH_REQUIRED', 'STATUS_UNVERIFIED', 'TOOL_MISSING'}: raise
        result = dict(expected)
        result.update({'state': 'submitted' if expected.get('request_id') else 'prepared', 'code': 'STATUS_UNVERIFIED',
                       'message': 'Previously recorded request state is retained; current platform status cannot be verified.'})
        return result
    if request['request_id'] != requested_number:
        raise TeamLibError('CONFLICT', 'Platform response does not match the original request identity.')
    if request['baseRefName'] != config['shared_branch'] or request['headRefName'] != expected.get('source_branch') or request['operation_id'] != expected.get('operation_id'):
        raise TeamLibError('CONFLICT', 'Platform request does not match the expected proposal.')
    if (not isinstance(request.get('author_login'), str) or request['author_login'].casefold() != expected['author_login'].casefold() or any(request.get(k) != expected[k] for k in ('body_sha256', 'title_sha256'))):
        return dict(expected, state='submitted', code='STATUS_UNVERIFIED',
                    observed_request={k: request.get(k) for k in ('request_id', 'author_login', 'body_sha256', 'title_sha256')},
                    message='Request author or reviewed title/body changed; original approval evidence cannot be reused.')
    result = dict(expected, **request)
    if request['headRefOid'] != expected.get('head_commit'):
        result.update({'state': 'submitted', 'code': 'STATUS_UNVERIFIED', 'message': 'Request head changed; the approved material must be checked again.'})
        return result
    if not request.get('mergedAt') or request.get('platform_state') != 'MERGED' or not request.get('merge_commit'):
        result.update({'state': 'submitted', 'code': 'OK', 'message': 'Request exists; publication has not been verified.'})
        return result
    try:
        workspace = ensure_no_symlinks(Path(expected['workspace']))
        # Explicit merged commit must be reachable from shared; a fresh current snapshot supplies material truth.
        merged_snapshot = open_snapshot(config, workspace, commit=request['merge_commit'])
        merged_target = Path(merged_snapshot['root']) / 'entries' / identifier
        validate_entry(merged_target)
        if _material(merged_target, 'entries/' + identifier + '/') != expected.get('files'):
            raise TeamLibError('STATUS_UNVERIFIED', 'Merged commit does not contain the submitted material.')
        snapshot = open_snapshot(config, workspace)
        target = Path(snapshot['root']) / 'entries' / identifier
        validate_entry(target)
        if _material(target, 'entries/' + identifier + '/') != expected.get('files'):
            raise TeamLibError('STATUS_UNVERIFIED', 'Shared material differs from the submitted entry.')
    except (TeamLibError, OSError, KeyError):
        result.update({'state': 'submitted', 'code': 'STATUS_UNVERIFIED', 'message': 'Merge is reported, but exact shared material is not verified.'})
        return result
    result.update({'state': 'published', 'code': 'OK', 'published_commit': snapshot['source_commit'],
                   'message': 'Exact submitted material is verified in the current shared branch.'})
    return result
