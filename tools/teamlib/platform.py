"""GitHub reference adapter. Credentials remain in Git/gh's existing login store."""
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from .contracts import TeamLibError, read_json, validate_id, validate_version

run_command = subprocess.run
_OPERATION = re.compile(r'<!-- teamlib-operation: ([0-9a-f]{32}) -->')
_PR_FIELDS = 'number,url,state,title,body,author,baseRefName,headRefName,headRefOid,mergeCommit,mergedAt'
_ISSUE_FIELDS = 'number,url,state,title,body,author'


def _run(argv, *, cwd=None):
    try:
        result = run_command(argv, cwd=cwd, shell=False, check=False, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except FileNotFoundError:
        raise TeamLibError('TOOL_MISSING', 'Required Git or platform CLI is unavailable.') from None
    except (subprocess.SubprocessError, OSError):
        raise TeamLibError('REMOTE_FAILED', 'Platform request failed or its outcome is unknown.') from None
    if result.returncode:
        raise TeamLibError('REMOTE_FAILED', 'Platform request was rejected.')
    return result.stdout


def _json(argv):
    try:
        return json.loads(_run(argv))
    except (ValueError, TypeError):
        raise TeamLibError('STATUS_UNVERIFIED', 'Platform returned unverifiable data.') from None


def repository_name(config):
    if config.get('platform') != 'github':
        raise TeamLibError('CONFIG_MISSING', 'Connected publishing requires the configured real GitHub repository; local mode has no native review or protection.')
    remote = config.get('remote', '')
    patterns = [r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?',
                r'git@github\.com:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?',
                r'ssh://git@github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?']
    matches = [re.fullmatch(p, remote) for p in patterns if isinstance(remote, str)]
    match = next((m for m in matches if m), None)
    branch = config.get('shared_branch')
    if not match or not isinstance(branch, str) or not branch or branch.startswith('-') or any(x in branch for x in ('..', '~', '^', ':', '?', '*', '[', '\\', '@{')) or any(c.isspace() or ord(c) < 32 for c in branch):
        raise TeamLibError('CONFIG_MISSING', 'An explicit credential-free GitHub remote and safe shared branch are required.')
    if config.get('publish_mode', 'request') != 'request' or config.get('auto_merge', False):
        raise TeamLibError('SCOPE_DENIED', 'Only reviewed requests without automatic merge are supported.')
    return match.group(1)


def _api(repo, suffix):
    return _json(['gh', 'api', 'repos/' + repo + suffix])


def _contents(repo, path, ref):
    row = _api(repo, '/contents/' + path + '?ref=' + quote(ref, safe=''))
    try:
        if row['encoding'] != 'base64': raise ValueError()
        return base64.b64decode(row['content'], validate=False).decode('utf-8')
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise TeamLibError('STATUS_UNVERIFIED', 'Trusted repository content is unavailable.') from None


def _trusted_member(repo, sha, login):
    try:
        members = json.loads(_contents(repo, 'governance/members.json', sha))
        if not isinstance(members, dict) or set(members) != {'schema_version', 'members'} or members['schema_version'] != 1 or not isinstance(members['members'], list):
            raise ValueError()
        actors = set(); logins = set(); matched = None
        for row in members['members']:
            if not isinstance(row, dict) or set(row) != {'actor_key', 'github_login', 'role'} or row['role'] not in {'contributor', 'maintainer'} or not isinstance(row['actor_key'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', row['actor_key']) or not isinstance(row['github_login'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', row['github_login']):
                raise ValueError()
            if row['actor_key'] in actors or row['github_login'].casefold() in logins: raise ValueError()
            actors.add(row['actor_key']); logins.add(row['github_login'].casefold())
            if row['github_login'].casefold() == login.casefold(): matched = row
    except (TypeError, ValueError, KeyError):
        raise TeamLibError('STATUS_UNVERIFIED', 'Trusted account mapping is invalid.') from None
    if matched is None:
        raise TeamLibError('SCOPE_DENIED', 'The authenticated account has no unique trusted membership mapping.')
    return matched


def doctor_read(config):
    """Verify private-repository reading without requiring PR/push/protection privileges."""
    repo = repository_name(config)
    try:
        actor = _json(['gh', 'api', 'user'])
    except TeamLibError as exc:
        if exc.code == 'TOOL_MISSING': raise
        raise TeamLibError('AUTH_REQUIRED', 'An authenticated individual GitHub account is required.') from None
    if not isinstance(actor, dict) or actor.get('type') != 'User' or not isinstance(actor.get('login'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', actor['login']):
        raise TeamLibError('AUTH_REQUIRED', 'Repository operations require an individual account.')
    repository = _api(repo, '')
    if not isinstance(repository, dict) or repository.get('private') is not True or repository.get('full_name', '').lower() != repo.lower():
        raise TeamLibError('SCOPE_DENIED', 'The configured repository is not verified private.')
    permissions = {k: repository.get('permissions', {}).get(k) is True for k in ('pull', 'push', 'admin')}
    if not permissions['pull']:
        raise TeamLibError('SCOPE_DENIED', 'The authenticated account has no verified repository read permission.')
    branch = _api(repo, '/branches/' + quote(config['shared_branch'], safe=''))
    sha = branch.get('commit', {}).get('sha', '') if isinstance(branch, dict) else ''
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise TeamLibError('STATUS_UNVERIFIED', 'The configured shared branch cannot be verified.')
    member = _trusted_member(repo, sha, actor['login'])
    return {'platform': 'github', 'repository': repo, 'private': True, 'read_verified': True,
            'shared_branch': config['shared_branch'], 'source_commit': sha,
            'login': actor['login'], 'actor_key': member['actor_key'], 'role': member['role'],
            'permissions': permissions, 'protected': branch.get('protected') is True}


def doctor_platform(config):
    identity = doctor_read(config); repo = identity['repository']; sha = identity['source_commit']
    if identity['protected'] is not True:
        raise TeamLibError('SCOPE_DENIED', 'The configured shared branch is not verified protected.')
    try:
        protection = _api(repo, '/branches/' + quote(config['shared_branch'], safe='') + '/protection')
    except TeamLibError:
        raise TeamLibError('SCOPE_DENIED', 'Shared branch protection details cannot be verified.') from None
    reviews = protection.get('required_pull_request_reviews') or {}
    if reviews.get('required_approving_review_count', 0) < 1 or reviews.get('dismiss_stale_reviews') is not True or protection.get('allow_force_pushes', {}).get('enabled') is not False or protection.get('allow_deletions', {}).get('enabled') is not False:
        raise TeamLibError('SCOPE_DENIED', 'Shared branch must require fresh approval and forbid force push and deletion.')
    workflow = _contents(repo, '.github/workflows/check-submission.yml', sha)
    _contents(repo, 'tools/check_submission.py', sha)
    # Presence is evidence of base ownership, not evidence GitHub enforces a trusted check source.
    check_rows = (protection.get('required_status_checks') or {}).get('checks', [])
    check_sources = [{'context': r.get('context'), 'app_id': r.get('app_id')} for r in check_rows if r.get('context') == 'team-library-policy']
    return dict(identity, approval_required=True, base_owned_checker=True,
                workflow_uses_base_event='pull_request_target' in workflow, required_check_sources=check_sources,
                hard_gate_enforced=False, manual_review_required=True)


def _request_number(repo, request_id, kind):
    value = str(request_id)
    if re.fullmatch(r'[1-9][0-9]*', value): return value
    match = re.fullmatch(r'https://github\.com/' + re.escape(repo) + '/' + kind + r'/([1-9][0-9]*)', value)
    if match: return match.group(1)
    raise TeamLibError('INVALID_PACKAGE', 'Request ID must belong to the configured repository.')


def _operation(body):
    matches = _OPERATION.findall(body)
    if len(matches) != 1:
        raise TeamLibError('INVALID_PACKAGE', 'A unique operation marker is required.')
    return matches[0]


def _scan(title, body_file):
    from .package import scan_file, scan_text
    scan_text(title, location='request title')
    scan_file(body_file, location='request body')
    try: body = Path(body_file).read_text(encoding='utf-8')
    except (OSError, UnicodeError): raise TeamLibError('INVALID_PACKAGE', 'Request body is unavailable.') from None
    return body, _operation(body)


def _safe_request(repo, row, governance=False):
    kind = 'issues' if governance else 'pull'
    number = _request_number(repo, row.get('number', ''), kind)
    url = 'https://github.com/' + repo + '/' + kind + '/' + number
    body = row.get('body') or ''
    title = row.get('title') or ''
    if not isinstance(body, str) or not isinstance(title, str):
        raise TeamLibError('STATUS_UNVERIFIED', 'Request review text cannot be verified.')
    markers = _OPERATION.findall(body)
    result = {'request_id': number, 'url': url, 'state': 'submitted', 'platform_state': row.get('state'),
              'operation_id': markers[0] if len(markers) == 1 else None,
              'author_login': row.get('author', {}).get('login'),
              'body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
              'title_sha256': hashlib.sha256(title.encode('utf-8')).hexdigest()}
    if not governance:
        result.update({k: row.get(k) for k in ('baseRefName', 'headRefName', 'headRefOid', 'mergedAt')})
        result['merge_commit'] = (row.get('mergeCommit') or {}).get('oid')
    return result


def get_request(config, request_id):
    repo = repository_name(config); doctor_read(config)
    number = _request_number(repo, request_id, 'pull')
    row = _json(['gh', 'pr', 'view', number, '--repo', repo, '--json', _PR_FIELDS])
    result = _safe_request(repo, row)
    if result['request_id'] != number:
        raise TeamLibError('CONFLICT', 'Platform returned a different request identity.')
    return result


def _find_pr(repo, branch, operation_id, shared_branch, login, expected_body=None, expected_title=None):
    rows = _json(['gh', 'pr', 'list', '--repo', repo, '--state', 'all', '--head', branch, '--limit', '100', '--json', _PR_FIELDS])
    if len(rows) > 1:
        raise TeamLibError('CONFLICT', 'Multiple requests use the proposal branch.')
    if not rows: return None
    row = rows[0]
    if row.get('baseRefName') != shared_branch or row.get('author', {}).get('login', '').lower() != login.lower() or _operation(row.get('body') or '') != operation_id:
        raise TeamLibError('CONFLICT', 'Existing proposal does not match this operation.')
    if expected_title is not None and row.get('title') != expected_title:
        raise TeamLibError('CONFLICT', 'Proposal operation already contains a different title.')
    if expected_body is not None and row.get('body') != expected_body:
        raise TeamLibError('CONFLICT', 'Proposal operation already contains different review material.')
    return _safe_request(repo, row)


def create_request(config, source_branch, title, body_file):
    body, _ = _scan(title, body_file)
    with tempfile.TemporaryDirectory(prefix='teamlib-pr-') as temporary:
        locked = Path(temporary) / 'body.md'; locked.write_text(body, encoding='utf-8')
        return _create_request_locked(config, source_branch, title, locked)


def _create_request_locked(config, source_branch, title, body_file):
    repo = repository_name(config)
    if not re.fullmatch(r'teamlib/[0-9a-f]{32}(?:-[0-2])?', source_branch) or source_branch == config['shared_branch']:
        raise TeamLibError('SCOPE_DENIED', 'Only a dedicated proposal branch may be submitted.')
    body, operation_id = _scan(title, body_file)
    doctor = doctor_platform(config)
    if not doctor['permissions']['push']:
        raise TeamLibError('SCOPE_DENIED', 'The authenticated account cannot submit a branch.')
    existing = _find_pr(repo, source_branch, operation_id, config['shared_branch'], doctor['login'], body, title)
    if existing: return existing
    try:
        _scan(title, body_file)
        _run(['gh', 'pr', 'create', '--repo', repo, '--base', config['shared_branch'], '--head', source_branch, '--title', title, '--body-file', str(body_file)])
    except TeamLibError:
        pass
    try:
        existing = _find_pr(repo, source_branch, operation_id, config['shared_branch'], doctor['login'], body, title)
        if existing: return existing
    except TeamLibError as exc:
        if exc.code == 'CONFLICT': raise
    return {'state': 'prepared', 'code': 'REMOTE_FAILED', 'operation_id': operation_id,
            'source_branch': source_branch, 'message': 'Proposal branch prepared; request creation is not verified. Retry queries the same operation first.'}


def _find_issue(repo, operation_id, login, expected_body=None):
    rows = _json(['gh', 'issue', 'list', '--repo', repo, '--state', 'all', '--search', operation_id + ' in:body', '--limit', '100', '--json', _ISSUE_FIELDS])
    rows = [r for r in rows if _OPERATION.findall(r.get('body') or '') == [operation_id]]
    if len(rows) > 1: raise TeamLibError('CONFLICT', 'Multiple governance issues match this operation.')
    if rows and rows[0].get('author', {}).get('login', '').lower() != login.lower():
        raise TeamLibError('CONFLICT', 'Governance operation belongs to another account.')
    if rows and expected_body is not None and rows[0].get('body') != expected_body:
        raise TeamLibError('CONFLICT', 'Governance operation already contains different material.')
    return _safe_request(repo, rows[0], True) if rows else None


def create_governance_request(config, kind, payload_file):
    from .package import scan_file, scan_text
    repo = repository_name(config)
    if kind not in {'withdrawal', 'restore', 'recommendation', 'verification', 'transfer'}:
        raise TeamLibError('INVALID_PACKAGE', 'Governance request kind is unsupported.')
    scan_file(payload_file, location='governance payload')
    payload = read_json(payload_file)
    if set(payload) != {'operation_id', 'id', 'version', 'reason'} or not isinstance(payload.get('reason'), str) or not payload['reason'].strip():
        raise TeamLibError('INVALID_PACKAGE', 'Governance payload must contain only ID, version, reason and operation ID.')
    validate_id(payload.get('id')); validate_version(payload.get('version'))
    operation_id = payload.get('operation_id')
    if not isinstance(operation_id, str) or not re.fullmatch(r'[0-9a-f]{32}', operation_id):
        raise TeamLibError('INVALID_PACKAGE', 'Governance request requires a stable operation ID.')
    doctor = doctor_platform(config)
    title = 'Team library ' + kind + ': ' + payload['id'] + ' ' + payload['version']
    body = json.dumps({'kind': kind, 'payload': payload}, ensure_ascii=False, indent=2) + '\n<!-- teamlib-operation: ' + operation_id + ' -->\n'
    scan_text(title, location='issue title'); scan_text(body, location='issue body')
    existing = _find_issue(repo, operation_id, doctor['login'], body)
    if existing: return existing
    with tempfile.TemporaryDirectory(prefix='teamlib-issue-') as temp:
        body_file = Path(temp) / 'body.md'; body_file.write_text(body, encoding='utf-8')
        try:
            _scan(title, body_file)
            _run(['gh', 'issue', 'create', '--repo', repo, '--title', title, '--body-file', str(body_file)])
        except TeamLibError:
            pass
    try:
        existing = _find_issue(repo, operation_id, doctor['login'], body)
        if existing: return existing
    except TeamLibError as exc:
        if exc.code == 'CONFLICT': raise
    return {'state': 'prepared', 'code': 'REMOTE_FAILED', 'operation_id': operation_id,
            'message': 'Governance issue creation is not verified; no state change has been applied.'}


def get_governance_request(config, request_id):
    from .package import scan_text
    repo = repository_name(config); doctor_read(config)
    number = _request_number(repo, request_id, 'issues')
    row = _json(['gh', 'issue', 'view', number, '--repo', repo, '--json', _ISSUE_FIELDS])
    body = row.get('body') or ''; scan_text(body, location='governance issue')
    result = _safe_request(repo, row, True)
    try:
        parsed = json.loads(_OPERATION.sub('', body).strip())
        validate_id(parsed['payload']['id']); validate_version(parsed['payload']['version'])
        result.update({'kind': parsed['kind'], 'payload': parsed['payload']})
    except (ValueError, KeyError, TypeError):
        raise TeamLibError('STATUS_UNVERIFIED', 'Governance issue material cannot be verified.') from None
    return result
