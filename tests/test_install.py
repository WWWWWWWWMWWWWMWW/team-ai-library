import json
import tempfile
import unittest
from pathlib import Path
from tools.teamlib.install import fetch_release, install_release
from tools.teamlib.contracts import TeamLibError
from tests.local_helpers import repository, release, publish


class InstallTests(unittest.TestCase):
    def fixture(self, d):
        from tools.teamlib.snapshots import open_snapshot
        repo = Path(d).resolve()/'source'
        config, workspace = repository(repo)
        return repo, config, workspace, open_snapshot(config,workspace)

    def test_download_install_real_source_and_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            repo, config, workspace, snapshot = self.fixture(d)
            package = fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            self.assertEqual(package['source_commit'],snapshot['source_commit'])
            self.assertTrue(all(not Path(row['path']).is_absolute() for row in package['releases']))
            receipt = install_release(package,Path(d).resolve()/'target',workspace)
            self.assertTrue(Path(receipt['receipt_path']).is_file())
            self.assertEqual(receipt['files'],receipt['baseline_files'])

    def test_all_dependencies_downloaded(self):
        with tempfile.TemporaryDirectory() as d:
            repo, config, workspace, snapshot = self.fixture(d)
            c = release(repo,'alice/c')
            b = release(repo,'alice/b',dependencies=[c])
            release(repo,dependencies=[b])
            publish(repo)
            from tools.teamlib.snapshots import open_snapshot
            package = fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',Path(d).resolve()/'download')
            self.assertEqual(len(package['dependency_lock']),2)
            self.assertEqual(len(package['releases']),3)

    def test_unknown_target_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, workspace, snapshot = self.fixture(d)
            package = fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            target = Path(d).resolve()/'target'
            target.mkdir()
            (target/'unknown').write_text('keep')
            with self.assertRaises(TeamLibError): install_release(package,target,workspace)
            self.assertEqual((target/'unknown').read_text(),'keep')

    def test_withdraw_after_download_blocks_install(self):
        with tempfile.TemporaryDirectory() as d:
            repo, config, workspace, snapshot = self.fixture(d)
            package = fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            state_path = repo/'entries/alice/root/state.json'
            state = json.loads(state_path.read_text())
            state['withdrawn_versions']=['1.0.0']; state['recommended_version']=None
            state_path.write_text(json.dumps(state)); publish(repo)
            with self.assertRaises(TeamLibError) as cm: install_release(package,Path(d).resolve()/'target',workspace)
            self.assertEqual(cm.exception.code,'WITHDRAWN')

    def test_corrupt_or_missing_payload_blocks(self):
        for change in ('corrupt','missing'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                _, _, workspace, snapshot = self.fixture(d)
                package = fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
                payload = Path(package['root'])/'releases/alice/root/1.0.0/payload/instructions.txt'
                if change=='missing': payload.unlink()
                else: payload.write_text('changed')
                with self.assertRaises(TeamLibError): install_release(package,Path(d).resolve()/'target',workspace)

    def test_offline_install_is_blocked_without_success_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,snapshot=self.fixture(d)
            package=fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            Path(config['remote']).rename(Path(d).resolve()/'unavailable.git')
            with self.assertRaises(TeamLibError) as cm: install_release(package,Path(d).resolve()/'target',workspace)
            self.assertEqual(cm.exception.code,'STATUS_UNVERIFIED')
            self.assertFalse((workspace/'installations').exists())

    def test_symlink_target_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _,_,workspace,snapshot=self.fixture(d)
            package=fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            actual=Path(d).resolve()/'actual';actual.mkdir()
            target=Path(d).resolve()/'link';target.symlink_to(actual,target_is_directory=True)
            with self.assertRaises(TeamLibError):install_release(package,target,workspace)
            self.assertEqual(list(actual.iterdir()),[])

    def test_forged_source_commit_cannot_receive_install_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            _,_,workspace,snapshot=self.fixture(d)
            package=fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            package['source_commit']='a'*40
            record={k:v for k,v in package.items() if k not in ('root','config')}
            (Path(package['root'])/'download.json').write_text(json.dumps(record))
            with self.assertRaises(TeamLibError):install_release(package,Path(d).resolve()/'target',workspace)

    def test_nested_install_cannot_mutate_download(self):
        with tempfile.TemporaryDirectory() as d:
            _,_,workspace,snapshot=self.fixture(d)
            package=fetch_release(snapshot,'alice/root','1.0.0',Path(d).resolve()/'download')
            with self.assertRaises(TeamLibError):install_release(package,Path(package['root'])/'target',workspace)

    def test_two_dependency_versions_competing_for_capability_position_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            repo,config,workspace,_=self.fixture(d)
            one=release(repo,'alice/dependency','1.0.0')
            two=release(repo,'alice/dependency','1.1.0')
            release(repo,dependencies=[one,two]);publish(repo)
            from tools.teamlib.snapshots import open_snapshot
            package=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',Path(d).resolve()/'download')
            with self.assertRaises(TeamLibError) as cm:install_release(package,Path(d).resolve()/'target',workspace)
            self.assertEqual(cm.exception.code,'DEPENDENCY_BLOCKED')
            self.assertFalse((workspace/'installations').exists())

    def test_first_install_receipt_failure_restores_empty_target_and_allows_retry(self):
        from unittest.mock import patch
        for existing in (False,True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as d:
                _,_,workspace,snapshot=self.fixture(d);root=Path(d).resolve()
                package=fetch_release(snapshot,'alice/root','1.0.0',root/'download')
                target=root/'target'
                if existing: target.mkdir()
                with patch('tools.teamlib.install.create_receipt',side_effect=OSError('fixture receipt failure')):
                    with self.assertRaises(OSError):install_release(package,target,workspace)
                self.assertEqual(target.exists(),existing)
                if existing:self.assertEqual(list(target.iterdir()),[])
                self.assertEqual(list(workspace.glob('installations/*/receipt.json')),[])
                self.assertTrue(list(target.parent.glob('.teamlib-install-*')))
                receipt=install_release(package,target,workspace)
                self.assertTrue(Path(receipt['receipt_path']).is_file())

    def test_install_binding_failure_restores_target_without_success_receipt(self):
        from unittest.mock import patch
        from tools.teamlib import install as module
        with tempfile.TemporaryDirectory() as d:
            _,_,workspace,snapshot=self.fixture(d);root=Path(d).resolve()
            package=fetch_release(snapshot,'alice/root','1.0.0',root/'download')
            real_write=module.write_json
            def fail_binding(path,record):
                if Path(path).name=='binding.json':raise TeamLibError('INVALID_PACKAGE','fixture binding failure')
                return real_write(path,record)
            with patch('tools.teamlib.install.write_json',side_effect=fail_binding):
                with self.assertRaises(TeamLibError):install_release(package,root/'target',workspace)
            self.assertFalse((root/'target').exists())
            self.assertEqual(list(workspace.glob('installations/*/receipt.json')),[])
            self.assertTrue(list(workspace.glob('installations/*/failed-install.json')))
            receipt=install_release(package,root/'target',workspace)
            self.assertTrue((Path(receipt['receipt_path']).parent/'binding.json').is_file())

    def test_configured_profile_and_provenance_target_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,snapshot=self.fixture(d);root=Path(d).resolve()
            config['target_profiles']={'allowed':{'path':str(root/'allowed'),'tool':'library-directory'}}
            package=fetch_release(snapshot,'alice/root','1.0.0',root/'download');package['config']=config
            for target in (root/'unconfigured',workspace,workspace/'mirrors/protected',workspace/'snapshots/protected'):
                with self.subTest(target=target),self.assertRaises(TeamLibError):install_release(package,target,workspace)
            self.assertFalse((root/'unconfigured').exists())
            self.assertTrue(Path(install_release(package,root/'allowed',workspace)['receipt_path']).is_file())
