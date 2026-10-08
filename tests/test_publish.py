import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.core_helpers import dump, entry, governance, release
from tests.platform_helpers import GithubService, config
from tools.teamlib.contracts import TeamLibError


class PublishTests(unittest.TestCase):
    def setUp(self):
        from tools.teamlib import publish, platform
        self.publish = publish; self.platform = platform
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.base = self.root / 'base'; self.base.mkdir()
        governance(self.base); self.service = GithubService()
        dump(self.base / 'governance/members.json', self.service.members)
        repository_root = Path(__file__).resolve().parents[1]
        shutil.copytree(repository_root / 'tools', self.base / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(repository_root / 'schemas', self.base / 'schemas')
        checker = self.base / 'tools/check_submission.py'
        if not checker.exists():
            checker.write_text('import argparse,json,sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\nfrom tools.teamlib.policy import check_change\np=argparse.ArgumentParser()\np.add_argument("--base");p.add_argument("--candidate");p.add_argument("--context")\na=p.parse_args()\nr=check_change(Path(a.base),Path(a.candidate),json.loads(Path(a.context).read_text()))\nprint(json.dumps(r));sys.exit(0 if r["allowed"] else 2)\n')
        self.git('init', '--initial-branch=main', str(self.base))
        self.git('-C', str(self.base), 'add', '.')
        self.git('-C', str(self.base), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'trusted shared base')
        self.remote = self.root / 'remote.git'; self.git('clone', '--bare', str(self.base), str(self.remote))
        self.commit = self.git('-C', str(self.base), 'rev-parse', 'HEAD').strip(); self.service.head = self.commit
        self.cfg = config(); self.workspace = self.root / 'workspace'
        self.source = entry(self.root / 'source')
        self.snapshot = {'root': str(self.base), 'source_commit': self.commit, 'repository': self.cfg['remote'], 'shared_branch': 'main', 'workspace': str(self.workspace), 'config': self.cfg}
        self.patches = [patch.object(platform, 'run_command', self.service), patch.object(publish, 'open_snapshot', lambda *a, **kw: dict(self.snapshot)), patch.object(publish, 'run_command', self.runner)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def git(self, *args):
        return subprocess.run(['git', *args], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def runner(self, args, **kwargs):
        args = list(args)
        if args[0] == 'git': args = [str(self.remote) if x == self.cfg['remote'] else x for x in args]
        result = subprocess.run(args, **kwargs)
        if 'push' in args and result.returncode == 0:
            self.service.proposal_head = args[-1].split(':')[0]
        return result

    def test_proposal_sanitized_single_commit_and_repeat(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(result['state'], 'submitted')
        self.assertEqual(result['id'], 'alice/demo')
        tip = self.git('--git-dir=' + str(self.remote), 'rev-parse', result['source_branch']).strip()
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-list', '--count', self.commit + '..' + tip).strip(), '1')
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'main').strip(), self.commit)
        second = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(second['operation_id'], result['operation_id']); self.assertEqual(len(self.service.requests), 1)

    def test_published_version_is_immutable_and_self_reported_role_denied(self):
        existing = entry(self.base / 'entries/alice/demo')
        self.git('-C', str(self.base), 'add', '.'); self.git('-C', str(self.base), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'publish')
        self.commit = self.git('-C', str(self.base), 'rev-parse', 'HEAD').strip(); self.snapshot['source_commit'] = self.commit; self.service.head = self.commit
        (self.source / 'releases/1.0.0/README.md').write_text('changed same version')
        with self.assertRaises(TeamLibError): self.publish.propose_entry(self.cfg, self.source, self.workspace)
        shutil.rmtree(self.source); shutil.copytree(existing, self.source)
        state = json.loads((self.source / 'state.json').read_text()); state['recommended_version'] = None; dump(self.source / 'state.json', state)
        self.cfg['role'] = 'maintainer'
        with self.assertRaises(TeamLibError): self.publish.propose_entry(self.cfg, self.source, self.workspace)

    def test_request_unmerged_and_merged_material_mismatch(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(self.publish.verify_request(self.cfg, result['request_id'], result)['state'], 'submitted')
        request = self.service.requests[0]; request['state'] = 'MERGED'; request['mergedAt'] = '2026-10-08T00:00:00Z'; request['mergeCommit'] = {'oid': self.commit}
        checked = self.publish.verify_request(self.cfg, result['request_id'], result)
        self.assertEqual(checked['state'], 'submitted'); self.assertEqual(checked['code'], 'STATUS_UNVERIFIED')
        shutil.copytree(self.source, self.base / 'entries/alice/demo')
        self.assertEqual(self.publish.verify_request(self.cfg, result['request_id'], result)['state'], 'published')

    def test_actual_inventory_and_outbound_secret_block_before_push(self):
        (self.source / 'releases/1.0.0/payload/extra.txt').write_text('unlisted')
        with self.assertRaises(TeamLibError): self.publish.propose_entry(self.cfg, self.source, self.workspace)
        (self.source / 'releases/1.0.0/payload/extra.txt').unlink()
        meta = json.loads((self.source / 'meta.json').read_text()); meta['summary'] = 'password'+'=FakeSecretValue123456'; dump(self.source / 'meta.json', meta)
        with self.assertRaises(TeamLibError): self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'for-each-ref', '--format=%(refname)', 'refs/heads/teamlib/').strip(), '')

    def test_request_wrong_base_and_changed_proposal_are_not_published(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.service.requests[0]['baseRefName'] = 'evil'
        with self.assertRaises(TeamLibError): self.publish.verify_request(self.cfg, result['request_id'], result)

    def test_changed_proposal_head_and_offline_merged_status_are_unverified(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.service.requests[0]['headRefOid'] = 'f' * 40
        self.assertEqual(self.publish.verify_request(self.cfg, result['request_id'], result)['code'], 'STATUS_UNVERIFIED')
        request = self.service.requests[0]; request['headRefOid'] = result['head_commit']; request['state'] = 'MERGED'; request['mergedAt'] = '2026-10-08T00:00:00Z'; request['mergeCommit'] = {'oid': self.commit}
        with patch.object(self.publish, 'open_snapshot', side_effect=TeamLibError('REMOTE_FAILED', 'offline')):
            checked = self.publish.verify_request(self.cfg, result['request_id'], result)
        self.assertEqual(checked['state'], 'submitted'); self.assertEqual(checked['code'], 'STATUS_UNVERIFIED')

    def test_current_maintainer_can_propose_state_only_without_config_role(self):
        existing = entry(self.base / 'entries/alice/demo')
        self.git('-C', str(self.base), 'add', '.'); self.git('-C', str(self.base), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'publish')
        self.git('-C', str(self.base), 'push', str(self.remote), 'main')
        self.commit = self.git('-C', str(self.base), 'rev-parse', 'HEAD').strip(); self.snapshot['source_commit'] = self.commit; self.service.head = self.commit
        self.service.login = 'maintainer-gh'
        state = json.loads((self.source / 'state.json').read_text()); state['recommended_version'] = None; dump(self.source / 'state.json', state)
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(result['state'], 'submitted'); self.assertEqual(result['new_versions'], [])

    def test_freshness_retry_has_two_refreshes_maximum(self):
        stale = dict(self.snapshot, source_commit='f' * 40)
        seen = []
        def snapshot(*args, **kw):
            seen.append(1)
            return stale
        with patch.object(self.publish, 'open_snapshot', snapshot):
            with self.assertRaises(TeamLibError) as cm: self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(cm.exception.code, 'CONFLICT'); self.assertEqual(len(seen), 3)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'for-each-ref', '--format=%(refname)', 'refs/heads/teamlib/').strip(), '')

    def test_trusted_base_checker_rejection_blocks_push(self):
        script = self.base / 'tools/check_submission.py'; script.parent.mkdir(exist_ok=True)
        script.write_text('import json\nprint(json.dumps({"allowed": False,"code":"SCOPE_DENIED"}))\nraise SystemExit(2)\n')
        self.git('-C', str(self.base), 'add', '.'); self.git('-C', str(self.base), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'trusted checker change')
        self.git('-C', str(self.base), 'push', str(self.remote), 'main')
        self.commit = self.git('-C', str(self.base), 'rev-parse', 'HEAD').strip(); self.snapshot['source_commit'] = self.commit; self.service.head = self.commit
        with self.assertRaises(TeamLibError): self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'for-each-ref', '--format=%(refname)', 'refs/heads/teamlib/').strip(), '')

    def test_user_old_history_and_payload_are_not_executed_or_uploaded(self):
        marker = self.root / 'executed.txt'
        (self.source / 'releases/1.0.0/payload/SKILL.md').write_text('import pathlib\npathlib.Path(' + repr(str(marker)) + ').write_text("executed")\n')
        from tools.teamlib.package import build_inventory
        manifest_path = self.source / 'releases/1.0.0/manifest.json'
        manifest = json.loads(manifest_path.read_text()); manifest['files'] = build_inventory(manifest_path.parent); dump(manifest_path, manifest)
        self.git('init', '--initial-branch=private', str(self.root))
        private = self.root / 'private.txt'; private.write_text('password'+'=HistoricalFakeSecret123456')
        self.git('-C', str(self.root), 'add', 'private.txt'); self.git('-C', str(self.root), '-c', 'user.name=User', '-c', 'user.email=user@example.invalid', 'commit', '-m', 'private unrelated history')
        private_commit = self.git('-C', str(self.root), 'rev-parse', 'HEAD').strip()
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(result['state'], 'submitted'); self.assertFalse(marker.exists())
        history = self.git('--git-dir=' + str(self.remote), 'rev-list', result['source_branch'])
        self.assertNotIn(private_commit, history)
        self.assertNotIn('private.txt', self.git('--git-dir=' + str(self.remote), 'ls-tree', '-r', '--name-only', result['source_branch']))

    def test_git_content_normalization_cannot_change_verified_material(self):
        attributes = self.base / '.gitattributes'; attributes.write_text('*.md text eol=lf\n')
        self.git('-C', str(self.base), 'add', '.'); self.git('-C', str(self.base), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'trusted git attributes')
        self.git('-C', str(self.base), 'push', str(self.remote), 'main')
        self.commit = self.git('-C', str(self.base), 'rev-parse', 'HEAD').strip(); self.snapshot['source_commit'] = self.commit; self.service.head = self.commit
        payload = self.source / 'releases/1.0.0/payload/SKILL.md'; payload.write_bytes(b'Read safely.\r\n')
        from tools.teamlib.package import build_inventory
        manifest_path = self.source / 'releases/1.0.0/manifest.json'; manifest = json.loads(manifest_path.read_text()); manifest['files'] = build_inventory(manifest_path.parent); dump(manifest_path, manifest)
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        blob = subprocess.run(['git', '--git-dir=' + str(self.remote), 'cat-file', 'blob', result['source_branch'] + ':entries/alice/demo/releases/1.0.0/payload/SKILL.md'], check=True, stdout=subprocess.PIPE).stdout
        self.assertEqual(blob, payload.read_bytes())

    def test_offline_status_preserves_known_submitted_state(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        with patch.object(self.publish, 'get_request', side_effect=TeamLibError('REMOTE_FAILED', 'offline')):
            checked = self.publish.verify_request(self.cfg, result['request_id'], result)
        self.assertEqual(checked['state'], 'submitted'); self.assertEqual(checked['code'], 'STATUS_UNVERIFIED')

    def test_push_completed_but_remote_confirmation_failed_stays_prepared(self):
        original = self.runner; pushed = []
        def uncertain(args, **kwargs):
            if 'ls-remote' in args and pushed: raise subprocess.TimeoutExpired(args, 1)
            result = original(args, **kwargs)
            if 'push' in args: pushed.append(True)
            return result
        with patch.object(self.publish, 'run_command', uncertain):
            result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(result['state'], 'prepared'); self.assertEqual(result['code'], 'STATUS_UNVERIFIED')
        self.assertTrue(pushed); self.assertEqual(len(self.service.requests), 0)

    def test_created_request_head_is_verified_before_returning_success(self):
        original = self.service._gh
        def raced(args):
            value = original(args)
            if args[1:3] == ['pr', 'create']:
                self.service.requests[-1]['headRefOid'] = 'f' * 40
            return value
        self.service._gh = raced
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(result['state'], 'submitted'); self.assertEqual(result['code'], 'STATUS_UNVERIFIED')

    def test_published_status_binds_original_body_title_author_and_request(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        shutil.copytree(self.source, self.base / 'entries/alice/demo')
        request = self.service.requests[0]
        request.update({'state': 'MERGED', 'mergedAt': '2026-10-08T00:00:00Z', 'mergeCommit': {'oid': self.commit}})
        self.assertEqual(self.publish.verify_request(self.cfg, result['request_id'], result)['state'], 'published')
        cases = [('body', 'Changed approval scope.\n<!-- teamlib-operation: ' + result['operation_id'] + ' -->\n'),
                 ('title', 'Changed approval conditions'), ('author', {'login': 'bob-gh'})]
        for field, value in cases:
            original = request.get(field); request[field] = value
            with self.subTest(field=field):
                try:
                    checked = self.publish.verify_request(self.cfg, result['request_id'], result)
                except TeamLibError as exc:
                    self.assertIn(exc.code, {'CONFLICT', 'STATUS_UNVERIFIED'})
                else:
                    self.assertNotEqual(checked['state'], 'published')
                    self.assertEqual(checked['body_sha256'], result['body_sha256'])
                    self.assertEqual(checked['author_login'], result['author_login'])
            request[field] = original
        duplicate = dict(request, number=2, url='https://github.com/acme/library/pull/2')
        self.service.requests.append(duplicate)
        with self.assertRaises(TeamLibError): self.publish.verify_request(self.cfg, '2', result)

    def test_missing_original_review_binding_cannot_be_adopted_from_current_api(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        unbound = dict(result)
        unbound.pop('body_sha256', None); unbound.pop('title_sha256', None)
        checked = self.publish.verify_request(self.cfg, result['request_id'], unbound)
        self.assertEqual(checked['code'], 'STATUS_UNVERIFIED')
        self.assertNotEqual(checked['state'], 'published')

    def test_merge_commit_must_contain_expected_material_not_only_current_shared(self):
        result = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        merge_root = self.root / 'unrelated-merge'; shutil.copytree(self.base, merge_root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        shutil.copytree(self.source, self.base / 'entries/alice/demo')
        self.service.requests[0].update({'state': 'MERGED', 'mergedAt': '2026-10-08T00:00:00Z', 'mergeCommit': {'oid': self.commit}})
        def snapshots(*args, **kwargs):
            return dict(self.snapshot, root=str(merge_root)) if kwargs.get('commit') else dict(self.snapshot)
        with patch.object(self.publish, 'open_snapshot', snapshots):
            checked = self.publish.verify_request(self.cfg, result['request_id'], result)
        self.assertEqual(checked['state'], 'submitted'); self.assertEqual(checked['code'], 'STATUS_UNVERIFIED')

    def test_proposal_retry_keeps_original_review_binding_after_body_changed(self):
        first = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.service.requests[0]['body'] = 'Different review scope.\n<!-- teamlib-operation: ' + first['operation_id'] + ' -->\n'
        second = self.publish.propose_entry(self.cfg, self.source, self.workspace)
        self.assertEqual(second['code'], 'STATUS_UNVERIFIED')
        self.assertEqual(second['body_sha256'], first['body_sha256'])
        persisted = json.loads((self.workspace / 'proposals' / (first['operation_id'] + '.json')).read_text())
        self.assertEqual(persisted['body_sha256'], first['body_sha256'])
        self.assertEqual(len(self.service.requests), 1)

    def test_owner_trial_submission_and_retry_keep_explicit_review_boundary(self):
        original=self.platform.doctor_platform
        def trial(cfg):
            return dict(original(cfg),deployment_mode='owner_trial',owner_trial=True,hard_gate_enforced=False,manual_review_required=True)
        with patch.object(self.publish,'doctor_platform',trial),patch.object(self.platform,'doctor_platform',trial):
            first=self.publish.propose_entry(self.cfg,self.source,self.workspace)
            second=self.publish.propose_entry(self.cfg,self.source,self.workspace)
        for result in (first,second):
            self.assertEqual(result['deployment_mode'],'owner_trial')
            self.assertTrue(result['manual_review_required']);self.assertFalse(result['hard_gate_enforced'])
            self.assertEqual(result['state'],'submitted')
        self.assertEqual(first['request_id'],second['request_id'])
        self.assertIn('owner-only trial',self.service.requests[0]['body'])
        self.assertEqual(len(self.service.requests),1)
