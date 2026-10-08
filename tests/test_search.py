import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.core_helpers import entry,dump,meta,state
from tools.teamlib.search import search_entries


class SearchTests(unittest.TestCase):
    def test_chinese_alias_targets_concrete_recommended_version(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();where=entry(root/'entries/alice/demo')
            m=meta();m.update(title='相册资源检查',summary='批量核对资源完整性',aliases=['查缺图'],tags=['相册','资源'])
            dump(where/'meta.json',m)
            results=search_entries(root,'查缺图')
            self.assertEqual(len(results),1)
            self.assertEqual((results[0]['id'],results[0]['version']),('alice/demo','1.0.0'))
            self.assertEqual(results[0]['scope']['excludes'],['production'])

    def test_withdrawn_version_visible_for_audit_but_not_recommended(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();where=entry(root/'entries/alice/demo')
            s=state(version=None);s['withdrawn_versions']=['1.0.0'];dump(where/'state.json',s)
            rows=search_entries(root,'Demo')
            self.assertEqual(rows[0]['state'],'withdrawn')
            self.assertFalse(rows[0]['recommended'])

    def test_unrelated_query_does_not_make_up_a_match(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();entry(root/'entries/alice/demo')
            self.assertEqual(search_entries(root,'充值订单批量生成'),[])
