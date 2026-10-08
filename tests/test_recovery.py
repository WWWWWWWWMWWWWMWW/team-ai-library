import unittest
from tools.teamlib.recovery import plan_withdrawal, recommend_recovery
from tools.teamlib.contracts import TeamLibError


class RecoveryTests(unittest.TestCase):
    def test_withdrawal_is_pure_and_keeps_other_versions(self):
        state = dict(recommended_version='1.0.0',withdrawn_versions=[])
        candidate = plan_withdrawal(state,'1.0.0','scope incorrect')
        self.assertIsNone(candidate['recommended_version'])
        self.assertEqual(state['withdrawn_versions'],[])
        self.assertIn('1.0.0',candidate['withdrawn_versions'])
        other = plan_withdrawal(dict(recommended_version='2.0.0',withdrawn_versions=[]),'1.0.0','bad')
        self.assertEqual(other['recommended_version'],'2.0.0')

    def test_safe_explicit_version_required(self):
        state = dict(recommended_version='2.0.0',withdrawn_versions=['1.0.0'])
        self.assertEqual(recommend_recovery(state,'2.0.0',['1.0.0','2.0.0'])['version'],'2.0.0')
        with self.assertRaises(TeamLibError):
            recommend_recovery(state,'1.0.0',['1.0.0','2.0.0'])

    def test_withdraw_bad_recover_safe_while_preserving_local_and_other_entry(self):
        import tempfile
        import json
        from pathlib import Path
        from tests.local_helpers import repository, release, publish, context
        from tools.teamlib.snapshots import open_snapshot
        from tools.teamlib.install import fetch_release,install_release
        from tools.teamlib.updates import apply_update
        from tools.teamlib.reuse import preflight_reuse,record_run
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();repo=root/'source';config,workspace=repository(repo)
            release(repo,version='1.1.0',text='bad scope');release(repo,'alice/other');publish(repo)
            bad=fetch_release(open_snapshot(config,workspace),'alice/root','1.1.0',root/'bad')
            installed=install_release(bad,root/'installed',workspace)
            # Independent project edits are never revoked or rewritten by library recovery.
            project=root/'project';project.mkdir();(project/'plan.md').write_text('local project change')
            statepath=repo/'entries/alice/root/state.json';state=json.loads(statepath.read_text())
            state=plan_withdrawal(state,'1.1.0','scope incorrect');state['recommended_version']='1.0.0';statepath.write_text(json.dumps(state));publish(repo)
            with self.assertRaises(TeamLibError) as cm:preflight_reuse(config,dict(receipt_path=installed['receipt_path']),context(),workspace)
            self.assertEqual(cm.exception.code,'WITHDRAWN')
            safe=fetch_release(open_snapshot(config,workspace),'alice/root','1.0.0',root/'safe')
            recovered=apply_update(Path(installed['receipt_path']),safe,workspace)
            checked=preflight_reuse(config,dict(receipt_path=recovered['receipt_path']),context(),workspace)
            instructions=(root/'installed/releases/alice/root/1.0.0/payload/instructions.txt').read_text()
            self.assertEqual(instructions,'instructions')
            run=record_run(workspace,checked['sources'],dict(task_goal='read safe planning instructions',environment=context()['environment'],result='passed',artifacts=[],change_summary='read instructions only',unverified=['AI production outcome']))
            self.assertEqual(run['sources'][0]['version'],'1.0.0')
            self.assertEqual((project/'plan.md').read_text(),'local project change')
            self.assertTrue((repo/'entries/alice/other/releases/1.0.0/README.md').is_file())
            self.assertTrue(Path(recovered['recovery_backup']).is_dir())
            with self.assertRaises(TeamLibError):install_release(bad,root/'bad-again',workspace)
