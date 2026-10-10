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
from .platform import doctor_platform, create_request, get_request, repository_name, _request_number, _find_pr, _operation, merge_checked_request
from .config import automatic_publication
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



def _chinese_upload_description(validated, operation_id, deployment):
    """Describe verified material in Chinese; never invent business results."""
    meta=validated['meta'];identifier=meta['id']
    kinds={'case':'案例','prompt':'提示词','workflow':'工作流','skill':'技能','tool':'工具','lesson':'经验','research':'研究资料'}
    title=('上传'+kinds[meta['kind']]+'：'+' '.join(meta['title'].split()))[:120]
    def values(items):return '、'.join('不限' if value=='any' else value for value in items) or '未声明'
    lines=['## 分享的内容',meta['summary'],'',
           '## 本次提交',f'- 能力名称：{meta["title"]}',f'- 类型：{kinds[meta["kind"]]}',
           f'- 条目：{identifier}',f'- 本次提供版本：{values(sorted(validated["releases"]))}',
           '- 本次新增、更新或状态变化以实际文件差异为准；本版变化和具体步骤见随包的中文 README。','']
    effects={'read_only':'只读，不修改业务资料','local_generate':'生成本地文件','project_write':'修改项目文件','remote_write':'写入远端'}
    for version,manifest in sorted(validated['releases'].items()):
        scope=manifest['scope'];compat=manifest['compatibility']
        lines += [f'## 版本 {version}：适用范围',f'- 输入：{values(scope["inputs"])}',
                  f'- 输出：{values(scope["outputs"])}',f'- 适用场景：{values(scope["includes"])}',
                  f'- 不适用场景：{values(scope["excludes"])}',
                  f'- 系统：{values(compat["os"])}；所需工具：{values(compat["tools"])}',
                  '- 运行时要求：'+('、'.join(k+' '+v for k,v in compat['runtimes'].items()) or '无额外声明'),
                  f'- 所需操作能力：{values(compat["capabilities"])}',
                  '- 副作用：'+values([effects.get(v,v) for v in manifest['effects']]),'',
                  '### 怎么复用','1. 先阅读本版 README，确认任务范围和环境符合上述条件。',
                  '2. 由 AI 下载固定版本并完成使用前检查，再按以下入口读取方法：']
        lines += [f'   - releases/{version}/{entrypoint}' for entrypoint in manifest['entrypoints']]
        lines += ['3. 只在用户已授权的任务范围内使用；具体步骤、示例和本版变化见 README。','',
                  '### 依赖',*([f'- {d["id"]}@{d["version"]}；固定摘要：{d["manifest_sha256"]}' for d in manifest['dependencies']] or ['- 无团队能力依赖。']),
                  '','### 包含哪些文件',*[f'- {row["path"]}（{row["size"]} 字节）' for row in manifest['files']],
                  f'- 版本说明：entries/{identifier}/releases/{version}/README.md','']
    lines += ['## 验证与审核','本次只校验材料、权限、依赖和分享范围，不代表已经执行能力或验证业务效果。',
              '业务验证需逐版本核对 state 中绑定的证据；没有证据的范围必须标注“未验证”，不能编造效果或节省时间。',
              ('检查通过后，AI 会以当前登录 GitHub 账号直接快速前进推送到共享分支并核对实际材料；检查未完成或内容发生变化时会暂停。' if deployment.get('direct_write') else '自动检查通过后，AI 会合入共享分支并核对实际材料；检查未完成或内容发生变化时会暂停，不会把未核对内容写入共享分支。'),' ',
              '## 来源与追溯',meta['source']['reference'],f'- 原作者：{meta["author_key"]}；当前负责人：{meta["owner_key"]}']
    if meta['source'].get('derived_from'):
        d=meta['source']['derived_from'];lines.append(f'- 改编自：{d["repository"]}，{d["id"]}@{d["version"]}，来源提交 {d["source_commit"]}，摘要 {d["manifest_sha256"]}')
    if deployment['owner_trial']:
        lines += ['','## 当前发布方式','仅所有者试用：共享分支未启用 GitHub 强制审核；本库由 AI 完成可信基线检查、敏感内容检查和 CI 检查，全部通过后自动合入。']
    if deployment.get('direct_write'):
        lines += ['','## 当前发布方式','公开仓库可直接读取；只有登录 GitHub 且具备 Write 权限的团队成员才能向 main 直推。匿名用户没有写入权限，也不要求 Pull Request 或审核。']
    lines += ['',f'<!-- teamlib-operation: {operation_id} -->','']
    body='\n'.join(lines)
    return title,title+'\n\n'+body,body


