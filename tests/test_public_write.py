import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.core_helpers import dump
from tests.platform_helpers import GithubService
from tools.teamlib.contracts import TeamLibError


class PublicWriteTests(unittest.TestCase):
    def test_public_write_config_is_explicit_and_direct(self):
        from tools.teamlib.config import load_config
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {
                'schema_version': 1,
                'remote': 'https://github.com/acme/library.git',
                'shared_branch': 'main',
                'platform': 'github',
                'workspace': '.cache/teamlib',
                'publish_mode': 'direct',
                'auto_merge': False,
                'deployment_mode': 'public_write',
                'target_profiles': {},
            }
            dump(root / 'library.json', value)
            self.assertEqual(load_config(root / 'library.json')['deployment_mode'], 'public_write')
            for invalid in (
                dict(value, publish_mode='request'),
                dict(value, deployment_mode='protected'),
                dict(value, auto_merge=True),
            ):
                dump(root / 'library.json', invalid)
                with self.assertRaises(TeamLibError):
                    load_config(root / 'library.json')

    def test_public_write_uses_github_write_and_does_not_require_member_allowlist(self):
        from tools.teamlib import platform
        service = GithubService()
        service.private = False
        service.protected = False
        service.login = 'new-contributor'
        service.members = {'schema_version': 1, 'members': []}
        config = {
            'schema_version': 1,
            'remote': 'https://github.com/acme/library.git',
            'shared_branch': 'main',
            'platform': 'github',
            'publish_mode': 'direct',
            'auto_merge': False,
            'deployment_mode': 'public_write',
        }
        with patch.object(platform, 'run_command', service):
            result = platform.doctor_platform(config)
        self.assertTrue(result['public'])
        self.assertTrue(result['direct_write'])
        self.assertEqual(result['actor_key'], 'new-contributor')
        self.assertEqual(result['role'], 'contributor')
        self.assertFalse(result['manual_review_required'])
        self.assertFalse(any(args[1:3] == ['pr', 'create'] for args, _ in service.calls if args[0] == 'gh'))


if __name__ == '__main__':
    unittest.main()
