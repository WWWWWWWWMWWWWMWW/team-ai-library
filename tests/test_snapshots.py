import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.git_helpers import create_remote, git, publish_fixture
from tools.teamlib.contracts import TeamLibError
from tools.teamlib.snapshots import open_snapshot


class SnapshotTests(unittest.TestCase):
    def test_shared_branch_snapshot_preserves_dirty_user_checkout(self):
        with TemporaryDirectory() as d:
            root = Path(d).resolve(); work, remote, config = create_remote(root)
            original_head = git(work, 'rev-parse', 'HEAD').stdout.strip()
            (work/'local-note.txt').write_text('unsaved personal work')
            snap = open_snapshot(config, root/'cache')
            self.assertEqual(snap['source_commit'], original_head)
            self.assertTrue((Path(snap['root'])/'entries/alice/demo/meta.json').exists())
            self.assertEqual((work/'local-note.txt').read_text(), 'unsaved personal work')
            self.assertEqual(git(work, 'rev-parse', 'HEAD').stdout.strip(), original_head)

    def test_explicit_source_pinned_while_default_fresh(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve(); work, remote, config=create_remote(root)
            old=git(work,'rev-parse','HEAD').stdout.strip()
            (work/'new-note.txt').write_text('new shared material')
            new=publish_fixture(work)
            pinned=open_snapshot(config,root/'cache',old)
            fresh=open_snapshot(config,root/'cache')
            self.assertEqual(pinned['source_commit'],old)
            self.assertFalse((Path(pinned['root'])/'new-note.txt').exists())
            self.assertEqual(fresh['source_commit'],new)
            self.assertTrue((Path(fresh['root'])/'new-note.txt').exists())

    def test_remote_failure_never_passes_as_fresh_cached_state(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve(); work, remote, config=create_remote(root)
            open_snapshot(config,root/'cache')
            remote.rename(root/'offline.git')
            with self.assertRaises(TeamLibError) as error:
                open_snapshot(config,root/'cache')
            self.assertEqual(error.exception.code,'REMOTE_FAILED')

    def test_unreachable_commit_cannot_become_shared_material(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve(); work, remote, config=create_remote(root)
            with self.assertRaises(TeamLibError):
                open_snapshot(config,root/'cache','0'*40)

    def test_snapshot_rejects_tracked_link_without_following_target(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve(); work, remote, config=create_remote(root)
            outside=root/'private.txt';outside.write_text('not shareable')
            (work/'link').symlink_to(outside)
            publish_fixture(work)
            with self.assertRaises(TeamLibError):open_snapshot(config,root/'cache')
            self.assertEqual(outside.read_text(),'not shareable')

    def test_export_attributes_cannot_hide_or_transform_tracked_bytes(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();work,remote,config=create_remote(root)
            (work/'.gitattributes').write_text('.gitattributes export-ignore\nhidden.txt export-ignore\nraw.txt export-subst\n')
            (work/'hidden.txt').write_bytes(b'all tracked material must be reviewed\r\n')
            raw=b'$Format:%H$\r\n';(work/'raw.txt').write_bytes(raw)
            source=publish_fixture(work)
            snapshot=open_snapshot(config,root/'cache');tree=Path(snapshot['root'])
            self.assertEqual(snapshot['source_commit'],source)
            self.assertTrue((tree/'.gitattributes').exists())
            self.assertEqual((tree/'hidden.txt').read_bytes(),b'all tracked material must be reviewed\r\n')
            self.assertEqual((tree/'raw.txt').read_bytes(),raw)

    def test_github_mode_read_gate_precedes_any_git_access(self):
        from unittest.mock import patch
        with TemporaryDirectory() as d:
            root=Path(d).resolve();work,remote,config=create_remote(root)
            config.update(platform='github',remote='https://github.com/company/library.git')
            with patch('tools.teamlib.platform.doctor_read',side_effect=TeamLibError('SCOPE_DENIED','Not verified private')):
                with self.assertRaises(TeamLibError) as error:open_snapshot(config,root/'cache')
            self.assertEqual(error.exception.code,'SCOPE_DENIED')
            self.assertFalse((root/'cache').exists())