def propose_entry(config, entry, workspace):
    entry = ensure_no_symlinks(entry); workspace = ensure_no_symlinks(workspace)
    validated = validate_entry(entry); identifier = validated['meta']['id']; validate_id(identifier)
    if config.get('publish_mode') == 'direct':
        return _direct_publish_entry(config, entry, workspace)
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
                result = complete_publication(config, previous)
                write_json(record_path, result)
                return result
            if previous.get('source_branch'):
                branch=previous['source_branch']
                if not re.fullmatch('teamlib/'+operation_id+r'(?:-[0-2])?',branch):
                    raise TeamLibError('CONFLICT','Original proposal branch does not match this operation.')
                try:
                    observed=_find_pr(repository_name(config),branch,operation_id,config['shared_branch'],doctor['login'])
                except TeamLibError as exc:
                    if exc.code not in {'REMOTE_FAILED','AUTH_REQUIRED','STATUS_UNVERIFIED','TOOL_MISSING'}:raise
                    return dict(previous,state='prepared',code='STATUS_UNVERIFIED',message='原投稿查询暂不可用，保留原始描述与回执；未再次上传。')
                if observed:
                    if not isinstance(previous.get('author_login'),str) or any(not isinstance(previous.get(key),str) or not re.fullmatch(r'[0-9a-f]{64}',previous[key]) for key in ('body_sha256','title_sha256')):
                        raise TeamLibError('STATUS_UNVERIFIED','Original request bindings are incomplete; the receipt is preserved.')
                    if any(observed.get(key)!=previous.get(key) for key in ('body_sha256','title_sha256')) or observed.get('headRefOid')!=previous.get('head_commit') or observed.get('author_login','').casefold()!=previous.get('author_login','').casefold():
                        raise TeamLibError('CONFLICT','Original request content changed; its stored review bindings are preserved.')
                    recovered=dict(previous,request_id=observed['request_id'],url=observed['url'])
                    result=complete_publication(config,recovered)
                    write_json(record_path,result)
                    return result

        deployment={'deployment_mode':doctor.get('deployment_mode','protected'),
                    'owner_trial':doctor.get('owner_trial',False),
                    'hard_gate_enforced':doctor.get('hard_gate_enforced',False),
                    'manual_review_required':doctor.get('manual_review_required',True),
                    'auto_merge':doctor.get('auto_merge',False)}
        title,commit_message,body=_chinese_upload_description(validated,operation_id,deployment)
        body_file = temp / 'body.md'
        body_file.write_text(body,encoding='utf-8')
        _operation(body)  # Validate the final marker before creating or uploading a Git commit.
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
                prepared = complete_publication(config, prepared)
            write_json(record_path, prepared)
            return prepared
    raise TeamLibError('CONFLICT', 'Proposal could not acquire a fresh trusted base.')


