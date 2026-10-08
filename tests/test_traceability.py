import tempfile
import unittest
from pathlib import Path
from tools.teamlib.reuse import record_run, derived_provenance
from tools.teamlib.contracts import TeamLibError


class TraceabilityTests(unittest.TestCase):
    def test_record_local_multiple_sources(self):
        with tempfile.TemporaryDirectory() as d:
            source=dict(repository='fake',shared_branch='shared',source_commit='a'*40,id='alice/root',version='1.0.0',manifest_sha256='b'*64)
            result=record_run(Path(d).resolve(),[source,dict(source,id='alice/dep')],dict(task_goal='planning',environment={'os':'macos'},result='passed',artifacts=['output.md'],change_summary='none',unverified=['runtime']))
            self.assertEqual(len(result['sources']),2)
            self.assertTrue(Path(result['record_path']).is_file())

    def test_sensitive_raw_data_not_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(TeamLibError): record_run(Path(d).resolve(),[],dict(task_goal='test',environment={},result='passed',artifacts=[],change_summary='none',unverified=[],chat='raw confidential data'))
            self.assertEqual(list(Path(d).resolve().iterdir()),[])

    def test_derived_preserves_original_identity(self):
        source=dict(repository='fake',source_commit='a'*40,id='alice/root',version='1.0.0',manifest_sha256='b'*64)
        derived=derived_provenance(source,['README.md'],'local wording')
        self.assertEqual(derived['derived_from'],source)
        self.assertFalse(derived['business_verified'])

    def test_fake_secret_is_blocked_without_copying_original(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(TeamLibError) as cm:
                record_run(Path(d).resolve(),[],dict(task_goal='token'+'=FAKE_VALUE_FOR_ISOLATED_TEST',environment={},result='passed',artifacts=[],change_summary='none',unverified=[]))
            self.assertNotIn('FAKE_VALUE',str(cm.exception))
            self.assertEqual(list(Path(d).resolve().iterdir()),[])

    def test_derived_origin_requires_exact_hash_commit_and_repository_shape(self):
        source=dict(repository='fake',source_commit='a'*40,id='alice/root',version='1.0.0',manifest_sha256='b'*64)
        for key,value in [('source_commit','invalid'),('manifest_sha256','invalid'),('source_commit',123),('repository',''),('repository',123),('repository','https'+ '://fake-user:'+'fake-password@example.invalid/private.git')]:
            with self.subTest(key=key,value=value),self.assertRaises(TeamLibError):derived_provenance(dict(source,**{key:value}),['README.md'],'local wording')
