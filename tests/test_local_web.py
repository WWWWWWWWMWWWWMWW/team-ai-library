"""Offline page packaging must preserve exact shared material and safe output."""
import contextlib
import importlib
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests.core_helpers import entry, governance, dump
from tools.teamlib.catalog import build_catalog, write_catalog
from tools.teamlib.contracts import TeamLibError, hash_file


class LocalWebTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        governance(self.root)
        self.where=entry(self.root/'entries/alice/demo')
        self.snapshot={'root':str(self.root),'source_commit':'a'*40,
                       'repository':'https://github.com/example/team.git','shared_branch':'main'}
        self.template=self.root/'shell.html'
        self.template.write_text('<!doctype html><script id="library-data" type="application/json">__TEAMLIB_DATA__</script>')

    def tearDown(self): self.temp.cleanup()

    def module(self):
        try: return importlib.import_module('tools.teamlib.local_web')
        except ModuleNotFoundError: self.fail('Local web packaging is not implemented.')

    def record(self): return self.module().build_web_record(self.snapshot,build_catalog(self.snapshot))

    def change_material(self,text,path='README.md'):
        folder=self.where/'releases/1.0.0'
        (folder/path).write_text(text)
        manifest=json.loads((folder/'manifest.json').read_text())
        for item in manifest['files']:
            if item['path']==path:
                item['sha256']=hash_file(folder/path); item['size']=(folder/path).stat().st_size
        dump(folder/'manifest.json',manifest)

    def test_content_and_catalog_use_one_concrete_shared_snapshot(self):
        self.change_material('共享说明正文')
        record=self.record()
        self.assertEqual(record['source']['commit'],'a'*40)
        material=record['releases'][0]['materials'][0]
        self.assertEqual(material['text'],'共享说明正文')
        self.assertTrue(material['displayable'])
        self.assertNotIn(str(self.root),json.dumps(record))
        self.assertRegex(record['generated_at'],r'^\d{4}-\d{2}-\d{2}T.*\+00:00$')

    def test_forged_catalog_or_wrong_source_cannot_supply_body(self):
        for key in ('source','releases'):
            record=build_catalog(self.snapshot)
            if key=='source': record['source']['commit']='b'*40
            else: record['releases'][0]['summary']='Pretend other content'
            with self.assertRaises(TeamLibError): self.module().build_web_record(self.snapshot,record)

    def test_changed_actual_material_blocks_packaging(self):
        record=build_catalog(self.snapshot)
        (self.where/'releases/1.0.0/README.md').write_text('not in inventory')
        with self.assertRaises(TeamLibError): self.module().build_web_record(self.snapshot,record)

    def test_html_and_script_text_remain_inert_in_embedded_json(self):
        text='</script><script>window.injected=true</script><img src="https://example.test/image">\u2028'
        self.change_material(text)
        record=self.record()
        html=self.module().render_web(record,template=self.template)
        self.assertNotIn(text,html)
        self.assertEqual(html.count('</script>'),1)
        encoded=re.search(r'type="application/json">(.*?)</script>',html,re.S).group(1)
        self.assertEqual(json.loads(encoded)['releases'][0]['materials'][0]['text'],text)

    def test_scripts_and_binary_text_are_explicitly_not_embedded(self):
        folder=self.where/'releases/1.0.0'
        manifest=json.loads((folder/'manifest.json').read_text())
        (folder/'payload/run.py').write_text('raise RuntimeError("NEVER_EXECUTE")')
        manifest['entrypoints']=['payload/run.py']
        manifest['files'].append({'path':'payload/run.py','size':(folder/'payload/run.py').stat().st_size,'sha256':hash_file(folder/'payload/run.py')})
        manifest['files'].sort(key=lambda r:r['path']); dump(folder/'manifest.json',manifest)
        record=self.record(); material=record['releases'][0]['materials'][1]
        self.assertFalse(material['displayable'])
        self.assertIn('reason',material)
        self.assertNotIn('NEVER_EXECUTE',json.dumps(record))
        self.change_material('not a safe\x00text')
        self.assertFalse(self.record()['releases'][0]['materials'][0]['displayable'])

    def test_oversized_text_is_marked_not_silently_truncated(self):
        self.change_material('中'*50000)
        material=self.record()['releases'][0]['materials'][0]
        self.assertFalse(material['displayable']); self.assertNotIn('text',material)
        self.assertIn('reason',material)

    def test_manual_html_prevents_all_catalog_writes(self):
        output=self.root/'docs'; output.mkdir()
        (output/'local-library.html').write_text('Preserve manual page')
        rendered=self.module().render_web(self.record(),template=self.template)
        with self.assertRaises(TeamLibError): write_catalog(build_catalog(self.snapshot),output,web_html=rendered)
        self.assertFalse((output/'catalog.json').exists())
        self.assertEqual((output/'local-library.html').read_text(),'Preserve manual page')

    def test_generated_page_can_refresh_and_failed_replace_keeps_last_page(self):
        output=self.root/'docs'
        record=self.record(); rendered=self.module().render_web(record,template=self.template)
        paths=write_catalog(build_catalog(self.snapshot),output,web_html=rendered)
        self.assertIn('html',paths)
        write_catalog(build_catalog(self.snapshot),output,web_html=rendered)
        old=(output/'local-library.html').read_text()
        original=__import__('os').replace
        def fail_html(source,target):
            if Path(target).name=='local-library.html': raise OSError('synthetic write failure')
            original(source,target)
        with patch('tools.teamlib.catalog.os.replace',side_effect=fail_html):
            with self.assertRaises(OSError): write_catalog(build_catalog(self.snapshot),output,web_html=rendered)
        self.assertEqual((output/'local-library.html').read_text(),old)
        self.assertEqual(list(output.glob('.teamlib-catalog-*')),[])

    def test_remote_failure_preserves_existing_page(self):
        from tools.build_catalog import main
        config=self.root/'library.json'
        dump(config,{'schema_version':1,'platform':'local','remote':str(self.root/'remote'),'shared_branch':'main',
                     'workspace':'.teamlib-workspace','publish_mode':'request','auto_merge':False,'target_profiles':{}})
        output=self.root/'docs'; output.mkdir(); (output/'local-library.html').write_text('Last complete page')
        with patch('sys.argv',['build_catalog.py','--config',str(config),'--output-dir',str(output)]):
            with patch('tools.build_catalog.open_snapshot',side_effect=TeamLibError('REMOTE_FAILED','Unavailable')):
                with contextlib.redirect_stdout(io.StringIO()): result=main()
        self.assertEqual(result,2)
        self.assertEqual((output/'local-library.html').read_text(),'Last complete page')

    def test_missing_or_duplicate_template_slot_is_rejected(self):
        for template in ('<html>no slot</html>','__TEAMLIB_DATA____TEAMLIB_DATA__'):
            self.template.write_text(template)
            with self.assertRaises(TeamLibError): self.module().render_web(self.record(),template=self.template)


if __name__=='__main__': unittest.main()