def _direct_publish_entry(config, entry, workspace):
    """Publish one checked entry with an authenticated fast-forward push to main.

    Public repositories are readable by anyone, but only a GitHub collaborator
    with Write permission can reach this path. The branch is never force-pushed;
    a race with main causes a retry or a conflict receipt.
    """
    entry = ensure_no_symlinks(entry); workspace = ensure_no_symlinks(workspace)
    validated = validate_entry(entry); identifier = validated['meta']['id']; validate_id(identifier)
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='direct-publication-', dir=workspace) as temporary:
        temp = Path(temporary); locked = temp / 'entry'; shutil.copytree(entry, locked)
        validated = validate_entry(locked); files = _material(locked, 'entries/' + identifier + '/')
        material_digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        doctor = doctor_platform(config)
        operation_id = hashlib.sha256(json.dumps([config['remote'], config['shared_branch'], doctor['actor_key'], identifier, material_digest]).encode()).hexdigest()[:32]
        record_path = workspace / 'proposals' / (operation_id + '.json')
        if record_path.exists():
            previous = read_json(record_path)
            if previous.get('files') != files or previous.get('repository') != config['remote']:
                raise TeamLibError('CONFLICT', 'Stored direct publication does not match the submitted material.')
            if previous.get('state') == 'published':
                return previous

        deployment = {'deployment_mode': 'public_write', 'owner_trial': False,
                      'hard_gate_enforced': False, 'manual_review_required': False,
                      'auto_merge': False, 'direct_write': True}
        title, commit_message, body = _chinese_upload_description(validated, operation_id, deployment)
        body_file = temp / 'body.md'; body_file.write_text(body, encoding='utf-8')
        _operation(body); scan_text(title, 'direct_commit_title')
        for attempt in range(3):
            snapshot = open_snapshot(config, workspace)
            doctor = doctor_platform(config)
            if snapshot['source_commit'] != doctor['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed repeatedly during direct publication.')
            base = Path(snapshot['root']); existing = base / 'entries' / identifier
            policy = _trusted_policy(base)
            validate_outbound(locked, commit_message + '\n' + title, body_file, policy=policy)
            _version_conflict(existing, locked)
            if existing.exists() and _material(existing, 'entries/' + identifier + '/') == files:
                result = {'state': 'published', 'code': 'OK', 'operation_id': operation_id,
                          'id': identifier, 'versions': sorted(validated['releases']),
                          'source_commit': snapshot['source_commit'], 'published_commit': snapshot['source_commit'],
                          'repository': config['remote'], 'shared_branch': config['shared_branch'],
                          'files': files, 'message': 'Exact entry material is already verified in the public shared branch.', **deployment}
                write_json(record_path, result); return result
            candidate = temp / ('candidate-' + str(attempt)); candidate.mkdir()
            _copy_snapshot(base, candidate)
            target = candidate / 'entries' / identifier
            if target.exists(): shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(locked, target)
            old_versions = set(validate_entry(existing)['releases']) if existing.exists() else set()
            new_versions = set(validated['releases']) - old_versions
            governance = existing.exists() and not new_versions and (hash_file(existing / 'state.json') != hash_file(locked / 'state.json') or read_json(existing / 'meta.json')['owner_key'] != validated['meta']['owner_key'])
            context = {'actor_key': doctor['actor_key'], 'proposal_author': doctor['actor_key'],
                       'role': doctor['role'], 'public_write': True,
                       'proposal_kind': 'governance' if governance else 'publication'}
            decision = _check_base(snapshot, candidate, context)
            fresh = open_snapshot(config, workspace); latest_doctor = doctor_platform(config)
            if fresh['source_commit'] != snapshot['source_commit'] or latest_doctor['source_commit'] != snapshot['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed repeatedly before the direct push.')
            if latest_doctor['login'].casefold() != doctor['login'].casefold() or latest_doctor['permissions'].get('push') is not True:
                raise TeamLibError('SCOPE_DENIED', 'GitHub Write identity changed while preparing the direct push.')
            branch = 'teamlib/' + operation_id + (('-' + str(attempt)) if attempt else '')
            _git(candidate, 'init', '--initial-branch=' + branch)
            _git(candidate, 'fetch', '--no-tags', config['remote'], 'refs/heads/' + config['shared_branch'])
            if _git(candidate, 'rev-parse', 'FETCH_HEAD') != snapshot['source_commit']:
                if attempt < 2: continue
                raise TeamLibError('CONFLICT', 'Shared branch changed while preparing the direct history.')
            _git(candidate, 'read-tree', snapshot['source_commit']); _git(candidate, 'update-ref', 'HEAD', snapshot['source_commit'])
            for path in tree_files(target):
                rel = path.relative_to(candidate).as_posix(); blob = _git(candidate, 'hash-object', '-w', '--no-filters', str(path))
                _git(candidate, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + rel)
            _git(candidate, '-c', 'user.name=Team library contributor', '-c', 'user.email=teamlib@users.noreply.github.com', '-c', 'commit.gpgsign=false', 'commit', '--no-verify', '-m', commit_message)
            head_commit = _git(candidate, 'rev-parse', 'HEAD')
            if _committed_material(candidate, head_commit, identifier) != files:
                raise TeamLibError('INVALID_PACKAGE', 'Actual direct commit material differs from the verified inventory.')
            if _git(candidate, 'rev-list', '--count', snapshot['source_commit'] + '..' + head_commit) != '1':
                raise TeamLibError('SCOPE_DENIED', 'Direct publication must contain exactly one new commit.')
            actual_paths = _git(candidate, 'diff', '--name-only', snapshot['source_commit'], head_commit).splitlines()
            if not actual_paths or any(not p.startswith('entries/' + identifier + '/') for p in actual_paths):
                raise TeamLibError('SCOPE_DENIED', 'Direct commit contains unexpected material.')
            validate_outbound(target, commit_message + '\n' + title, body_file, policy=policy)
            prepared = {'state': 'prepared', 'code': 'OK', 'operation_id': operation_id, 'id': identifier,
                        'versions': sorted(validated['releases']), 'new_versions': sorted(new_versions), 'files': files,
                        'head_commit': head_commit, 'source_commit': snapshot['source_commit'],
                        'repository': config['remote'], 'shared_branch': config['shared_branch'], 'workspace': str(workspace),
                        'checks': decision['checks'], 'proposal_actor_key': doctor['actor_key'],
                        'author_login': doctor['login'], **deployment}
            write_json(record_path, prepared)
            try:
                _git(candidate, 'push', config['remote'], head_commit + ':refs/heads/' + config['shared_branch'])
            except TeamLibError as exc:
                prepared.update({'code': exc.code, 'message': 'Direct commit was prepared; main was not confirmed updated.'})
                write_json(record_path, prepared); return prepared
            remote_head = _git(candidate, 'ls-remote', '--heads', config['remote'], 'refs/heads/' + config['shared_branch'])
            if not remote_head or remote_head.split()[0] != head_commit:
                prepared.update({'code': 'STATUS_UNVERIFIED', 'message': 'Direct push completed without a verifiable main ref.'})
                write_json(record_path, prepared); return prepared
            try:
                verified = open_snapshot(config, workspace)
                verified_target = Path(verified['root']) / 'entries' / identifier
                validate_entry(verified_target)
                if _material(verified_target, 'entries/' + identifier + '/') != files:
                    raise TeamLibError('STATUS_UNVERIFIED', 'Shared material differs from the direct commit.')
            except (TeamLibError, OSError, KeyError):
                prepared.update({'code': 'STATUS_UNVERIFIED', 'message': 'Direct push is recorded, but exact shared material is not verified.'})
                write_json(record_path, prepared); return prepared
            result = dict(prepared, state='published', code='OK', published_commit=verified['source_commit'],
                          message='Exact submitted material is verified in the public shared branch.')
            write_json(record_path, result); return result
    raise TeamLibError('CONFLICT', 'Direct publication could not acquire a fresh trusted base.')


