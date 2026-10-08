import json
import tempfile
import unittest
from pathlib import Path
from tests.local_helpers import repository, release, publish, context
from tools.teamlib.reuse import preflight_reuse
from tools.teamlib.install import fetch_release, install_release
from tools.teamlib.contracts import TeamLibError


class ReuseTests(unittest.TestCase):
    def fixture(self,d,chain=False):
        from tools.teamlib.snapshots import open_snapshot
        repo=Path(d).resolve()/'source'; config,workspace=repository(repo)
        if chain:
            c=release(repo,'alice/c'); b=release(repo,'alice/b',dependencies=[c]); release(repo,dependencies=[b]); publish(repo)
        package=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',Path(d).resolve()/'download')
        return repo,config,workspace,package

    def test_temporary_reuse_does_not_install(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d)
            result=preflight_reuse(config,dict(download_path=package['root']),context(),workspace)
            self.assertEqual(result['state'],'prepared')
            self.assertFalse(result['business_verified'])
            self.assertFalse((workspace/'installations').exists())

    def test_transitive_material_changed_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d,True)
            (Path(package['root'])/'releases/alice/c/1.0.0/README.md').write_text('local')
            with self.assertRaises(TeamLibError): preflight_reuse(config,dict(download_path=package['root']),context(),workspace)

    def test_dependency_withdrawal_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            repo,config,workspace,package=self.fixture(d,True)
            path=repo/'entries/alice/c/state.json'; state=json.loads(path.read_text()); state['withdrawn_versions']=['1.0.0'];state['recommended_version']=None;path.write_text(json.dumps(state));publish(repo)
            with self.assertRaises(TeamLibError) as cm: preflight_reuse(config,dict(download_path=package['root']),context(),workspace)
            self.assertEqual(cm.exception.code,'WITHDRAWN')

    def test_scope_environment_authorization_fail_closed(self):
        for key in ('scope','environment','effects'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as d:
                _,config,workspace,package=self.fixture(d); ctx=context()
                if key=='scope': ctx['task_scope']['includes']=['production']
                if key=='environment': ctx['environment']['os']='windows'
                if key=='effects': ctx['effects_authorized']=[]
                with self.assertRaises(TeamLibError): preflight_reuse(config,dict(download_path=package['root']),ctx,workspace)

    def test_receipt_actual_change_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d)
            receipt=install_release(package,Path(d).resolve()/'target',workspace)
            (Path(receipt['target'])/'releases/alice/root/1.0.0/README.md').write_text('local')
            with self.assertRaises(TeamLibError): preflight_reuse(config,dict(receipt_path=receipt['receipt_path']),context(),workspace)

    def test_offline_never_cached_success(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d)
            Path(config['remote']).rename(Path(d).resolve()/'unavailable.git')
            with self.assertRaises(TeamLibError): preflight_reuse(config,dict(download_path=package['root']),context(),workspace)

    def test_receipt_unmodified_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d)
            receipt=install_release(package,Path(d).resolve()/'target',workspace)
            result=preflight_reuse(config,dict(receipt_path=receipt['receipt_path']),context(),workspace)
            self.assertEqual(result['state'],'prepared')

    def test_source_sha_revocation_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            repo,config,workspace,package=self.fixture(d)
            (repo/'governance/revocations.json').write_text(json.dumps(dict(schema_version=1,revocations=[dict(source_commit=package['source_commit'],reason='fixture fake incident')])))
            publish(repo)
            with self.assertRaises(TeamLibError) as cm: preflight_reuse(config,dict(download_path=package['root']),context(),workspace)
            self.assertEqual(cm.exception.code,'WITHDRAWN')

    def test_malformed_current_revocations_fail_closed_controlled(self):
        records=[dict(schema_version=1),dict(schema_version=1,revocations=[],unknown=[]),dict(schema_version=1,revocations=[],revoked_commits=123),dict(schema_version=1,revocations=[],manifest_sha256s=['invalid']),dict(schema_version=1,revocations=[{'source_commit':'a'*40,'unknown':True}]),dict(schema_version=1,revocations=[{'id':'alice/root','version':123}]),dict(schema_version=True,revocations=[]),dict(schema_version=1,revocations=[{'source_commit':'a'*40,'reason':123}])]
        for record in records:
            with self.subTest(record=record),tempfile.TemporaryDirectory() as d:
                repo,config,workspace,package=self.fixture(d)
                (repo/'governance/revocations.json').write_text(json.dumps(record));publish(repo)
                with self.assertRaises(TeamLibError) as cm:preflight_reuse(config,dict(download_path=package['root']),context(),workspace)
                self.assertEqual(cm.exception.code,'STATUS_UNVERIFIED')

    def test_receipt_reuse_rejects_target_rebinding(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            _,config,workspace,package=self.fixture(d)
            root=Path(d).resolve();receipt=install_release(package,root/'controlled',workspace)
            shutil.copytree(root/'controlled',root/'unmanaged')
            receipt['target']=str(root/'unmanaged');Path(receipt['receipt_path']).write_text(json.dumps(receipt))
            with self.assertRaises(TeamLibError) as cm:preflight_reuse(config,dict(receipt_path=receipt['receipt_path']),context(),workspace)
            self.assertEqual(cm.exception.code,'CONFLICT')
