import tempfile
import unittest
from pathlib import Path
from tests.core_helpers import dump


class ConfigTests(unittest.TestCase):
    def config(self):
        return {'schema_version': 1, 'remote': '', 'shared_branch': '', 'platform': 'unconfigured', 'workspace': '.cache/teamlib', 'publish_mode': 'request', 'auto_merge': False, 'target_profiles': {}}

    def test_unconfigured_is_explicit_and_runtime_paths(self):
        from tools.teamlib.config import load_config
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'library.json'; dump(p,self.config()); c=load_config(p)
            self.assertEqual(c['platform'],'unconfigured'); self.assertEqual(c['repository_root'],str(Path(d).resolve()))
            self.assertTrue(Path(c['workspace']).is_absolute())

    def test_optional_deployment_mode_defaults_to_protected(self):
        from tools.teamlib.config import load_config
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'library.json'; dump(p,self.config())
            self.assertEqual(load_config(p)['deployment_mode'], 'protected')

    def test_owner_trial_is_explicit_and_only_supported_by_github(self):
        from tools.teamlib.config import load_config
        from tools.teamlib.contracts import TeamLibError, validate_record
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'library.json'
            good=dict(self.config(), platform='github', remote='https://github.com/acme/library.git', shared_branch='main', deployment_mode='owner_trial')
            dump(p,good)
            self.assertEqual(load_config(p)['deployment_mode'], 'owner_trial')
            validate_record('library',good)
            for change in [{'deployment_mode':'unknown'}, {'deployment_mode':None}, {'platform':'unconfigured','remote':'','shared_branch':''}, {'platform':'local','remote':str(Path(d)/'remote.git')}]:
                bad=dict(good,**change); dump(p,bad)
                with self.subTest(change=change), self.assertRaises(TeamLibError): load_config(p)
                with self.subTest(schema=change), self.assertRaises(TeamLibError): validate_record('library',bad)

    def test_reject_missing_insecure_workspace_credentials_and_modes(self):
        from tools.teamlib.config import load_config
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'library.json'
            for change in [{'publish_mode':'direct'}, {'auto_merge':True}, {'workspace':'../escape'}, {'workspace':'/'}, {'remote':'https'+ '://user:'+'supersecret@example.com/repo.git'}, {''.join(['to','ken']):'credential'}]:
                c=self.config(); c.update(change); dump(p,c)
                with self.subTest(change=change), self.assertRaises(TeamLibError): load_config(p)
            c=self.config(); del c['shared_branch']; dump(p,c)
            with self.assertRaises(TeamLibError): load_config(p)
            (Path(d)/'link').symlink_to(Path(d))
            c=self.config(); c['workspace']='link/cache'; dump(p,c)
            with self.assertRaises(TeamLibError): load_config(p)

    def test_repo_ancestors_and_profile_layout_overlap_are_rejected(self):
        from tools.teamlib.config import load_config
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); repo=root/'repo'; repo.mkdir(); p=repo/'library.json'
            for change in [{'workspace':str(root)}, {'target_profiles':{'a':{'path':str(root)}}}, {'target_profiles':{'a':{'path':'.cache/teamlib'}}}, {'target_profiles':{'a':{'path':'.cache'}}}, {'target_profiles':{'a':{'path':'.cache/teamlib/target'}}}, {'target_profiles':{'a':{'path':'installed'},'b':{'path':'installed'}}}, {'target_profiles':{'a':{'path':'installed'},'b':{'path':'installed/nested'}}}]:
                c=self.config(); c.update(change); dump(p,c)
                with self.subTest(change=change), self.assertRaises(TeamLibError): load_config(p)

    def test_local_platform_remote_is_only_filesystem(self):
        from tools.teamlib.config import load_config
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); p=root/'library.json'
            for remote in ['https://github.com/example/private.git','ssh://git@github.com/example/private.git','git://example.org/repo','git@github.com:example/private.git','ext::anything','file://example.org/repo']:
                c=self.config(); c.update(platform='local',remote=remote,shared_branch='shared'); dump(p,c)
                with self.subTest(remote=remote), self.assertRaises(TeamLibError): load_config(p)
            remote=root/'team remote.git'; remote.mkdir()
            for value in [str(remote),remote.as_uri()]:
                c=self.config(); c.update(platform='local',remote=value,shared_branch='shared'); dump(p,c)
                self.assertEqual(load_config(p)['remote'],str(remote))
