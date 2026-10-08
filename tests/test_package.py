import json
import tempfile
import unittest
from pathlib import Path
from tests.core_helpers import dump, entry, release


class PackageTests(unittest.TestCase):
    def test_manifest_not_self_hashed(self):
        from tools.teamlib.package import build_inventory, validate_release
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); release(root)
            self.assertEqual([r['path'] for r in build_inventory(root)],['README.md','payload/SKILL.md'])
            self.assertEqual(validate_release(root)['id'],'alice/demo')

    def test_omitted_missing_hash_and_case_collisions(self):
        from tools.teamlib.package import validate_release
        from tools.teamlib.contracts import TeamLibError
        for mode in ['extra','missing','hash','case','traversal']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root=Path(d); m=release(root)
                if mode=='extra': (root/'payload'/'extra.py').write_text('pass')
                if mode=='missing': (root/'payload'/'SKILL.md').unlink()
                if mode=='hash': (root/'payload'/'SKILL.md').write_text('changed')
                if mode=='case': (root/'payload'/'skill.md').write_text('collision')
                if mode=='traversal': m['entrypoints']=['../fixture_value']; dump(root/'manifest.json',m)
                with self.assertRaises(TeamLibError): validate_release(root)

    def test_symlink_and_nested_symlink_rejected(self):
        from tools.teamlib.package import build_inventory
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'release'; release(root)
            (root/'payload'/'link').symlink_to(root/'README.md')
            with self.assertRaises(TeamLibError): build_inventory(root)
            (root/'payload'/'link').unlink(); (root/'payload'/'nested').symlink_to(root/'payload',target_is_directory=True)
            with self.assertRaises(TeamLibError): build_inventory(root)

    def test_outbound_scans_meta_body_message_and_no_secret_echo(self):
        from tools.teamlib.package import validate_outbound
        from tools.teamlib.contracts import TeamLibError
        fixture_value='ghp_'+'A'*36
        for where in ['meta','body','message','payload']:
            with self.subTest(where=where), tempfile.TemporaryDirectory() as d:
                root=Path(d)/'entry'; entry(root); body=Path(d)/'body.md'; body.write_text('Review material')
                message='Publish demo'
                if where=='meta': m=json.loads((root/'meta.json').read_text()); m['summary']=fixture_value; dump(root/'meta.json',m)
                if where=='body': body.write_text(fixture_value)
                if where=='message': message=fixture_value
                if where=='payload': (root/'releases'/'1.0.0'/'payload'/'SKILL.md').write_text(fixture_value)
                with self.assertRaises(TeamLibError) as caught: validate_outbound(root,message,body)
                self.assertNotIn(fixture_value,str(caught.exception)); self.assertNotIn(fixture_value,str(caught.exception.data))

    def test_opaque_content_unapproved_and_clean_share(self):
        from tools.teamlib.package import validate_outbound
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'entry'; entry(root); body=Path(d)/'body.md'; body.write_text('Clean body')
            self.assertTrue(validate_outbound(root,'Publish example',body)['allowed'])
            (root/'releases'/'1.0.0'/'payload'/'archive.zip').write_bytes(b'PK\x00\xff')
            with self.assertRaises(TeamLibError): validate_outbound(root,'Publish',body)

    def test_missing_manifest_returns_controlled_error(self):
        from tools.teamlib.package import validate_release
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); release(root); (root/'manifest.json').unlink()
            with self.assertRaises(TeamLibError): validate_release(root)

    def test_nonregular_json_is_rejected_without_blocking(self):
        import os, subprocess, sys
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'pipe'; os.mkfifo(path)
            script='from tools.teamlib.contracts import read_json,TeamLibError\nimport sys\ntry: read_json(sys.argv[1])\nexcept TeamLibError: sys.exit(0)\nsys.exit(1)'
            try: result=subprocess.run([sys.executable,'-c',script,str(path)],timeout=0.5,capture_output=True)
            except subprocess.TimeoutExpired: self.fail('Nonregular JSON read blocked on FIFO')
            self.assertEqual(result.returncode,0)

    def test_binary_embedded_secret_cannot_be_approved(self):
        from tools.teamlib.package import scan_file
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'image.png'; path.write_bytes(b'\x89PNG\xffghp_'+b'A'*36+b'\x00')
            with self.assertRaises(TeamLibError) as caught: scan_file(path)
            self.assertEqual(caught.exception.data['category'],'secret_like_text')

    def test_release_budgets_apply_to_inventory(self):
        from tools.teamlib.package import build_inventory
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); release(root)
            with (root/'payload'/'large.txt').open('wb') as f: f.truncate(5*1024*1024+1)
            with self.assertRaises(TeamLibError): build_inventory(root)
            (root/'payload'/'large.txt').unlink()
            for n in range(500): (root/'payload'/('file'+str(n))).write_text('a')
            with self.assertRaises(TeamLibError): build_inventory(root)

    def test_archive_magic_cannot_be_hidden_by_filename(self):
        from tools.teamlib.package import scan_file
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'notes.txt'; path.write_bytes(b'PK\x03\x04apparently readable material')
            with self.assertRaises(TeamLibError) as caught: scan_file(path)
            self.assertEqual(caught.exception.data['category'],'opaque_archive')

    def test_unicode_escaped_json_secrets_are_blocked_without_echo(self):
        from tools.teamlib.package import validate_outbound
        from tools.teamlib.contracts import TeamLibError, hash_file
        from tests.core_helpers import state
        fixture_value='ghp_'+'B'*36
        escaped=''.join('\\u%04x' % ord(c) for c in fixture_value)
        for location in ['meta','manifest','state','request_value','request_key']:
            with self.subTest(location=location), tempfile.TemporaryDirectory() as d:
                root=Path(d)/'entry'; entry(root); body=Path(d)/'body.json'; dump(body,{'request':'review'})
                if location=='meta':
                    path=root/'meta.json'; record=json.loads(path.read_text()); record['summary']=fixture_value
                elif location=='manifest':
                    path=root/'releases/1.0.0/manifest.json'; record=json.loads(path.read_text()); record['scope']['includes'].append(fixture_value)
                elif location=='state':
                    path=root/'state.json'; record=state(); record['verification']=[{'id':'alice/demo','version':'1.0.0','manifest_sha256':hash_file(root/'releases/1.0.0/manifest.json'),'date':'2026-10-08','tool':'AI 1.0','environment':{'os':'macOS'},'business_scope':'documentation','result':'unverified','evidence':[fixture_value]}]
                elif location=='request_value': path=body; record={'nested':[{'message':fixture_value}]}
                else: path=body; record={'nested':[{fixture_value:'ordinary'}]}
                path.write_text(json.dumps(record).replace(fixture_value,escaped))
                with self.assertRaises(TeamLibError) as caught: validate_outbound(root,'Publish',body)
                self.assertNotIn(fixture_value,str(caught.exception)); self.assertNotIn(fixture_value,str(caught.exception.data))
                self.assertEqual(caught.exception.data['category'],'secret_like_text')

    def test_json_key_value_assignment_and_markdown_body_are_decoded(self):
        from tools.teamlib.package import scan_text, scan_file
        from tools.teamlib.contracts import TeamLibError
        fixture_value='FAKE_VALUE_FOR_ISOLATED_TEST'; encoded=''.join('\\u%04x' % ord(c) for c in fixture_value)
        text=json.dumps({'nested':[{''.join(['to','ken']):fixture_value}]}).replace(fixture_value,encoded)
        with self.assertRaises(TeamLibError) as caught: scan_text(text)
        self.assertNotIn(fixture_value,str(caught.exception.data))
        with tempfile.TemporaryDirectory() as d:
            body=Path(d)/'body.md'; body.write_text('Review this request:\n```json\n'+text+'\n```')
            with self.assertRaises(TeamLibError): scan_file(body)

    def test_successful_outbound_result_contains_no_decoded_material(self):
        from tools.teamlib.package import validate_outbound
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'entry'; entry(root); body=Path(d)/'body.md'; body.write_text('review')
            result=validate_outbound(root,'Publish',body)
            self.assertEqual(set(result),{'allowed','state','checks','release_count'})