def complete_publication(config, expected):
    """Finish an authorized upload without a human review step; preserve its receipt."""
    result = verify_request(config, expected.get('request_id'), expected)
    if result.get('state') == 'published' or result.get('code') != 'OK' or not automatic_publication(config):
        return result
    try:
        merge_checked_request(config, expected)
    except TeamLibError as exc:
        return dict(result, code=exc.code, message=exc.message)
    # A reported merge is insufficient: verify the original bytes in the
    # reachable merged commit and in fresh shared material.
    return verify_request(config, expected['request_id'], expected)


def verify_direct_publication(config, expected, workspace):
    """Recheck an existing direct-write receipt against the current main tree."""
    if config.get('publish_mode') != 'direct' or not isinstance(expected, dict) or expected.get('direct_write') is not True:
        raise TeamLibError('STATUS_UNVERIFIED', 'A direct publication receipt is required.')
    if expected.get('repository') != config.get('remote') or expected.get('shared_branch') != config.get('shared_branch'):
        raise TeamLibError('STATUS_UNVERIFIED', 'Direct publication provenance differs from the configured repository.')
    identifier = expected.get('id'); validate_id(identifier)
    files = expected.get('files')
    if not isinstance(files, dict) or not files or any(not isinstance(path, str) or not path.startswith('entries/' + identifier + '/') or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) for path, digest in files.items()):
        raise TeamLibError('STATUS_UNVERIFIED', 'Direct publication file inventory is incomplete.')
    snapshot = open_snapshot(config, workspace)
    target = Path(snapshot['root']) / 'entries' / identifier
    validate_entry(target)
    if _material(target, 'entries/' + identifier + '/') != files:
        return dict(expected, state='prepared', code='STATUS_UNVERIFIED',
                    message='Current shared material differs from the direct publication receipt.')
    return dict(expected, state='published', code='OK', published_commit=snapshot['source_commit'],
                message='Exact direct publication material is verified in the current shared branch.')


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
