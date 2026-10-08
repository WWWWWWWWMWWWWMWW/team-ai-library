import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.core_helpers import dump
from tests.platform_helpers import GithubService, config
from tools.teamlib.contracts import TeamLibError


class PlatformTests(unittest.TestCase):
    def setUp(self):
        from tools.teamlib import platform
        self.platform = platform
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.body = self.root / 'body.md'; self.body.write_text('Please review.\n<!-- teamlib-operation: ' + 'a' * 32 + ' -->\n')
        self.service = GithubService()
        self.patch = patch.object(platform, 'run_command', self.service); self.patch.start(); self.addCleanup(self.patch.stop)

    def test_unconfigured_and_local_cannot_claim_connected_security(self):
        for cfg in ({'platform': 'unconfigured'}, {'platform': 'local', 'remote': '/tmp/demo.git', 'shared_branch': 'main'}):
            with self.assertRaises(TeamLibError): self.platform.doctor_platform(cfg)
        self.assertEqual(self.service.calls, [])

    def test_actual_private_auth_and_protection_are_required(self):
        result = self.platform.doctor_platform(config())
        self.assertEqual(result['actor_key'], 'alice')
        self.assertEqual(result['role'], 'contributor')
        self.assertTrue(result['private'])
        self.assertFalse(result['hard_gate_enforced'])
        for attribute, value in [('private', False), ('protected', False), ('login', 'unmapped-gh')]:
            setattr(self.service, attribute, value)
            with self.assertRaises(TeamLibError): self.platform.doctor_platform(config())
            setattr(self.service, attribute, {'private': True, 'protected': True, 'login': 'alice-gh'}[attribute])

    def test_request_query_before_retry_and_submission_truth(self):
        self.service.create_then_timeout = True
        first = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        second = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.assertEqual(first['state'], 'submitted'); self.assertEqual(second['request_id'], '1')
        self.assertEqual(len(self.service.requests), 1)
        for args, kw in self.service.calls:
            self.assertIs(kw['shell'], False)
            if args[1:3] == ['pr', 'create']:
                self.assertIn('--body-file', args); self.assertNotIn('Please review.', args)

    def test_create_failure_preserves_prepared_without_secret_stderr(self):
        self.service.fail_create = True
        result = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.assertEqual(result['state'], 'prepared')
        self.assertNotIn('sensitive', json.dumps(result))

    def test_secret_title_or_issue_body_blocks_before_remote_write(self):
        from tools.teamlib.package import validate_outbound
        self.body.write_text('password'+'=ThisIsAFakeSecret123456\n<!-- teamlib-operation: ' + 'a' * 32 + ' -->')
        with self.assertRaises(TeamLibError): self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.assertFalse(any(a[1:3] == ['pr', 'create'] for a, _ in self.service.calls))

    def test_governance_issue_idempotency_and_read(self):
        payload = self.root / 'withdraw.json'
        dump(payload, {'operation_id': 'b' * 32, 'id': 'alice/demo', 'version': '1.0.0', 'reason': 'Scope no longer applies'})
        self.service.create_then_timeout = True
        first = self.platform.create_governance_request(config(), 'withdrawal', payload)
        second = self.platform.create_governance_request(config(), 'withdrawal', payload)
        self.assertEqual(first['state'], 'submitted'); self.assertEqual(second['request_id'], '1')
        self.assertEqual(len(self.service.issues), 1)
        self.assertEqual(self.platform.get_governance_request(config(), '1')['state'], 'submitted')

    def test_request_ids_do_not_accept_command_or_foreign_url(self):
        for identifier in ('--help', 'https://github.com/evil/repo/pull/1', '$(touch x)'):
            with self.assertRaises(TeamLibError): self.platform.get_request(config(), identifier)

    def test_governance_same_operation_different_payload_is_conflict(self):
        payload = self.root / 'withdraw.json'
        value = {'operation_id': 'b' * 32, 'id': 'alice/demo', 'version': '1.0.0', 'reason': 'First scope'}
        dump(payload, value)
        self.platform.create_governance_request(config(), 'withdrawal', payload)
        value['reason'] = 'Changed scope'; dump(payload, value)
        with self.assertRaises(TeamLibError): self.platform.create_governance_request(config(), 'withdrawal', payload)

    def test_ambiguous_or_revoked_trusted_mapping_is_denied(self):
        self.service.members['members'].append(dict(self.service.members['members'][0]))
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(config())

    def test_request_same_operation_with_changed_body_is_conflict(self):
        branch = 'teamlib/' + 'a' * 32
        self.platform.create_request(config(), branch, 'Safe title', self.body)
        self.body.write_text('Different approval scope.\n<!-- teamlib-operation: ' + 'a' * 32 + ' -->\n')
        with self.assertRaises(TeamLibError): self.platform.create_request(config(), branch, 'Safe title', self.body)

    def test_body_is_locked_before_external_create(self):
        original = self.service
        actual_bodies = []
        def racing_service(args, **kwargs):
            if args[1:3] == ['pr', 'create']:
                self.body.write_text('password'+'=ChangedBeforeRead123456\n')
                actual_bodies.append(Path(args[args.index('--body-file') + 1]).read_text())
            return original(args, **kwargs)
        with patch.object(self.platform, 'run_command', racing_service):
            result = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.assertEqual(result['state'], 'submitted')
        self.assertNotIn('ChangedBeforeRead', actual_bodies[0])

    def test_governance_unknown_payload_field_blocks_share(self):
        payload = self.root / 'withdraw.json'
        dump(payload, {'operation_id': 'b' * 32, 'id': 'alice/demo', 'version': '1.0.0', 'reason': 'Scope', 'raw_chat': 'Unrelated private chat'})
        with self.assertRaises(TeamLibError): self.platform.create_governance_request(config(), 'withdrawal', payload)
        self.assertEqual(len(self.service.issues), 0)

    def test_create_succeeded_but_followup_query_failed_stays_prepared(self):
        original = self.service
        def uncertain(args, **kwargs):
            if args[1:3] == ['pr', 'list'] and self.service.requests:
                raise subprocess.TimeoutExpired(args, 1)
            return original(args, **kwargs)
        with patch.object(self.platform, 'run_command', uncertain):
            result = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.assertEqual(result['state'], 'prepared')
        self.assertEqual(len(self.service.requests), 1)

    def test_read_gate_needs_private_personal_membership_and_pull_only(self):
        self.service.protected = False
        original = self.service._gh
        def reader(args):
            value = original(args)
            if args[1] == 'api' and args[2] == 'repos/acme/library':
                value['permissions'] = {'pull': True, 'push': False, 'admin': False}
            return value
        self.service._gh = reader
        checked = self.platform.doctor_read(config())
        self.assertEqual(checked['actor_key'], 'alice'); self.assertTrue(checked['read_verified'])
        self.assertFalse(checked['permissions']['push'])
        self.assertFalse(any('/protection' in args[2] for args, _ in self.service.calls if args[1] == 'api'))
        for attribute, value in [('private', False), ('login', 'unmapped-gh')]:
            setattr(self.service, attribute, value)
            with self.assertRaises(TeamLibError): self.platform.doctor_read(config())
            setattr(self.service, attribute, {'private': True, 'login': 'alice-gh'}[attribute])
        def no_pull(args):
            value = reader(args)
            if args[1] == 'api' and args[2] == 'repos/acme/library': value['permissions']['pull'] = False
            return value
        self.service._gh = no_pull
        with self.assertRaises(TeamLibError): self.platform.doctor_read(config())

    def test_read_gate_rejects_bot_even_with_matching_membership(self):
        original = self.service._gh
        def bot(args):
            value = original(args)
            if args[1] == 'api' and args[2] == 'user': value['type'] = 'Bot'
            return value
        self.service._gh = bot
        with self.assertRaises(TeamLibError): self.platform.doctor_read(config())

    def test_get_request_returns_review_digests_without_raw_body_for_readonly_user(self):
        import hashlib
        created = self.platform.create_request(config(), 'teamlib/' + 'a' * 32, 'Safe title', self.body)
        self.service.protected = False
        self.service.permissions = {'pull': True, 'push': False, 'admin': False}
        checked = self.platform.get_request(config(), created['request_id'])
        self.assertEqual(checked['body_sha256'], hashlib.sha256(self.body.read_bytes()).hexdigest())
        self.assertEqual(checked['title_sha256'], hashlib.sha256(b'Safe title').hexdigest())
        self.assertNotIn('body', checked); self.assertNotIn('title', checked)
