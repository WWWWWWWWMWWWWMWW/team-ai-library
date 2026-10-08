"""The directory must reflect shared material rather than candidate or stale evidence."""
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests.core_helpers import entry, release, dump, state, governance
from tools.teamlib.contracts import TeamLibError, hash_file


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        governance(self.root)
        self.where = entry(self.root/'entries/alice/demo')
        self.snapshot = {'root':str(self.root), 'source_commit':'a'*40,
                         'repository':'https://github.com/example/team.git', 'shared_branch':'main'}

    def tearDown(self): self.temp.cleanup()

    def module(self):
        try: return importlib.import_module('tools.teamlib.catalog')
        except ModuleNotFoundError:
            self.fail('The shared-source directory generator has not been implemented.')

    def build(self, **kwargs): return self.module().build_catalog(self.snapshot, **kwargs)

    def evidence(self, version='1.0.0', digest=None, result='passed'):
        return {'id':'alice/demo','version':version,
                'manifest_sha256':digest or hash_file(self.where/f'releases/{version}/manifest.json'),
                'date':'2026-10-08','tool':'AI 1.0','environment':{'os':'macos'},
                'business_scope':'脱敏测试样例','result':result,'evidence':['本地测试记录']}

    def test_shared_provenance_and_concrete_version_entrypoints_are_preserved(self):
        record = self.build()
        self.assertEqual(record['source']['commit'], 'a'*40)
        self.assertEqual(record['capability_count'], 1)
        row = record['releases'][0]
        self.assertEqual((row['id'],row['version']), ('alice/demo','1.0.0'))
        self.assertEqual(row['readme'], 'entries/alice/demo/releases/1.0.0/README.md')
        self.assertEqual(row['entrypoints'], ['entries/alice/demo/releases/1.0.0/payload/SKILL.md'])
        self.assertNotIn(str(self.root), str(record))

    def test_all_seven_categories_are_visible_even_when_empty(self):
        text = self.module().render_markdown(self.build())
        for label in ['技能','工作流','提示词','工具','案例','经验','研究资料']:
            self.assertIn('## '+label, text)
        self.assertIn('尚无已入库条目', text)

    def test_recommendation_is_explicit_and_not_latest_version(self):
        release(self.where/'releases/2.0.0',version='2.0.0')
        rows = self.build()['releases']
        self.assertEqual([r['version'] for r in rows if r['recommended']], ['1.0.0'])
        dump(self.where/'state.json', state(version=None))
        self.assertFalse(any(r['recommended'] for r in self.build()['releases']))

    def test_withdrawn_and_revoked_material_is_not_recommended(self):
        record = state(version=None); record['withdrawn_versions']=['1.0.0']; dump(self.where/'state.json',record)
        row = self.build()['releases'][0]
        self.assertEqual(row['availability'], 'withdrawn')
        self.assertFalse(row['recommended'])
        dump(self.where/'state.json',state())
        dump(self.root/'governance/revocations.json',{'schema_version':1,'revocations':[{'id':'alice/demo','version':'1.0.0','reason':'材料作废'}]})
        row = self.build()['releases'][0]
        self.assertEqual(row['availability'], 'revoked')
        self.assertFalse(row['recommended'])

    def test_verification_requires_exact_version_and_material_digest(self):
        record = state(); record['verification']=[self.evidence(digest='b'*64)]
        dump(self.where/'state.json', record)
        row = self.build()['releases'][0]
        self.assertEqual(row['verification'], [])
        self.assertEqual(row['verification_label'], '未验证')
        record['verification']=[self.evidence()]; dump(self.where/'state.json', record)
        row = self.build()['releases'][0]
        self.assertEqual(len(row['verification']),1)
        self.assertIn('记录范围',row['verification_label'])
        self.assertEqual(row['verification'][0]['business_scope'],'脱敏测试样例')

    def test_failed_and_passed_records_do_not_become_blanket_verification(self):
        record=state(); record['verification']=[self.evidence(),self.evidence(result='failed')]
        dump(self.where/'state.json',record)
        self.assertIn('失败',self.build()['releases'][0]['verification_label'])

    def test_dependency_withdrawal_blocks_recommendation_without_hiding_the_entry(self):
        other=entry(self.root/'entries/bob/check',owner='bob',identifier='bob/check')
        manifest_path=self.where/'releases/1.0.0/manifest.json'
        import json
        manifest=json.loads(manifest_path.read_text())
        manifest['dependencies']=[{'id':'bob/check','version':'1.0.0','manifest_sha256':hash_file(other/'releases/1.0.0/manifest.json')}]
        dump(manifest_path,manifest)
        status=state(owner='bob',version=None); status['withdrawn_versions']=['1.0.0']; dump(other/'state.json',status)
        row=next(r for r in self.build()['releases'] if r['id']=='alice/demo')
        self.assertEqual(row['availability'],'blocked_dependency')
        self.assertFalse(row['recommended'])
        self.assertEqual(row['dependencies'][0]['id'],'bob/check')

    def test_tampered_material_stops_generation(self):
        (self.where/'releases/1.0.0/payload/SKILL.md').write_text('Changed material')
        with self.assertRaises(TeamLibError): self.build()

    def test_pending_requests_are_separate_from_shared_capabilities(self):
        request={'number':3,'kind':'publication','ids':['bob/new'],
                 'head_commit':'b'*40,'url':'https://github.com/example/team/pull/3'}
        record=self.build(pending=[request],pending_status='available')
        self.assertEqual(record['capability_count'],1)
        self.assertEqual(record['pending_requests'],[request])
        self.assertNotIn('bob/new',{r['id'] for r in record['releases']})
        self.assertIn('处理中请求',self.module().render_markdown(record))

    def test_unavailable_pending_list_is_not_reported_as_empty(self):
        record=self.build(pending_status='unavailable')
        self.assertIn('未能刷新',self.module().render_markdown(record))

    def test_text_is_escaped_and_same_snapshot_is_deterministic(self):
        import json
        path=self.where/'meta.json'; meta=json.loads(path.read_text())
        meta['title']='Example | <img src=x>\n[bad](https://example.test)'; dump(path,meta)
        first=self.build(); self.assertEqual(first,self.build())
        text=self.module().render_markdown(first)
        self.assertNotIn('<img src=x>',text)
        self.assertIn('&#124;',text)
        self.assertNotIn('[bad](https://example.test)',text)

    def test_pending_classifier_uses_actual_paths_and_never_exports_request_body(self):
        config={'platform':'github','remote':'https://github.com/example/team.git','shared_branch':'main','publish_mode':'request','auto_merge':False}
        requests=[{'number':n,'head':{'sha':'b'*40},'base':{'ref':'main'},'body':'DO_NOT_EXPORT_BODY'} for n in (1,2,3)]
        files={1:[{'filename':'entries/bob/new/releases/1.0.0/README.md','status':'added'}],
               2:[{'filename':'docs/new.md','status':'added'}],
               3:[{'filename':'entries/alice/demo/state.json','status':'modified'}]}
        def paginated(repo,suffix):
            return requests if '?state=open' in suffix else files[int(suffix.split('/')[2])]
        latest={'state':'open','head':{'sha':'b'*40},'base':{'ref':'main'}}
        with patch('tools.teamlib.platform._paginated',side_effect=paginated):
            with patch('tools.teamlib.platform._api',return_value=latest):
                rows=self.module().collect_pending(config)
        self.assertEqual([r['kind'] for r in rows],['publication','maintenance','governance'])
        self.assertEqual(rows[0]['ids'],['bob/new'])
        self.assertNotIn('DO_NOT_EXPORT_BODY',str(rows))

    def test_changed_request_head_blocks_pending_collection(self):
        config={'platform':'github','remote':'https://github.com/example/team.git','shared_branch':'main','publish_mode':'request','auto_merge':False}
        request={'number':1,'head':{'sha':'b'*40},'base':{'ref':'main'}}
        with patch('tools.teamlib.platform._paginated',side_effect=[[request],[{'filename':'docs/new.md','status':'added'}]]):
            with patch('tools.teamlib.platform._api',return_value={'state':'open','head':{'sha':'c'*40},'base':{'ref':'main'}}):
                with self.assertRaises(TeamLibError): self.module().collect_pending(config)

    def test_remote_failure_leaves_existing_local_directory_unchanged(self):
        import contextlib, io, sys
        from tools.build_catalog import main
        config=self.root/'library.json'
        dump(config,{'schema_version':1,'platform':'local','remote':str(self.root/'remote'),
                     'shared_branch':'main','workspace':'.teamlib-workspace','publish_mode':'request',
                     'auto_merge':False,'target_profiles':{}})
        directory=self.root/'docs'; directory.mkdir()
        target=directory/'CATALOG.md'; target.write_text('Preserve old directory')
        with patch.object(sys,'argv',['build_catalog.py','--config',str(config),'--output-dir',str(directory)]):
            with patch('tools.build_catalog.open_snapshot',side_effect=TeamLibError('REMOTE_FAILED','Unavailable')):
                with contextlib.redirect_stdout(io.StringIO()): result=main()
        self.assertEqual(result,2)
        self.assertEqual(target.read_text(),'Preserve old directory')

    def test_existing_manual_directory_is_not_overwritten(self):
        directory=self.root/'docs'; directory.mkdir()
        path=directory/'CATALOG.md'; path.write_text('My manual directory')
        with self.assertRaises(TeamLibError): self.module().write_catalog(self.build(),directory)
        self.assertEqual(path.read_text(),'My manual directory')

    def test_generated_outputs_can_be_refreshed_and_machine_index_matches(self):
        import json
        directory=self.root/'docs'
        record=self.build()
        self.module().write_catalog(record,directory)
        self.module().write_catalog(record,directory)
        self.assertEqual(json.loads((directory/'catalog.json').read_text()),record)
        self.assertIn('能力总目录',(directory/'CATALOG.md').read_text())


if __name__=='__main__': unittest.main()
