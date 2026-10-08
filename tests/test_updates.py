import tempfile
import unittest
from pathlib import Path
from tools.teamlib.updates import compare_update


class UpdateTests(unittest.TestCase):
    def setup_roots(self, d, texts):
        roots = [Path(d).resolve()/name for name in ('base','local','upstream')]
        for root, text in zip(roots, texts):
            root.mkdir()
            if text is not None:
                (root/'README.md').write_text(text)
        return roots

    def test_both_changed_keeps_original(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self.setup_roots(d, ('old','local','new'))
            report = compare_update(*roots)
            self.assertIn('README.md', report['conflicts'])
            self.assertEqual((roots[1]/'README.md').read_text(),'local')

    def test_local_and_upstream_separate_changes_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self.setup_roots(d, ('old','local','old'))
            (roots[1]/'unknown.txt').write_text('keep')
            (roots[2]/'script.bin').write_bytes(b'new')
            result = compare_update(*roots)
            self.assertEqual(result['conflicts'], [])
            candidate = Path(result['candidate'])
            self.assertEqual((candidate/'README.md').read_text(),'local')
            self.assertEqual((candidate/'unknown.txt').read_text(),'keep')
            self.assertEqual((candidate/'script.bin').read_bytes(),b'new')

    def test_upstream_delete_local_modify_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            report = compare_update(*self.setup_roots(d, ('old','local',None)))
            self.assertIn('README.md',report['conflicts'])

    def test_symlink_rejected(self):
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            roots = self.setup_roots(d, ('old','old','new'))
            (roots[1]/'link').symlink_to(roots[0]/'README.md')
            with self.assertRaises(TeamLibError):
                compare_update(*roots)


class AppliedUpdateTests(unittest.TestCase):
    def test_consecutive_updates_preserve_local_changes_and_upstream_baseline(self):
        from tests.local_helpers import repository, release, publish
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release, install_release
        from tools.teamlib.updates import apply_update
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            package=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'download-0')
            receipt=install_release(package,root/'target',workspace)
            (root/'target/releases/alice/root/1.0.0/README.md').write_text('local wording')
            (root/'target/unknown.txt').write_text('keep unknown')
            for index,version in enumerate(('1.1.0','1.2.0'),1):
                release(repo,version=version,text='safe')
                (repo/f'entries/alice/root/releases/{version}/payload/instructions.txt').write_text('new instructions '+str(index))
                from tools.teamlib.package import build_inventory
                import json
                folder=repo/f'entries/alice/root/releases/{version}'
                manifest=json.loads((folder/'manifest.json').read_text());manifest['files']=build_inventory(folder);(folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True))
                publish(repo)
                package=fetch_release(open_snapshot(config,workspace),'alice/root',version,root/f'download-{index}')
                receipt=apply_update(Path(receipt['receipt_path']),package,workspace)
                current=root/f'target/releases/alice/root/{version}/README.md'
                self.assertEqual(current.read_text(),'local wording')
                self.assertEqual((Path(receipt['baseline'])/f'releases/alice/root/{version}/README.md').read_text(),'safe')
                self.assertEqual((root/'target/unknown.txt').read_text(),'keep unknown')
                self.assertTrue(receipt['local_changes'])
                self.assertTrue(Path(receipt['recovery_backup']).is_dir())

    def test_binary_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            roots=[Path(d).resolve()/name for name in ('base','local','upstream')]
            for root,data in zip(roots,(b'old',b'local',b'new')):
                root.mkdir();(root/'sheet.xlsx').write_bytes(data)
            result=compare_update(*roots)
            self.assertEqual(result['conflicts'],['sheet.xlsx'])
            self.assertEqual((roots[1]/'sheet.xlsx').read_bytes(),b'local')

    def test_failed_receipt_write_rolls_back_target_and_receipt(self):
        from tests.local_helpers import repository, release, publish
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release, install_release
        from tools.teamlib.updates import apply_update
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            package=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'old')
            receipt=install_release(package,root/'target',workspace)
            original=Path(receipt['receipt_path']).read_bytes()
            release(repo,version='1.1.0');publish(repo)
            new=fetch_release(open_snapshot(config,workspace),'alice/root','1.1.0',root/'new')
            with patch('tools.teamlib.updates.create_receipt',side_effect=OSError('isolated write failure')):
                with self.assertRaises(OSError):apply_update(Path(receipt['receipt_path']),new,workspace)
            self.assertTrue((root/'target/releases/alice/root/1.0.0/README.md').is_file())
            self.assertFalse((root/'target/releases/alice/root/1.1.0').exists())
            self.assertEqual(Path(receipt['receipt_path']).read_bytes(),original)

    def test_overlap_is_blocked_without_creating_candidate_in_original(self):
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();base=root/'base';local=root/'local';upstream=local/'nested'
            base.mkdir();upstream.mkdir(parents=True)
            with self.assertRaises(TeamLibError):compare_update(base,local,upstream)
            self.assertEqual(list(local.iterdir()),[upstream])

    def test_receipt_target_alone_cannot_rebind_unmanaged_or_provenance_directory(self):
        import json,shutil
        from tests.local_helpers import repository,release,publish
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release,install_release
        from tools.teamlib.updates import apply_update
        from tools.teamlib.contracts import TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            old=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'old')
            receipt=install_release(old,root/'controlled',workspace)
            unmanaged=root/'unmanaged';shutil.copytree(root/'controlled',unmanaged);(unmanaged/'personal.txt').write_text('preserve')
            release(repo,version='1.1.0');publish(repo)
            new=fetch_release(open_snapshot(config,workspace),'alice/root','1.1.0',root/'new')
            for target in (unmanaged,Path(receipt['baseline'])):
                forged=dict(receipt,target=str(target));Path(receipt['receipt_path']).write_text(json.dumps(forged))
                with self.assertRaises(TeamLibError) as cm:apply_update(Path(receipt['receipt_path']),new,workspace)
                self.assertEqual(cm.exception.code,'CONFLICT')
                self.assertTrue((root/'controlled/releases/alice/root/1.0.0/README.md').is_file())
                self.assertTrue((target/'releases/alice/root/1.0.0/README.md').is_file())
            self.assertEqual((unmanaged/'personal.txt').read_text(),'preserve')

    def test_update_final_candidate_and_rollback_are_on_target_parent(self):
        import errno,os
        from unittest.mock import patch
        from tests.local_helpers import repository,release,publish
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release,install_release
        from tools.teamlib.updates import apply_update
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            old=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'old')
            target=root/'target';receipt=install_release(old,target,workspace)
            release(repo,version='1.1.0');publish(repo)
            new=fetch_release(open_snapshot(config,workspace),'alice/root','1.1.0',root/'new')
            original_rename=os.rename;moves=[]
            def simulated_separate_volumes(source,dest):
                source=Path(source);dest=Path(dest);moves.append((source,dest))
                if (workspace in source.parents)!=(workspace in dest.parents):
                    raise OSError(errno.EXDEV,'fixture different device')
                return original_rename(source,dest)
            with patch('tools.teamlib.updates.os.rename',side_effect=simulated_separate_volumes):
                result=apply_update(Path(receipt['receipt_path']),new,workspace)
            self.assertTrue((target/'releases/alice/root/1.1.0/README.md').is_file())
            candidates=[source for source,dest in moves if dest==target and source.name.startswith('teamlib-update-')]
            self.assertTrue(candidates)
            self.assertEqual(candidates[0].parent,target.parent)
            self.assertTrue(Path(result['recovery_backup']).is_dir())

    def test_cross_volume_receipt_failure_rollback_preserves_original(self):
        import errno,os
        from unittest.mock import patch
        from tests.local_helpers import repository,release,publish
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release,install_release
        from tools.teamlib.updates import apply_update
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            old=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'old')
            target=root/'target';receipt=install_release(old,target,workspace);original_receipt=Path(receipt['receipt_path']).read_bytes()
            release(repo,version='1.1.0');publish(repo)
            new=fetch_release(open_snapshot(config,workspace),'alice/root','1.1.0',root/'new')
            real_rename=os.rename
            def separate_volumes(source,dest):
                source=Path(source);dest=Path(dest)
                if (workspace in source.parents)!=(workspace in dest.parents):raise OSError(errno.EXDEV,'fixture different device')
                return real_rename(source,dest)
            with patch('tools.teamlib.updates.os.rename',side_effect=separate_volumes),patch('tools.teamlib.updates.create_receipt',side_effect=OSError('fixture failed receipt')):
                with self.assertRaises(OSError) as cm:apply_update(Path(receipt['receipt_path']),new,workspace)
            self.assertEqual(str(cm.exception),'fixture failed receipt')
            self.assertTrue((target/'releases/alice/root/1.0.0/README.md').is_file())
            self.assertEqual(Path(receipt['receipt_path']).read_bytes(),original_receipt)
            self.assertTrue(list(target.parent.glob('teamlib-update-*')))
