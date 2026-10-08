import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.core_helpers import entry, dump, manifest, state
from tools.teamlib.contracts import TeamLibError,hash_file
from tools.teamlib.dependencies import load_catalog,resolve_dependencies


class DependencyTests(unittest.TestCase):
    def records(self):
        return {('a/root','1.0.0'):{'manifest_sha256':'a'*64,'dependencies':[{'id':'b/leaf','version':'1.0.0','manifest_sha256':'b'*64}]},
                ('b/leaf','1.0.0'):{'manifest_sha256':'b'*64,'dependencies':[]}}

    def test_precise_closure_returns_dependency_before_root(self):
        self.assertEqual(resolve_dependencies(self.records(),('a/root','1.0.0')),[('b/leaf','1.0.0'),('a/root','1.0.0')])

    def test_missing_or_digest_mismatch_blocks_instead_of_latest(self):
        for mode in ('missing','hash'):
            records=self.records()
            if mode=='missing':del records[('b/leaf','1.0.0')]
            else:records[('b/leaf','1.0.0')]['manifest_sha256']='c'*64
            with self.subTest(mode=mode), self.assertRaises(TeamLibError):resolve_dependencies(records,('a/root','1.0.0'))

    def test_cycle_blocks_and_does_not_mutate_records(self):
        records=self.records();records[('b/leaf','1.0.0')]['dependencies']=[{'id':'a/root','version':'1.0.0','manifest_sha256':'a'*64}]
        original=copy.deepcopy(records)
        with self.assertRaises(TeamLibError):resolve_dependencies(records,('a/root','1.0.0'))
        self.assertEqual(records,original)

    def test_catalog_binds_actual_manifest_and_state(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();entry(root/'entries/alice/demo')
            catalog=load_catalog(root);record=catalog[('alice/demo','1.0.0')]
            self.assertEqual(record['manifest_sha256'],hash_file(root/'entries/alice/demo/releases/1.0.0/manifest.json'))
            self.assertEqual(record['state']['owner_key'],'alice')

    def test_catalog_rejects_identity_and_owner_divergence(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();where=entry(root/'entries/alice/demo')
            dump(where/'state.json',state(owner='bob'))
            with self.assertRaises(TeamLibError):load_catalog(root)
